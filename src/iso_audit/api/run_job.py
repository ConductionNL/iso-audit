"""Live-run-orchestratie: run_audit (chapter-scoped) → DB-export → draft.

Stap 2 in live-modus draait de echte pipeline (Drive-ingest + LLM-classificatie),
vangt de "Stap X/7"-voortgang op via een logging-handler, exporteert de findings
uit de DB en draaft de kop-NC's. Background-thread; geen interactieve review
(`no_review=True`). De DB→Finding-mapping is een pure, testbare functie.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from iso_audit.api.runs import Kosten
from iso_audit.memo.draft import draft_findings
from iso_audit.memo.models import BronRef, Finding
from iso_audit.memo.norm_lookup import NormDatabase, laad_norm_db

_NORM_SLUG = {"9001": "iso-9001-2015", "27001": "iso-27001-2022"}
_SEV = {"NC": "NC", "OFI": "OFI", "positief": "POSITIVE"}


def _bron_url(herkomst: str, doc_id: str) -> str | None:
    """Bouw een klikbare link naar het brondocument o.b.v. herkomst + id.

    Boring & auditable: per bron een expliciete, well-known URL-vorm; onbekende
    bron of ontbrekend id → geen link (None). Geen geheime mapping-logica.
    """
    import os

    if not doc_id:
        return None
    h = (herkomst or "").lower()
    if h == "drive":
        return f"https://drive.google.com/open?id={doc_id}"
    if h == "jira":
        base = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
        return f"{base}/browse/{doc_id}" if base else None
    if h == "miro":
        board = os.environ.get("MIRO_BOARD_ID", "")
        return f"https://miro.com/app/board/{board}/?moveToWidget={doc_id}" if board else None
    return None


class _ProgressHandler(logging.Handler):
    """Duwt pipeline-logregels naar een sink (voor live voortgang in de UI)."""

    def __init__(self, sink: Callable[[str], None]) -> None:
        super().__init__()
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self._sink(record.getMessage())


def _resolve_standard(row_norm: str, clause: str, db: NormDatabase | None) -> str:
    """Bepaal de norm-DB-slug per finding. Bij norm='beide' via clausule-membership.

    Clausule-ID's botsen tussen 9001 en 27001 (bv. §6.2); de DB slaat 'beide' op
    zonder per-finding norm. We resolven dan: alleen in 27001 → 27001; anders
    (alleen 9001, of botsing in beide) → 9001 (default).
    """
    if row_norm in _NORM_SLUG:
        return _NORM_SLUG[row_norm]
    if (
        db is not None
        and db.has_clause("iso-27001-2022", clause)
        and not db.has_clause("iso-9001-2015", clause)
    ):
        return "iso-27001-2022"
    return "iso-9001-2015"


def export_db_findings(*, norm: str = "9001", norms_dir: str | None = None) -> list[Finding]:
    """Lees de bevindingen uit de audit-DB en map ze naar het memo-Finding-model."""
    import sqlite3

    from iso_audit.classification.clause_mapping import laad_clause_map
    from iso_audit.classification.thema import bepaal_thema
    from iso_audit.store import verbinding

    titels = laad_clause_map(norm).get("clausules", {})
    db = laad_norm_db(norms_dir) if norms_dir else None
    conn = verbinding()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM bevindingen ORDER BY clausule_id").fetchall()
    conn.close()
    findings: list[Finding] = []
    for r in rows:
        clausule = r["clausule_id"]
        titel = titels.get(clausule, {}).get("titel", clausule)
        herkomst = r["herkomst"] or ""
        doc_id = r["doc_id"] or ""
        beschrijving = r["beschrijving"] or r["onderbouwing"] or "(geen beschrijving)"
        thema = bepaal_thema(
            {
                "beschrijving": r["beschrijving"],
                "onderbouwing": r["onderbouwing"],
                "document_naam": r["document_naam"],
            }
        )
        findings.append(
            Finding(
                id=str(r["id"]),
                severity=_SEV.get(r["classificatie"], "UNCLASSIFIED"),  # type: ignore[arg-type]
                standard=_resolve_standard(r["norm"], clausule, db),
                clause=clausule,
                source=herkomst,  # bevinding berust op bron Y (Drive/Miro/…)
                thema=thema,
                # Geen "NC"-prefix: niet elke bevinding is een NC (ook OFI/positief).
                title=f"§{clausule} — {titel} [{(r['document_naam'] or '?')[:50]}]",
                description=beschrijving,
                bronnen=[
                    BronRef(
                        herkomst=herkomst,
                        doc_id=doc_id,
                        doc_naam=r["document_naam"] or "",
                        url=_bron_url(herkomst, doc_id),
                        beschrijving=beschrijving,
                    )
                ],
            )
        )
    return findings


def run_live_pipeline(
    *,
    norm: str,
    sources: list[str],
    chapter: str | None,
    on_log: Callable[[str], None],
    alleen_ingest: bool = False,
) -> Kosten | None:
    """Draai de echte audit-pipeline met opgevangen voortgang (geen review-prompt).

    `alleen_ingest` stopt na het inlezen en vastleggen; die modus raakt de Claude-API niet.

    Returnt de kosten van de classificatie, zodat de worker die in het run-record kan zetten.
    `None` bij een ingest-only run: die raakt de API niet, dus er zijn geen kosten — en nul
    rapporteren zou suggereren dat er geclassificeerd is.
    """
    from iso_audit import pipeline
    from iso_audit.modes.autonoom import AutonoomMode
    from iso_audit.store import initialiseer, verbinding

    if not sources:
        # Laatste gate vóór de pipeline. Hier stond `sources or ["drive"]`, waardoor een
        # lege selectie stil een drive-run werd — ook als Drive niet gekoppeld was.
        raise ValueError("Geen bronnen opgegeven; een run zonder bron leest niets.")

    handler = _ProgressHandler(on_log)
    pijplijn_logger = logging.getLogger("iso_audit")
    pijplijn_logger.addHandler(handler)
    # INFO-regels (de "Stap X/7"-voortgang) moeten de handler bereiken; default
    # kan de logger op WARNING staan. Niveau tijdelijk verlagen + herstellen.
    vorig_niveau = pijplijn_logger.level
    pijplijn_logger.setLevel(logging.INFO)
    conn = verbinding()
    initialiseer(conn)

    kosten_uit: list[Kosten] = []

    def _bewaar_kosten(teller: Any) -> None:
        from iso_audit.classification.findings import PRIJZEN_GRONDSLAG, PRIJZEN_PEILDATUM

        kosten_uit.append(
            Kosten(
                usd=teller.kosten_usd(),
                model=teller.model,
                peildatum=PRIJZEN_PEILDATUM,
                grondslag=PRIJZEN_GRONDSLAG,
                calls=teller.calls,
                fouten=teller.fouten,
            )
        )

    try:
        pipeline.run_audit(
            norm,
            no_review=True,
            chapter=chapter,
            mode=AutonoomMode(conn=conn),
            sources=sources,
            alleen_ingest=alleen_ingest,
            op_kosten=_bewaar_kosten,
        )
    finally:
        pijplijn_logger.removeHandler(handler)
        pijplijn_logger.setLevel(vorig_niveau)
    return kosten_uit[-1] if kosten_uit else None


def draft_from_db(*, norm: str, norms_dir: str, language: str, top_n: int) -> list[Finding]:
    """Exporteer DB-findings en draaf de kop-NC's (na een live run)."""
    ruw = export_db_findings(norm=norm, norms_dir=norms_dir)
    norm_db = laad_norm_db(norms_dir)
    return draft_findings(ruw, norm_db=norm_db, language=language, top_n=top_n)
