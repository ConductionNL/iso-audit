"""Tests voor `iso_audit.interviewvoorstel` — vragen die herleidbaar zijn, en geen namen.

De vorm van deze module volgt uit een meting: van de 481 bewijslast-items in
`data/normteksten` beschrijven er ongeveer drie een waarneming. De catalogus is
artefact-gericht, dus de vraag is omgedraaid — niet "wat kan een mens bevestigen" maar "waar is
dit artefact".
"""

from __future__ import annotations

import sqlite3

import pytest

from iso_audit import interviewvoorstel as iv
from iso_audit.store import initialiseer, now


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    initialiseer(c)
    return c


def _koppel(c: sqlite3.Connection, clausule: str, norm: str = "27001") -> None:
    c.execute(
        "INSERT INTO clause_matches (doc_id, herkomst, clausule_id, norm) VALUES (?,?,?,?)",
        ("d1", "Drive", clausule, norm),
    )
    c.execute(
        "INSERT INTO documents (id, naam, tekst, herkomst, ingested_at) VALUES (?,?,?,?,?)",
        ("d1", "Beleid.docx", "x", "Drive", now()),
    )
    c.commit()


def test_elke_vraag_is_herleidbaar_naar_een_bewijslast_item(conn: sqlite3.Connection) -> None:
    """Een vraag in een auditdossier die niemand kan herleiden, is precies wat dit tool weert."""
    voorstellen = iv.stel_voor(conn, "27001")

    assert voorstellen, "een leeg landschap levert voorstellen voor elke clausule"
    for voorstel in voorstellen:
        for vraag in voorstel.vragen:
            assert vraag.bewijslast
            assert vraag.bewijslast.rstrip(".") in vraag.tekst


def test_gedekte_clausule_levert_geen_voorstel(conn: sqlite3.Connection) -> None:
    """Waar documentbewijs is, hoeft geen gesprek."""
    zonder = {v.clausule_id for v in iv.stel_voor(conn, "27001")}
    gedekt = sorted(zonder)[0]

    _koppel(conn, gedekt)

    assert gedekt not in {v.clausule_id for v in iv.stel_voor(conn, "27001")}


def test_geen_verzonnen_persoonsnaam(conn: sqlite3.Connection) -> None:
    """Het tool kent geen personen en hoort ze niet te raden.

    Een verzonnen naam in een auditplanning ziet eruit als een afspraak die iemand heeft
    gemaakt — erger dan een lege.
    """
    for voorstel in iv.stel_voor(conn, "27001"):
        assert voorstel.rol == iv.ROL_ONBEKEND
        assert "@" not in voorstel.rol


def test_rollen_tabel_is_leeg_opgeleverd() -> None:
    """Bewust leeg: de rol invullen is organisatiekennis, geen implementatiekeuze."""
    assert iv.ROLLEN == {}


def test_vraag_vraagt_naar_de_vindplaats_en_niet_naar_een_mening() -> None:
    vraag = iv._vraag_voor("Notulen directiebeoordeling ondertekend door topmanagement")

    assert "Waar is" in vraag.tekst
    assert "waarom niet" in vraag.tekst
    for mening in ("vindt u", "denkt u", "bent u van mening"):
        assert mening not in vraag.tekst.lower()


def test_clausule_zonder_bewijslast_levert_geen_voorstel(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Een gesprek zonder onderwerp is erger dan geen gesprek."""
    monkeypatch.setattr(iv, "ongedekte_clausules", lambda *a: ["5.1"])
    monkeypatch.setattr(iv.normteksten, "lookup", lambda *a: {"titel": "T", "bewijslast": []})

    assert iv.stel_voor(conn, "27001") == []


def test_record_vorm_is_stabiel(conn: sqlite3.Connection) -> None:
    """Deze vorm gaat naar de UI en straks naar de trail."""
    record = iv.stel_voor(conn, "9001")[0].als_record()

    assert set(record) == {"norm", "clausule_id", "titel", "rol", "vragen"}
    assert set(record["vragen"][0]) == {"tekst", "bewijslast"}


def test_titel_komt_uit_de_clause_map(conn: sqlite3.Connection) -> None:
    """`normteksten` heeft geen `titel` per clausule — nagemeten leeg voor élke 27001-clausule.

    Een voorstel dat alleen "5.28" zegt, laat de auditor eerst opzoeken waar het over gaat.
    """
    voorstellen = {v.clausule_id: v for v in iv.stel_voor(conn, "27001")}

    assert voorstellen["5.28"].titel == "Verzamelen van bewijs"
