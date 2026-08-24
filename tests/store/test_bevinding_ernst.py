"""`ernst` en `onbruikbaar` moeten de database halen.

Een NC met `ernst: "major"` betekent dat het proces als geheel afwezig of gebroken is en dat
certificering in gevaar komt; `minor` is een op zichzelf staande misser. Dat onderscheid bepaalt
wat het management moet beslissen, en het is het eerste dat een memo van drie A4 nodig heeft.

`onbruikbaar` markeert een oordeel zonder beschrijving én zonder onderbouwing. Die rijen worden
niet weggegooid — dát het model ze zo teruggaf is zelf een gegeven over de classificatie — maar
ze mogen niet meetellen als bevinding. In de run van 2026-08-24 waren dat er 55.

Zonder kolommen vallen beide bij het opslaan weg, en dan is de prompt wel aangepast maar het
resultaat niet: een verbetering die alleen in de logs bestaat.
"""

from __future__ import annotations

import sqlite3

from iso_audit.classification.findings import _upsert_bevindingen
from iso_audit.store import initialiseer

_BEVINDING = {
    "_doc_id": "d1",
    "herkomst": "Drive",
    "clausule": "8.24",
    "clausule_titel": "Gebruik van cryptografie",
    "document_naam": "Beleid.docx",
    "classificatie": "NC",
    "beschrijving": "Geen cryptografiebeleid aangetroffen.",
    "onderbouwing": "27001 §8.24 eist regels voor het gebruik van cryptografie.",
    "pre_classificatie": None,
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    return conn


def test_ernst_wordt_bewaard() -> None:
    conn = _conn()
    _upsert_bevindingen(conn, [{**_BEVINDING, "ernst": "major", "onbruikbaar": False}], "27001")
    rij = conn.execute("SELECT ernst FROM bevindingen").fetchone()
    assert rij[0] == "major"


def test_ernst_mag_leeg_zijn_bij_een_ofi() -> None:
    """Alleen een NC heeft een ernst; bij OFI en positief hoort daar niets te staan."""
    conn = _conn()
    _upsert_bevindingen(
        conn,
        [{**_BEVINDING, "classificatie": "OFI", "ernst": None, "onbruikbaar": False}],
        "27001",
    )
    assert conn.execute("SELECT ernst FROM bevindingen").fetchone()[0] is None


def test_onbruikbaar_wordt_bewaard() -> None:
    conn = _conn()
    _upsert_bevindingen(
        conn,
        [{**_BEVINDING, "beschrijving": "", "onderbouwing": "", "onbruikbaar": True}],
        "27001",
    )
    assert conn.execute("SELECT onbruikbaar FROM bevindingen").fetchone()[0] == 1


def test_een_bestaande_database_krijgt_de_kolommen() -> None:
    """Migratie: `CREATE TABLE IF NOT EXISTS` raakt een bestaande tabel niet aan."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE bevindingen (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id           TEXT NOT NULL,
            herkomst         TEXT NOT NULL,
            clausule_id      TEXT NOT NULL,
            norm             TEXT NOT NULL,
            classificatie    TEXT NOT NULL,
            beschrijving     TEXT,
            onderbouwing     TEXT,
            pre_classificatie TEXT,
            document_naam    TEXT,
            classified_at    TEXT NOT NULL,
            UNIQUE(doc_id, herkomst, clausule_id, norm)
        );
        """
    )
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie,"
        " classified_at) VALUES ('d1', 'Drive', '8.24', '27001', 'NC', '2026-01-01')"
    )
    conn.commit()

    initialiseer(conn)

    kolommen = {r[1] for r in conn.execute("PRAGMA table_info(bevindingen)")}
    assert {"ernst", "onbruikbaar"} <= kolommen
    assert conn.execute("SELECT COUNT(*) FROM bevindingen").fetchone()[0] == 1
