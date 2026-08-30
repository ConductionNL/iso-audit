"""Een nieuwe audit erft geen bevindingen van een vorige.

Op 2026-08-30 leverde een schone audit 247 bevindingen op terwijl de run er zes had opgeleverd.
De andere 241 kwamen uit de gedeelde `bevindingen`-tabel: die is niet per audit gescheiden, dus
elke audit exporteert alles wat er ooit in is beland. Archiveren van de vorige audit hielp niet —
de bevindingen zitten in de database, niet in de auditmap.

Gevolg: "schoon beginnen" bestond niet. Een run die zes bevindingen oplevert, toont er
tweehonderdzevenenveertig, en welke daarvan van déze audit zijn, is niet te zien.

De kolom `audit_id` lost dat op. Rijen van vóór deze wijziging hebben hem niet; die blijven
zichtbaar voor de audit die ze heeft aangemaakt, en anders voor niemand — stil laten verdwijnen
zou bewijs weggooien, en aan iedereen tonen is precies het probleem dat we oplossen.
"""

from __future__ import annotations

import sqlite3

import pytest

from iso_audit.store import initialiseer


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    initialiseer(c)
    return c


def _bevinding(c: sqlite3.Connection, doc: str, audit: str | None, clausule: str = "A.5.1") -> None:
    c.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "beschrijving, document_naam, classified_at, audit_id) VALUES (?,?,?,?,?,?,?,?,?)",
        (doc, "Drive", clausule, "27001", "NC", "iets", doc, "2026-08-30T12:00:00Z", audit),
    )


def test_de_kolom_bestaat(conn: sqlite3.Connection) -> None:
    kolommen = {r[1] for r in conn.execute("PRAGMA table_info(bevindingen)")}
    assert "audit_id" in kolommen


def test_een_audit_ziet_alleen_zijn_eigen_bevindingen(conn: sqlite3.Connection) -> None:
    from iso_audit.classification.findings import _bevindingen_query

    _bevinding(conn, "d1", "27001-2026-H4")
    _bevinding(conn, "d2", "27001-2026-Q4")
    query, waarden = _bevindingen_query("27001", audit_id="27001-2026-H4")
    gevonden = {r[0] for r in conn.execute(query.replace("SELECT *", "SELECT doc_id"), waarden)}
    assert gevonden == {"d1"}


def test_zonder_audit_id_komt_alles_mee(conn: sqlite3.Connection) -> None:
    """Rapportage over de hele database blijft mogelijk; alleen de audit-export filtert."""
    from iso_audit.classification.findings import _bevindingen_query

    _bevinding(conn, "d1", "27001-2026-H4")
    _bevinding(conn, "d2", "27001-2026-Q4")
    query, waarden = _bevindingen_query("27001")
    gevonden = {r[0] for r in conn.execute(query.replace("SELECT *", "SELECT doc_id"), waarden)}
    assert gevonden == {"d1", "d2"}


def test_oude_rijen_zonder_audit_id_horen_bij_de_audit_die_ze_maakte(
    conn: sqlite3.Connection,
) -> None:
    """Stil laten verdwijnen zou bewijs weggooien; aan iedereen tonen is het probleem zelf.

    De migratie schrijft het id van de audit die destijds liep; lukt dat niet, dan blijft de rij
    zonder id en is hij alleen zonder filter zichtbaar.
    """
    from iso_audit.classification.findings import _bevindingen_query

    _bevinding(conn, "oud", None)
    query, waarden = _bevindingen_query("27001", audit_id="27001-2026-H4")
    gevonden = {r[0] for r in conn.execute(query.replace("SELECT *", "SELECT doc_id"), waarden)}
    assert gevonden == set(), "een rij zonder audit hoort niet bij een nieuwe audit"


def test_het_hoofdstukfilter_werkt_samen_met_het_auditfilter(conn: sqlite3.Connection) -> None:
    from iso_audit.classification.findings import _bevindingen_query

    _bevinding(conn, "d1", "27001-2026-H4", clausule="A.5.1")
    _bevinding(conn, "d2", "27001-2026-H4", clausule="4.1")
    query, waarden = _bevindingen_query("27001", hoofdstuk="A.5", audit_id="27001-2026-H4")
    gevonden = {r[0] for r in conn.execute(query.replace("SELECT *", "SELECT doc_id"), waarden)}
    assert gevonden == {"d1"}
