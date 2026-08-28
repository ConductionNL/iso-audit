"""Volledig auditrapport — alle clausules met normtekst, bewijs en bevindingen.

Per norm een Markdown-rapport met voor elke clausule:

- Normtekst + interpretatie + bewijslast (uit `iso_audit.data.normteksten`)
- Gevonden bewijs (Drive-documenten + Miro-notities) uit lokale DB
- Interview-bevinding (NC / OFI / positief) uit `interviews`-tabel
- Planning 2025 (uit `audit_planning`-tabel, pipeline-runtime schema-extensie)

Gemigreerd uit `Ops_to_Biz/audit/full_report.py` per milestone B §2.5.4.
Wijzigingen: imports naar `iso_audit.*`; scope-filter + audit_planning
gracefully gemist via `sqlite3.OperationalError`-catch.

Gebruik:
    python -m iso_audit.reporting.full_report --norm 9001
    python -m iso_audit.reporting.full_report --norm 27001
    python -m iso_audit.reporting.full_report --norm beide
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# src/iso_audit/reporting/full_report.py → parent x 4 = repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_OUTPUT_DIR = _REPO_ROOT / "output" / "audit_reports"

BEVINDING_LABEL: dict[str, str] = {
    "NC": "🔴 Non-conformiteit",
    "OFI": "🟡 Verbeterpunt (OFI)",
    "positief": "🟢 Positief",
    "overgeslagen": "⚪ Overgeslagen",
}


def _drive_link(doc_id: str, mime: str | None) -> str:
    """Drive-URL met juiste pad per MIME-type."""
    if mime == "application/vnd.google-apps.document":
        return f"https://docs.google.com/document/d/{doc_id}"
    if mime == "application/vnd.google-apps.spreadsheet":
        return f"https://docs.google.com/spreadsheets/d/{doc_id}"
    return f"https://drive.google.com/file/d/{doc_id}"


def _fetch_bewijzen(conn: sqlite3.Connection, norm: str) -> list[sqlite3.Row]:
    """Bewijzen-fetch met `documents.scope='in'`-filter; fallback bij ontbrekende kolom."""
    sql_with_scope = """
        SELECT cm.clausule_id, cm.doc_id, cm.herkomst,
               COALESCE(d.naam, m.tekst) AS naam,
               d.mime_type
        FROM clause_matches cm
        LEFT JOIN documents d  ON d.id  = cm.doc_id AND cm.herkomst = 'Drive'
        LEFT JOIN miro_notes m ON m.id  = cm.doc_id AND cm.herkomst = 'Miro'
        WHERE cm.norm IN (?, 'beide')
          AND (cm.herkomst != 'Drive' OR d.scope = 'in')
          AND cm.sub_punt = ''
        ORDER BY cm.clausule_id, naam
    """
    sql_zonder_scope = """
        SELECT cm.clausule_id, cm.doc_id, cm.herkomst,
               COALESCE(d.naam, m.tekst) AS naam,
               d.mime_type
        FROM clause_matches cm
        LEFT JOIN documents d  ON d.id  = cm.doc_id AND cm.herkomst = 'Drive'
        LEFT JOIN miro_notes m ON m.id  = cm.doc_id AND cm.herkomst = 'Miro'
        WHERE cm.norm IN (?, 'beide')
          AND cm.sub_punt = ''
        ORDER BY cm.clausule_id, naam
    """
    try:
        return conn.execute(sql_with_scope, (norm,)).fetchall()
    except sqlite3.OperationalError as e:
        logger.warning("documents.scope-kolom ontbreekt, fallback-query: %s", e)
        return conn.execute(sql_zonder_scope, (norm,)).fetchall()


def _fetch_planning(conn: sqlite3.Connection, norm: str) -> dict[str, str]:
    """Audit-planning per clausule; lege dict als `audit_planning`-tabel ontbreekt."""
    try:
        rows = conn.execute(
            "SELECT clausule_id, kwartaal FROM audit_planning WHERE norm=? AND jaar=2025",
            (norm,),
        ).fetchall()
    except sqlite3.OperationalError as e:
        logger.warning("audit_planning-tabel ontbreekt: %s", e)
        return {}
    return {r["clausule_id"]: r["kwartaal"] for r in rows if r["kwartaal"]}


def _laad_normteksten(norm: str) -> dict[str, dict[str, Any]]:
    """Returnt `{clausule_id: {normtekst, interpretatie, bewijslast, ...}}` voor de norm."""
    from iso_audit.data.normteksten import NORMTEKSTEN_9001, NORMTEKSTEN_27001

    if norm == "9001":
        return NORMTEKSTEN_9001
    if norm == "27001":
        return NORMTEKSTEN_27001
    return {**NORMTEKSTEN_9001, **NORMTEKSTEN_27001}


def _sorteersleutel(clausule_id: str) -> tuple[int, ...]:
    """Sorteert "5.12" correct na "5.9" (numeriek, niet lexicografisch).

    Bijlage A-maatregelen dragen sinds 2026-08-28 een `A.`-prefix en horen ná de
    managementclausules: eerst hoofdstuk 4 t/m 10, dan A.5 t/m A.8. Dat is de volgorde van de
    norm zelf, en een rapport dat A.5.1 tussen 4.4 en 5.1 zet, leest als een fout.
    """
    annex = clausule_id.startswith("A.")
    parts = clausule_id.removeprefix("A.").split(".")
    try:
        return (1 if annex else 0, *(int(p) for p in parts))
    except ValueError:
        return (0,)


def genereer_rapport(norm: str) -> str:
    """Genereer een Markdown-rapport voor de gegeven norm."""
    from iso_audit.classification.clause_mapping import laad_clause_map
    from iso_audit.store import verbinding

    conn = verbinding()
    clause_map = laad_clause_map(norm)
    clausules: dict[str, Any] = clause_map.get("clausules", {})

    bewijzen: dict[str, list[dict[str, Any]]] = {k: [] for k in clausules}
    for row in _fetch_bewijzen(conn, norm):
        if row["clausule_id"] in bewijzen:
            bewijzen[row["clausule_id"]].append(dict(row))

    interviews: dict[str, dict[str, Any]] = {}
    for row in conn.execute(
        "SELECT * FROM interviews WHERE norm IN (?, 'beide')", (norm,)
    ).fetchall():
        interviews[row["clausule_id"]] = dict(row)

    planning = _fetch_planning(conn, norm)

    gedekt = sum(1 for v in bewijzen.values() if v)
    total = len(clausules)
    interviews_gedaan = len(interviews)
    conn.close()

    normteksten = _laad_normteksten(norm)
    norm_label = clause_map.get("norm", norm)
    dekking_pct = round(gedekt / total * 100) if total else 0

    regels: list[str] = [
        f"# Volledig Auditrapport — {norm_label}",
        "",
        f"**Datum**: {date.today()}  ",
        f"**Clausule-dekking**: {gedekt}/{total} ({dekking_pct}%)  ",
        f"**Interviews gedaan**: {interviews_gedaan}  ",
        "",
        "---",
        "",
    ]

    for clausule_id in sorted(clausules, key=_sorteersleutel):
        titel = clausules[clausule_id].get("titel", "")
        nt = normteksten.get(clausule_id, {})
        items = bewijzen.get(clausule_id, [])
        iv = interviews.get(clausule_id)
        plan = planning.get(clausule_id)

        drive_items = [i for i in items if i["herkomst"] == "Drive"]
        miro_items = [i for i in items if i["herkomst"] == "Miro"]

        regels.append(f"## {clausule_id} — {titel}")
        regels.append("")

        if nt.get("normtekst"):
            regels.append("**Normtekst**")
            regels.append(f"> {nt['normtekst']}")
            regels.append("")

        if nt.get("interpretatie"):
            regels.append("**Interpretatie**")
            regels.append(nt["interpretatie"])
            regels.append("")

        if nt.get("bewijslast"):
            regels.append("**Bewijslast** — wat moet aanwezig zijn:")
            for b in nt["bewijslast"]:
                regels.append(f"- {b}")
            regels.append("")

        if drive_items or miro_items:
            totaal_bewijs = len(drive_items) + len(miro_items)
            regels.append(f"**Gevonden bewijs** ({totaal_bewijs})")
            for item in drive_items[:15]:
                link = _drive_link(item["doc_id"], item.get("mime_type"))
                regels.append(f"- [{item['naam']}]({link})")
            if len(drive_items) > 15:
                regels.append(f"- _...en {len(drive_items) - 15} meer Drive-documenten_")
            for item in miro_items[:5]:
                tekst = (item["naam"] or "")[:80]
                regels.append(f"- _(Miro)_ {tekst}")
            regels.append("")
        else:
            regels.append("**Gevonden bewijs**: _(geen)_")
            regels.append("")

        if iv:
            label = BEVINDING_LABEL.get(iv["bevinding"], iv["bevinding"])
            regels.append(f"**Bevinding**: {label}")
            if iv.get("notitie"):
                regels.append(f"> {iv['notitie']}")
            regels.append("")
        else:
            regels.append("**Bevinding**: _(nog niet geïnterviewd)_")
            regels.append("")

        if plan:
            regels.append(f"**Planning 2025**: {plan}")
        else:
            regels.append("**Planning 2025**: _(niet in auditplanning)_")
        regels.append("")
        regels.append("---")
        regels.append("")

    regels.append(f"_Gegenereerd op {date.today()} uit lokale audit DB_")
    return "\n".join(regels)


def schrijf_rapport(norm: str, output_dir: str | os.PathLike[str] | None = None) -> str:
    """Genereer en schrijf het rapport naar `output_dir`/`Auditrapport_volledig_*.md`."""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    pad = out_dir / f"Auditrapport_volledig_{norm}_{date.today()}.md"
    inhoud = genereer_rapport(norm)
    pad.write_text(inhoud, encoding="utf-8")
    logger.info("Rapport geschreven: %s", pad)
    return str(pad)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Volledig auditrapport genereren")
    parser.add_argument(
        "--norm",
        choices=["9001", "27001", "beide"],
        default="beide",
    )
    args = parser.parse_args()
    if args.norm == "beide":
        for n in ["9001", "27001"]:
            pad = schrijf_rapport(n)
            print(f"Rapport: {pad}")
    else:
        pad = schrijf_rapport(args.norm)
        print(f"Rapport: {pad}")
    return 0
