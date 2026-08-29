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
    gevonden = {r[0] for r in conn.execute(query.replace("SELECT *", "SELECT clausule_id"), waarden)}
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
    gevonden = {r[0] for r in conn.execute(query.replace("SELECT *", "SELECT clausule_id"), waarden)}
    assert gevonden == {"A.8.16"}


@pytest.mark.parametrize("hoofdstuk", ["", None])
def test_een_leeg_hoofdstuk_telt_als_geen_filter(hoofdstuk: str | None) -> None:
    query, _ = _bevindingen_query("27001", hoofdstuk=hoofdstuk)
    assert "clausule_id like" not in _kolommen(query)
