"""Het review-advies wordt bewaard, zodat de memo erbij kan.

De review draait in de pipeline en de memo wordt later gebouwd, mogelijk in een ander proces.
Zonder opslag zou de kernzin en de actietabel alleen in de trail staan — leesbaar voor een mens
die zoekt, onbruikbaar voor de memo-bouwer.

Eén rij per (norm, clausule): de review oordeelt per clausule, niet per bevinding. Een tweede
run overschrijft het advies van de eerste — dat is geen verlies, want het ruwe antwoord met
tijdstempel blijft in `assistent_vragen` staan.
"""

from __future__ import annotations

import sqlite3

from iso_audit.store import bewaar_review_advies, initialiseer, review_adviezen


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    return conn


def test_een_advies_wordt_bewaard_en_teruggelezen() -> None:
    conn = _conn()
    bewaar_review_advies(
        conn,
        norm="27001",
        clausule="8.14",
        advies="bevestigen",
        voorgestelde_klasse="NC",
        ernst="minor",
        kern="Geen getest continuïteitsplan.",
        reden="Volgens Plan.docx.",
        acties=[{"wat": "BCM-plan opstellen", "wie": "IT-lead", "uiterlijk": "2026-Q3"}],
    )

    alles = review_adviezen(conn)

    assert list(alles) == [("27001", "8.14")]
    rij = alles[("27001", "8.14")]
    assert rij["kern"] == "Geen getest continuïteitsplan."
    assert rij["acties"][0]["wie"] == "IT-lead"


def test_een_tweede_run_overschrijft_het_advies() -> None:
    """Het ruwe antwoord blijft in de trail; hier staat de laatste stand."""
    conn = _conn()
    for kern in ("eerste", "tweede"):
        bewaar_review_advies(
            conn, norm="27001", clausule="8.14", advies="bevestigen", kern=kern, reden="r"
        )

    alles = review_adviezen(conn)
    assert len(alles) == 1
    assert alles[("27001", "8.14")]["kern"] == "tweede"


def test_dezelfde_clausule_in_twee_normen_blijft_gescheiden() -> None:
    conn = _conn()
    for norm in ("9001", "27001"):
        bewaar_review_advies(
            conn, norm=norm, clausule="7.5", advies="bevestigen", kern=norm, reden="r"
        )

    alles = review_adviezen(conn)
    assert alles[("9001", "7.5")]["kern"] == "9001"
    assert alles[("27001", "7.5")]["kern"] == "27001"


def test_zonder_acties_komt_er_een_lege_lijst_terug() -> None:
    conn = _conn()
    bewaar_review_advies(conn, norm="27001", clausule="5.1", advies="verlagen", kern="k", reden="r")
    assert review_adviezen(conn)[("27001", "5.1")]["acties"] == []
