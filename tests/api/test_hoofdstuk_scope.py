"""Een run op hoofdstuk 4 levert bevindingen uit hoofdstuk 4, niet uit de hele norm.

Gemeten op 2026-08-29: een run met `chapter='4'` op ISO 27001 leverde **303 bevindingen** met
clausules als 10.2, 9.1 en A.8.16. Het run-record zei netjes `hoofdstuk: 4`, en de pipeline
classificeerde ook alleen hoofdstuk 4 — maar de export naar de werkset filterde alleen op norm.
Alles wat ooit in de database was gekomen, kwam mee.

Dat is dezelfde fout waar `RunStartRequest` al tegen waarschuwt bij de norm: *"een run waarvan de
scope niet meer uit de audit volgt — en dan liegt de memo over wat er getoetst is"*. Voor het
hoofdstuk gold die redenering nog niet.

Zonder hoofdstuk verandert er niets: dan is de scope de hele norm en hoort alles erin.
"""

from __future__ import annotations

import sqlite3

import pytest

from iso_audit.classification.findings import _bevindingen_query


def _kolommen(query: str) -> str:
    return query.lower()


def test_zonder_hoofdstuk_blijft_de_query_op_norm_filteren() -> None:
    query, waarden = _bevindingen_query("27001")
    assert "clausule_id like" not in _kolommen(query)
    assert "27001" in waarden


def test_met_hoofdstuk_filtert_de_query_op_clausule() -> None:
    query, waarden = _bevindingen_query("27001", hoofdstuk="4")
    assert "clausule_id like" in _kolommen(query)
    assert "4.%" in waarden


def test_het_hoofdstuk_matcht_ook_de_clausule_zelf() -> None:
    """Een bevinding op precies "4" hoort bij hoofdstuk 4."""
    _, waarden = _bevindingen_query("27001", hoofdstuk="4")
    assert "4" in waarden


def test_bijlage_a_valt_buiten_een_managementhoofdstuk() -> None:
    """A.8.16 is geen hoofdstuk 8: de prefix maakt het een maatregel uit Bijlage A."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bevindingen (clausule_id TEXT, norm TEXT)")
    conn.executemany(
        "INSERT INTO bevindingen VALUES (?,?)",
        [("8.1", "27001"), ("8.3", "27001"), ("A.8.16", "27001"), ("A.8.2", "27001")],
    )
    query, waarden = _bevindingen_query("27001", hoofdstuk="8")
    gevonden = {
        r[0] for r in conn.execute(query.replace("SELECT *", "SELECT clausule_id"), waarden)
    }
    assert gevonden == {"8.1", "8.3"}, f"Bijlage A hoort er niet bij: {gevonden}"


def test_een_bijlage_a_hoofdstuk_kan_ook(tmp_path: object) -> None:
    """Wie A.8 wil toetsen, typt A.8 — en krijgt dan alleen de maatregelen."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bevindingen (clausule_id TEXT, norm TEXT)")
    conn.executemany(
        "INSERT INTO bevindingen VALUES (?,?)",
        [("8.1", "27001"), ("A.8.16", "27001"), ("A.5.1", "27001")],
    )
    query, waarden = _bevindingen_query("27001", hoofdstuk="A.8")
    gevonden = {
        r[0] for r in conn.execute(query.replace("SELECT *", "SELECT clausule_id"), waarden)
    }
    assert gevonden == {"A.8.16"}


@pytest.mark.parametrize("hoofdstuk", ["", None])
def test_een_leeg_hoofdstuk_telt_als_geen_filter(hoofdstuk: str | None) -> None:
    query, _ = _bevindingen_query("27001", hoofdstuk=hoofdstuk)
    assert "clausule_id like" not in _kolommen(query)


# --- Bijlage A als eigen scope ----------------------------------------------


def _db_met(clausules: list[str]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE bevindingen (clausule_id TEXT, norm TEXT, herkomst TEXT)")
    conn.executemany(
        "INSERT INTO bevindingen VALUES (?,?,?)", [(c, "27001", "Drive") for c in clausules]
    )
    return conn


def _scope(conn: sqlite3.Connection, hoofdstuk: str | None) -> set[str]:
    query, waarden = _bevindingen_query("27001", hoofdstuk=hoofdstuk)
    sql = query.replace("SELECT *", "SELECT clausule_id")
    return {r[0] for r in conn.execute(sql, waarden)}


_ALLES = ["4.1", "4.4", "8.1", "8.3", "9.2", "A.5.1", "A.5.29", "A.8.1", "A.8.16", "A.8.24"]


def test_de_hele_bijlage_a_als_scope() -> None:
    """`A` toetst alle maatregelen en geen enkele managementclausule."""
    assert _scope(_db_met(_ALLES), "A") == {"A.5.1", "A.5.29", "A.8.1", "A.8.16", "A.8.24"}


def test_een_thema_uit_bijlage_a() -> None:
    """A.5 is "Organisatorische beheersmaatregelen" — 37 stuks in de norm."""
    assert _scope(_db_met(_ALLES), "A.5") == {"A.5.1", "A.5.29"}


def test_de_technologische_maatregelen() -> None:
    """A.8 is "Technologische beheersmaatregelen"; §8.1 t/m §8.3 zijn dat níet."""
    assert _scope(_db_met(_ALLES), "A.8") == {"A.8.1", "A.8.16", "A.8.24"}


def test_hoofdstuk_acht_en_bijlage_acht_zijn_niet_hetzelfde() -> None:
    """De kern van de A-prefix: §8 is Uitvoering, A.8 zijn de technologische maatregelen.

    Zonder dit onderscheid zou een run op "hoofdstuk 8" 34 maatregelen meenemen die er niet bij
    horen — en zou de memo claimen dat de uitvoering is getoetst terwijl er encryptie-bevindingen
    in staan.
    """
    conn = _db_met(_ALLES)
    assert _scope(conn, "8") == {"8.1", "8.3"}
    assert _scope(conn, "A.8") == {"A.8.1", "A.8.16", "A.8.24"}
    assert not _scope(conn, "8") & _scope(conn, "A.8")


def test_een_losse_maatregel_als_scope() -> None:
    """Wie alleen A.8.24 wil toetsen, krijgt niet heel A.8."""
    assert _scope(_db_met(_ALLES), "A.8.24") == {"A.8.24"}


def test_zonder_scope_komt_alles_mee() -> None:
    """Geen hoofdstuk betekent de hele norm: 26 managementclausules plus 93 maatregelen."""
    assert _scope(_db_met(_ALLES), None) == set(_ALLES)


def test_de_scope_dekt_samen_de_hele_norm() -> None:
    """Managementclausules en Bijlage A samen zijn de norm; niets valt tussen wal en schip."""
    conn = _db_met(_ALLES)
    management: set[str] = set()
    for hoofdstuk in ("4", "5", "6", "7", "8", "9", "10"):
        management |= _scope(conn, hoofdstuk)
    assert management | _scope(conn, "A") == set(_ALLES)
