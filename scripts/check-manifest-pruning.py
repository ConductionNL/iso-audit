"""Detecteer velden die de kube-API stil weggooit uit onze manifests.

## Waarom dit bestaat

De API pruunt onbekende velden **zonder te falen**. Op 2026-08-14 stuurde
`deploy/deployment.yaml` een `fieldRef` als source van een projected volume — dat bestaat
daar niet. Kubernetes gooide de entry weg tot `{}`, het namespace-bestand ontbrak in de
pod, en de code viel terug op een hardcoded namespace. In `iso-platform` klopte die per
ongeluk; in elke andere namespace was het stil fout geweest.

De enige aanwijzing was één warning bij een `kubectl patch`, tussen de rest van de output.
Een gewone `kubectl apply --dry-run=server` **zonder** `-o json` meldde niets.

## Hoe het werkt

Twee signalen, en beide zijn nagerekend tegen de echte fout:

1. `--dry-run=server -o json` faalt hard op zo'n manifest. `-o json` is essentieel: het
   dwingt de server het op te slaan object te renderen in plaats van alleen te bevestigen.
2. Waar pruning een **lijst-element** leeg achterlaat, is dat altijd fout: `- iets: {}` in
   een lijst betekent dat wij een veld stuurden dat de server niet kent. Een lege dict als
   *waarde* kan wél legitiem zijn (`emptyDir: {}`), dus daarop niet controleren.

Vereist een bereikbaar cluster; daarom een pre-flight in `rollout-portal.sh` en geen
CI-stap.

Usage:
    python3 scripts/check-manifest-pruning.py            # deploy/
    python3 scripts/check-manifest-pruning.py --pad argo # andere kustomize-map
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


def _server_view(pad: str) -> dict[str, Any]:
    opdracht = f"kubectl kustomize {pad} | kubectl apply --dry-run=server -o json -f -"
    # Vaste pipeline, pad komt van de operator; geen shell.
    klaar = subprocess.run(
        opdracht, shell=True, capture_output=True, text=True, timeout=180, check=False
    )
    if klaar.returncode != 0:
        print("server-side validatie faalde:", file=sys.stderr)
        print(klaar.stderr.strip()[:1200] or klaar.stdout.strip()[:1200], file=sys.stderr)
        raise SystemExit(1)
    geladen: dict[str, Any] = json.loads(klaar.stdout)
    return geladen


def lege_lijstelementen(obj: Any, pad: str = "") -> list[str]:
    """Vind lijst-elementen die leeg zijn geworden."""
    uit: list[str] = []
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            if v in ({}, [], None):
                uit.append(f"{pad}[{i}]")
            else:
                uit += lege_lijstelementen(v, f"{pad}[{i}]")
    elif isinstance(obj, dict):
        for sleutel, v in obj.items():
            uit += lege_lijstelementen(v, f"{pad}.{sleutel}")
    return uit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pad", default="deploy", help="kustomize-map (default: deploy)")
    args = parser.parse_args()

    top = _server_view(args.pad)
    fout: list[str] = []
    for item in top.get("items", [top]):
        naam = f"{item.get('kind')}/{item.get('metadata', {}).get('name')}"
        fout += [f"{naam} {p}" for p in lege_lijstelementen(item)]

    if fout:
        print("STIL GEPRUUND — wij stuurden een veld dat de API niet kent:", file=sys.stderr)
        for f in fout:
            print(f"   {f}", file=sys.stderr)
        return 1
    print("  manifests: niets gepruned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
