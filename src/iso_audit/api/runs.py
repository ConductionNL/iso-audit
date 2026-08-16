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
    nummer = som(dir_) + 1
    record: dict[str, Any] = {
        "run_id": f"run-{nummer:04d}",
        "soort": "start",
        "gestart": _nu(),
        "door": door,
        "modus": modus,
        "norm": norm,
        "bronnen": bronnen,
        "hoofdstuk": hoofdstuk or "",
        "toegevoegd": toegevoegd,
        "overgeslagen": overgeslagen,
        "status": "fout" if fout else "loopt",
    }
    if fout:
        record["fout"] = fout[:500]
        record["geeindigd"] = record["gestart"]
    _append(dir_, record)
    return record


def afsluiten(
    audit_dir: str | Path,
    run_id: str,
    *,
    toegevoegd: int = 0,
    overgeslagen: int = 0,
    fout: str | None = None,
) -> dict[str, Any]:
    """Schrijf het afsluitrecord van een run — append-only, niets wordt overschreven.

    Waarom twee records en geen update: `runs.jsonl` is de audit-trail, en append-only is
    daar de garantie. Tot 2026-08-14 las de route `laatste_merge` direct nadat de
    worker-thread was gestart — dus altijd `(0, 0)` — en schreef `status: "klaar"`. Elk
    live-run-record beweerde daardoor permanent "klaar, 0 toegevoegd, 0 overgeslagen",
    geschreven vóórdat er iets gelezen was, en append-only betekent dat je dat niet meer
    kunt rechtzetten.

    De uitkomst is eigendom van de worker; die roept dit aan als hij klaar is of faalt.
    Lezers gebruiken `samengevat()`, dat per `run_id` de laatste stand teruggeeft.
    """
    dir_ = Path(audit_dir)
    record: dict[str, Any] = {
        "run_id": run_id,
        "soort": "afsluiting",
        "geeindigd": _nu(),
        "toegevoegd": toegevoegd,
        "overgeslagen": overgeslagen,
        "status": "fout" if fout else "klaar",
    }
    if fout:
        record["fout"] = fout[:500]
    _append(dir_, record)
    return record


def _append(audit_dir: Path, record: dict[str, Any]) -> None:
    """Eén regel toevoegen. Eén `write` van één regel < 4 KiB is op POSIX atomair genoeg
    voor gelijktijdige appends; dat is dezelfde aanname waarop `triage_log.jsonl` leunt."""
    with (audit_dir / RUNS).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


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


def samengevat(audit_dir: str | Path) -> list[dict[str, Any]]:
    """Per run de laatste stand, oudste eerst — de vorm waar de UI iets aan heeft.

    `lijst()` blijft de ruwe append-only waarheid; hier worden de records per `run_id`
    over elkaar heen gelegd (laatste wint per veld). Een run met alleen een startrecord
    houdt `status: "loopt"`.
    """
    per_run: dict[str, dict[str, Any]] = {}
    for r in lijst(audit_dir):
        rid = str(r.get("run_id", ""))
        if not rid:
            continue
        if rid in per_run:
            per_run[rid].update(r)
        else:
            per_run[rid] = dict(r)
    return list(per_run.values())


def som(audit_dir: str | Path) -> int:
    """Aantal runs — niet het aantal records.

    Sinds een run twee records heeft (start + afsluiting) zou tellen op regels elke run
    dubbel tellen. Dat raakt twee dingen: de nummering in `registreer()` en
    `aantal_runs` op het dashboard (`overzicht.regel`).
    """
    return len({str(r.get("run_id", "")) for r in lijst(audit_dir) if r.get("run_id")})


def geraadpleegde_bronnen(audit_dir: str | Path) -> list[str]:
    """Bronnen uit afgeronde runs, gesorteerd.

    Runs met status `loopt` of `fout` vallen af: een run die op een ontbrekende credential
    faalde heeft niets gelezen, en die kolom is een bewijsuitspraak.

    Een sim-run leest ook niets en zou hier strikt genomen ook niet in horen. Dat filter
    is er bewust **niet**: het zou de betekenis van de dashboardkolom veranderen, en dat is
    een aparte beslissing dan het repareren van een run-record dat "klaar, 0, 0" beweerde
    voordat er iets gelezen was.
    """
    uniek: set[str] = set()
    for r in samengevat(audit_dir):
        if r.get("status") != "klaar":
            continue
        for b in r.get("bronnen") or []:
            if b:
                uniek.add(str(b))
    return sorted(uniek)
