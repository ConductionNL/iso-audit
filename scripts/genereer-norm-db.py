#!/usr/bin/env python3
"""Genereer `examples/norms/<slug>.yaml` uit `iso_audit.data.normteksten`.

De norm-DB die de memo-bouwer leest is een export uit de repo-bron. Die export was tot
2026-08-24 met de hand gemaakt en bevatte **13 van de 121** clausules, en dat had twee gevolgen
die allebei stil waren:

1. `iso-audit memo` weigerde op de echte dataset ("Clausule '10.3' ontbreekt"), en dat werd
   gelezen als een licentieprobleem terwijl de tekst gewoon in de repo staat.
2. `run_job._resolve_standard()` gebruikt deze DB om te bepalen bij welke norm een bevinding
   hoort ("alleen in 27001 → 27001; anders → 9001"). Met 13 clausules zei die DB bijna altijd
   "niet in 27001", dus viel vrijwel alles terug op de default. Gemeten op de werkset van
   2026-08-24: **448 van de 903 bevindingen droegen de verkeerde norm** — clausule 8.24
   (cryptografie, Annex A van 27001) stond gelabeld als ISO 9001:2015.

Een export die met de hand wordt bijgehouden loopt achter, en dat is hier niet zichtbaar: er
komt geen fout, alleen een verkeerd antwoord. Vandaar dit script plus
`tests/data/test_norm_db_export.py`, die faalt zodra bron en export uiteenlopen.

De teksten zijn bewust verkorte Nederlandse weergaven en geen officiële ISO-tekst; die keuze is
in de bron gemaakt en wordt hier alleen doorgegeven.

Writes: examples/norms/iso-9001-2015.yaml, examples/norms/iso-27001-2022.yaml
Idempotent: ja — dezelfde bron levert byte-identieke uitvoer
Requires: iso_audit.data.normteksten

Usage:
  uv run python scripts/genereer-norm-db.py            # schrijf de export
  uv run python scripts/genereer-norm-db.py --check    # faal als de export achterloopt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from iso_audit.classification.clause_mapping import laad_clause_map
from iso_audit.data import normteksten

UITVOER = Path("examples/norms")

NORMEN: dict[str, tuple[str, str, dict[str, Any]]] = {
    "iso-9001-2015": ("ISO 9001:2015", "9001", normteksten.NORMTEKSTEN_9001),
    "iso-27001-2022": ("ISO 27001:2022", "27001", normteksten.NORMTEKSTEN_27001),
}


def bouw(slug: str) -> dict[str, Any]:
    """Bouw de export-structuur voor één norm."""
    naam, norm, bron = NORMEN[slug]
    # Titels staan in de clause-map, teksten in de normteksten. Bewust die twee bronnen en
    # geen derde plek waar een titel opnieuw wordt opgeschreven: dan lopen ze uiteen.
    titels = laad_clause_map(norm).get("clausules", {})
    clausules: dict[str, Any] = {}
    for clausule_id in sorted(bron, key=_sorteersleutel):
        gegevens = bron[clausule_id]
        clausules[clausule_id] = {
            "title_nl": titels.get(clausule_id, {}).get("titel", ""),
            "title_en": "",
            "text_nl": gegevens.get("normtekst", ""),
            "text_en": "",
        }
    return {
        "metadata": {
            "standard": naam,
            "slug": slug,
            "source": (
                "iso_audit.data.normteksten (verkorte NL-weergave, repo-bron) — geen "
                "officiële ISO-volledige tekst. Gegenereerd door "
                "scripts/genereer-norm-db.py; niet met de hand bijwerken."
            ),
        },
        "clauses": clausules,
    }


def _sorteersleutel(clausule_id: str) -> tuple[int, ...]:
    """Sorteer 5.9 vóór 5.10 — tekstueel sorteren zet 5.10 vóór 5.9."""
    return tuple(int(deel) if deel.isdigit() else 0 for deel in clausule_id.split("."))


def naar_yaml(gegevens: dict[str, Any]) -> str:
    return str(yaml.safe_dump(gegevens, allow_unicode=True, sort_keys=False, width=98))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument(
        "--check", action="store_true", help="faal als de export achterloopt op de bron"
    )
    args = parser.parse_args(argv)

    afwijkend: list[str] = []
    for slug in NORMEN:
        pad = UITVOER / f"{slug}.yaml"
        inhoud = naar_yaml(bouw(slug))
        if args.check:
            huidig = pad.read_text(encoding="utf-8") if pad.is_file() else ""
            if huidig != inhoud:
                afwijkend.append(str(pad))
            continue
        pad.parent.mkdir(parents=True, exist_ok=True)
        pad.write_text(inhoud, encoding="utf-8")
        aantal = len(NORMEN[slug][2])
        print(f"{pad}: {aantal} clausules")

    if afwijkend:
        print(
            "norm-DB loopt achter op iso_audit.data.normteksten: "
            + ", ".join(afwijkend)
            + "\nDraai: uv run python scripts/genereer-norm-db.py",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
