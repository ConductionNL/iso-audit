"""Een bevinding erft de norm van zijn koppeling, niet die van de run.

`clause_matches` weet sinds de per-norm-koppeling precies uit welke norm een match komt — 3.067
voor 9001 en 1.332 voor 27001 in de run van 2026-08-25. `bevindingen` kreeg nog steeds `beide`,
de run-parameter, en daardoor moest `_resolve_standard()` achteraf raden.

Met een complete norm-DB raadt die goed voor de 103 clausulenummers die maar in één norm
bestaan. Voor de achttien die in beide bestaan kán hij niet kiezen en valt hij terug op 9001 —
30 bevindingen in die run. Dat is precies het gat dat de match wél kan dichten.
"""

from __future__ import annotations

from typing import Any

from iso_audit.classification.findings import bouw_bevindingen


def _doc(clausule_normen: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "id": "d1",
        "naam": "Beleid.docx",
        "herkomst": "Drive",
        "clausule_normen": clausule_normen,
    }


def _res(clausule: str) -> dict[str, Any]:
    return {
        "clausule": clausule,
        "classificatie": "NC",
        "beschrijving": "iets",
        "onderbouwing": "iets",
    }


def test_de_bevinding_krijgt_de_norm_van_de_match() -> None:
    bevs = bouw_bevindingen(
        doc=_doc([("7.5", "9001")]),
        clausules=["7.5"],
        resultaten=[_res("7.5")],
        clausule_titels={},
    )
    assert bevs[0]["norm"] == "9001"


def test_hetzelfde_nummer_uit_twee_normen_geeft_twee_bevindingen() -> None:
    """§7.5 is in 9001 "Gedocumenteerde informatie" en in 27001 iets heel anders.

    Eén bevinding zou betekenen dat het oordeel over de ene norm voor de andere doorgaat.
    """
    bevs = bouw_bevindingen(
        doc=_doc([("7.5", "9001"), ("7.5", "27001")]),
        clausules=["7.5"],
        resultaten=[_res("7.5")],
        clausule_titels={},
    )
    assert sorted(b["norm"] for b in bevs) == ["27001", "9001"]


def test_zonder_koppelingnorm_blijft_het_veld_leeg() -> None:
    """Dan beslist de aanroeper, zoals voorheen — geen geraden norm."""
    bevs = bouw_bevindingen(
        doc={"id": "d1", "naam": "B.docx", "herkomst": "Drive"},
        clausules=["8.24"],
        resultaten=[_res("8.24")],
        clausule_titels={},
    )
    assert bevs[0].get("norm") in (None, "")


def test_de_opslag_gebruikt_de_norm_van_de_bevinding() -> None:
    """De run-parameter is `beide`; die mag de norm van de match niet overschrijven."""
    import sqlite3

    from iso_audit.classification.findings import _upsert_bevindingen
    from iso_audit.store import initialiseer

    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    _upsert_bevindingen(
        conn,
        [
            {
                "_doc_id": "d1",
                "herkomst": "Drive",
                "clausule": "7.5",
                "norm": "9001",
                "classificatie": "NC",
                "document_naam": "B.docx",
                "beschrijving": "x",
                "onderbouwing": "y",
            }
        ],
        "beide",
    )
    assert conn.execute("SELECT norm FROM bevindingen").fetchone()[0] == "9001"


def test_zonder_eigen_norm_valt_de_opslag_terug_op_de_run() -> None:
    """Bestaande paden zonder koppelingnorm (Miro, opvolgpunten) blijven werken."""
    import sqlite3

    from iso_audit.classification.findings import _upsert_bevindingen
    from iso_audit.store import initialiseer

    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    _upsert_bevindingen(
        conn,
        [
            {
                "_doc_id": "d1",
                "herkomst": "Miro",
                "clausule": "8.24",
                "classificatie": "OFI",
                "document_naam": "notitie",
                "beschrijving": "x",
                "onderbouwing": "y",
            }
        ],
        "27001",
    )
    assert conn.execute("SELECT norm FROM bevindingen").fetchone()[0] == "27001"
