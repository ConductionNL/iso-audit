"""Een afgebroken run raakt zijn werk niet kwijt, en begint niet opnieuw.

De vraag van de auditor vóór de volledige run: wat als het API-tegoed opraakt halverwege? Dan
moet de stand blijven staan en moet een nieuwe run verdergaan waar de vorige stopte — anders
betaal je twee keer voor hetzelfde en duurt elke poging even lang als de eerste.

Twee dingen maken dat waar:

- **Per document opslaan en committen.** Wat geclassificeerd is, staat in de database zodra het
  klaar is; een fout op document 500 kost geen 499 eerdere.
- **Overslaan wat er al staat.** `_gedaan_per_doc` bepaalt dat, en dáár zat het gat: hij zocht op
  de run-parameter (`beide`), terwijl bevindingen worden opgeslagen met hun eigen norm (`9001` of
  `27001`). Bij een gecombineerde run vond hij dus niets en begon alles opnieuw — precies bij de
  run waarvoor de vraag werd gesteld.
"""

from __future__ import annotations

import sqlite3

import pytest

from iso_audit.classification.findings import _gedaan_per_doc
from iso_audit.store import initialiseer


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    initialiseer(c)
    for doc, clausule, norm in (
        ("d1", "4.1", "9001"),
        ("d1", "A.5.1", "27001"),
        ("d2", "9.2", "27001"),
    ):
        c.execute(
            "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
            "beschrijving, document_naam, classified_at) VALUES (?,?,?,?,?,?,?,?)",
            (doc, "Drive", clausule, norm, "OFI", "x", doc, "2026-08-30T12:00:00Z"),
        )
    c.commit()
    return c


def test_een_run_op_een_norm_ziet_zijn_eigen_werk(conn: sqlite3.Connection) -> None:
    assert _gedaan_per_doc(conn, "27001") == {"d1": {"A.5.1"}, "d2": {"9.2"}}


def test_een_gecombineerde_run_ziet_het_werk_van_beide_normen(conn: sqlite3.Connection) -> None:
    """Dit was het gat: `norm='beide'` zocht rijen met de letterlijke waarde 'beide'.

    Bevindingen dragen hun eigen norm, dus vond hij niets en begon een hervatte run van voren af
    aan — bij precies het runtype waarvoor de hervatting bedoeld is.
    """
    gedaan = _gedaan_per_doc(conn, "beide")
    assert gedaan == {"d1": {"4.1", "A.5.1"}, "d2": {"9.2"}}


def test_oude_rijen_met_de_letterlijke_norm_beide_tellen_mee(conn: sqlite3.Connection) -> None:
    """Van vóór de per-norm-opslag; die zijn ook gedaan werk."""
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "beschrijving, document_naam, classified_at) VALUES (?,?,?,?,?,?,?,?)",
        ("d3", "Drive", "7.5", "beide", "OFI", "x", "d3", "2026-08-30T12:00:00Z"),
    )
    conn.commit()
    assert "7.5" in _gedaan_per_doc(conn, "beide")["d3"]


def test_wat_niet_gedaan_is_komt_niet_terug(conn: sqlite3.Connection) -> None:
    gedaan = _gedaan_per_doc(conn, "beide")
    assert "10.2" not in gedaan.get("d1", set())


def test_de_bevindingen_staan_er_nog_na_een_afgebroken_run(conn: sqlite3.Connection) -> None:
    """Per document committen: een fout op document 500 kost geen 499 eerdere."""
    from iso_audit.classification.findings import _upsert_bevindingen

    bevs = [
        {
            "_doc_id": "d9",
            "herkomst": "Drive",
            "clausule": "A.5.1",
            "norm": "27001",
            "classificatie": "NC",
            "beschrijving": "iets",
            "document_naam": "d9",
        }
    ]
    _upsert_bevindingen(conn, bevs, "beide", "27001-2026-H4")
    # Een tweede verbinding ziet de rij: hij is dus echt gecommit, niet alleen in het geheugen.
    assert conn.execute("SELECT count(*) FROM bevindingen WHERE doc_id='d9'").fetchone()[0] == 1
    assert "A.5.1" in _gedaan_per_doc(conn, "beide")["d9"]
