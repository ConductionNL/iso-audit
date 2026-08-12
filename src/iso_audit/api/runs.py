"""Runs binnen een audit: append-only registratie en aanvullend samenvoegen.

Een tweede run in dezelfde audit **vult aan**: nieuwe kandidaten komen erbij, wat al
getrieerd is blijft getrieerd. Dat is wat de praktijk vraagt — Jira erbij zetten na
een Drive-only run — maar het vraagt een dedup-regel, anders triageert de auditor
hetzelfde twee keer.

## Dedup

Sleutel: ``(standard, clause, source, genormaliseerde titel)``. Deterministisch in
code, geen LLM en geen gelijkenis-drempel. Dat laatste is een bewuste weigering: een
drempel die niemand kan uitleggen hoort niet in een auditwerktuig, en "0.83 leek genoeg"
is geen antwoord aan een auditor.

Overgeslagen duplicaten worden **geteld bij het run-record**, niet stil weggelaten —
dezelfde discipline als het ``dropped``-spoor uit `auditmemo-curate`. Een run die
dertig kandidaten oplevert waarvan achttien al bekend zijn, moet niet lijken alsof hij
niets deed.

## Wat een run niet doet

Bestaande regels in ``findings.json`` wijzigen of verwijderen. Alleen toevoegen.
Daarmee blijft de triage-trail als geheel geldig: een beslissing verwijst naar een
bevinding die niet onder haar voeten is veranderd.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUNS = "runs.jsonl"
FINDINGS = "findings.json"

_WS = re.compile(r"\s+")


def _nu() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def dedup_sleutel(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    """Deterministische sleutel voor deduplicatie tussen runs.

    Normalisatie van de titel is lowercasing plus whitespace-collaps. Bewust niet
    meer: interpunctie strippen of synonymen matchen maakt de regel onuitlegbaar en
    daarmee onbruikbaar in een audit.
    """
    titel = _WS.sub(" ", str(finding.get("title", "")).strip().lower())
    return (
        str(finding.get("standard", "")),
        str(finding.get("clause", "")),
        str(finding.get("source") or ""),
        titel,
    )


def voeg_toe(
    audit_dir: str | Path,
    kandidaten: list[dict[str, Any]],
) -> tuple[int, int]:
    """Voeg kandidaten aanvullend toe aan de werkset.

    Retourneert ``(toegevoegd, overgeslagen)``. Bestaande bevindingen worden niet
    aangeraakt — ook niet als een kandidaat "beter" lijkt: dat oordeel is aan de
    auditor, niet aan een merge-functie.
    """
    pad = Path(audit_dir) / FINDINGS
    bestaand: list[dict[str, Any]] = (
        json.loads(pad.read_text(encoding="utf-8")) if pad.is_file() else []
    )
    bekend = {dedup_sleutel(f) for f in bestaand}

    toegevoegd = 0
    overgeslagen = 0
    for k in kandidaten:
        sleutel = dedup_sleutel(k)
        if sleutel in bekend:
            overgeslagen += 1
            continue
        bekend.add(sleutel)
        bestaand.append(k)
        toegevoegd += 1

    if toegevoegd:
        pad.write_text(
            json.dumps(bestaand, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    return toegevoegd, overgeslagen


def registreer(
    audit_dir: str | Path,
    *,
    door: str,
    modus: str,
    norm: str,
    bronnen: list[str],
    hoofdstuk: str | None = None,
    toegevoegd: int = 0,
    overgeslagen: int = 0,
    fout: str | None = None,
) -> dict[str, Any]:
    """Schrijf één append-only run-record en retourneer het.

    Ook een mislukte run wordt geregistreerd, met zijn fout. Weglaten maakt het
    overzicht schoner en het dossier onvolledig — een run die faalde op een
    ontbrekende credential is precies wat je later wil terugzien.
    """
    dir_ = Path(audit_dir)
    pad = dir_ / RUNS
    nummer = som(dir_) + 1
    record: dict[str, Any] = {
        "run_id": f"run-{nummer:04d}",
        "gestart": _nu(),
        "door": door,
        "modus": modus,
        "norm": norm,
        "bronnen": bronnen,
        "hoofdstuk": hoofdstuk or "",
        "toegevoegd": toegevoegd,
        "overgeslagen": overgeslagen,
        "status": "fout" if fout else "klaar",
    }
    if fout:
        record["fout"] = fout[:500]
    with pad.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def lijst(audit_dir: str | Path) -> list[dict[str, Any]]:
    """Alle run-records, oudste eerst. Onleesbare regels worden overgeslagen."""
    pad = Path(audit_dir) / RUNS
    if not pad.is_file():
        return []
    records: list[dict[str, Any]] = []
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel:
            continue
        try:
            records.append(json.loads(regel))
        except json.JSONDecodeError:
            continue
    return records


def som(audit_dir: str | Path) -> int:
    """Aantal geregistreerde runs."""
    return len(lijst(audit_dir))


def geraadpleegde_bronnen(audit_dir: str | Path) -> list[str]:
    """Alle bronnen die ooit in deze audit zijn geraadpleegd, gesorteerd."""
    uniek: set[str] = set()
    for r in lijst(audit_dir):
        for b in r.get("bronnen") or []:
            if b:
                uniek.add(str(b))
    return sorted(uniek)
