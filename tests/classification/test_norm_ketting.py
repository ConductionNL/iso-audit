"""De norm van de koppeling moet de hele keten door tot in de review.

Gemeten in de run van 2026-08-25 21:40: `clause_matches` had 3.067 koppelingen op 9001 en 1.332
op 27001, maar `bevindingen.norm` stond op `beide` en `review_adviezen.norm` was leeg. De review
groepeerde daardoor op een lege norm — in het log stond letterlijk "op  §9.3" met een gat waar de
norm hoort.

Twee gaten, allebei alleen zichtbaar in een echte run:

1. `_classify_drive` bouwde een minimale doc-dict met alleen id, naam en herkomst; daar viel
   `clausule_normen` weg.
2. De terugleesquery filterde op de run-norm (`beide`), dus per-norm opgeslagen rijen zou hij
   niet eens vinden.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from iso_audit.classification.findings import _bevindingen_voor_norm, bouw_bevindingen
from iso_audit.store import initialiseer


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialiseer(conn)
    return conn


def _schrijf(conn: sqlite3.Connection, norm: str, clausule: str = "8.24") -> None:
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie,"
        " document_naam, beschrijving, onderbouwing, classified_at)"
        " VALUES ('d1','Drive',?,?,'NC','B.docx','x','y','2026-01-01')",
        (clausule, norm),
    )
    conn.commit()


def test_beide_haalt_de_rijen_van_allebei_de_normen_op() -> None:
    """Anders levert een gecombineerde run nul bevindingen op voor review en memo."""
    conn = _conn()
    _schrijf(conn, "9001", "7.5")
    _schrijf(conn, "27001", "8.24")

    rijen = _bevindingen_voor_norm(conn, "beide")

    assert sorted(r["norm"] for r in rijen) == ["27001", "9001"]


def test_oude_rijen_met_beide_gaan_ook_mee() -> None:
    """Databases van vóór de per-norm-opslag mogen niet stil leeg raken."""
    conn = _conn()
    _schrijf(conn, "beide")
    assert len(_bevindingen_voor_norm(conn, "beide")) == 1


def test_een_enkele_norm_haalt_alleen_die_norm() -> None:
    conn = _conn()
    _schrijf(conn, "9001", "7.5")
    _schrijf(conn, "27001", "8.24")
    assert [r["norm"] for r in _bevindingen_voor_norm(conn, "9001")] == ["9001"]


def test_de_doc_dict_naar_bouw_bevindingen_houdt_de_koppelingnorm() -> None:
    """Het gat dat de run blootlegde: een minimale dict laat `clausule_normen` vallen."""
    doc: dict[str, Any] = {
        "id": "d1",
        "naam": "B.docx",
        "herkomst": "Drive",
        "clausule_normen": [("7.5", "9001")],
    }
    bevs = bouw_bevindingen(
        doc=doc,
        clausules=["7.5"],
        resultaten=[
            {"clausule": "7.5", "classificatie": "NC", "beschrijving": "x", "onderbouwing": "y"}
        ],
        clausule_titels={},
    )
    assert bevs[0]["norm"] == "9001"


def test_de_teruggegeven_bevinding_draagt_norm_en_onbruikbaar() -> None:
    """De review groepeert op `clausule_id` + `norm` en filtert op `onbruikbaar`.

    Ontbraken die velden, dan groepeerde hij op een lege norm — in het log van 2026-08-25
    stond "op  §9.3" met een gat waar de norm hoort — en telden lege oordelen gewoon mee.
    """
    import inspect

    from iso_audit.classification import findings

    bron = inspect.getsource(findings.classificeer_alle_bevindingen)
    for veld in ('"norm": r["norm"]', '"clausule_id": r["clausule_id"]', '"onbruikbaar"'):
        assert veld in bron, f"veld ontbreekt in de teruggegeven bevinding: {veld}"
