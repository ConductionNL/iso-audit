"""Tests voor de clausule-agent — voorbereiden mag, oordelen niet.

De grens is de hele change: zodra er een voorgestelde klasse in het antwoord zit, bevestigt de
auditor in plaats van te beoordelen, en dan is de onafhankelijkheid van de auditor een
formaliteit.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from iso_audit.assistent import clausule as ca
from iso_audit.assistent.vraag import AntwoordOnverifieerbaarError
from iso_audit.store import initialiseer, now


class _Blok:
    def __init__(self, tekst: str) -> None:
        self.type = "text"
        self.text = tekst


class _Usage:
    input_tokens = 800
    output_tokens = 300
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0


class _Client:
    def __init__(self, antwoord: Any, stop_reason: str = "end_turn") -> None:
        self._tekst = antwoord if isinstance(antwoord, str) else json.dumps(antwoord)
        self._stop = stop_reason
        self.verzoeken: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kw: Any) -> Any:
        self.verzoeken.append(kw)
        resp = type("R", (), {})()
        resp.content = [_Blok(self._tekst)]
        resp.stop_reason = self._stop
        resp.usage = _Usage()
        return resp


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    initialiseer(c)
    c.execute(
        "INSERT INTO documents (id, naam, tekst, herkomst, ingested_at) VALUES (?,?,?,?,?)",
        ("d1", "MT-verslag 2026-03.docx", "directiebeoordeling", "Drive", now()),
    )
    c.execute(
        "INSERT INTO clause_matches (doc_id, herkomst, clausule_id, norm) VALUES (?,?,?,?)",
        ("d1", "Drive", "5.1", "9001"),
    )
    c.commit()
    return c


def _bewijslast(norm: str = "9001", clausule: str = "5.1") -> list[str]:
    from iso_audit.data import normteksten

    return [str(b) for b in (normteksten.lookup(norm, clausule) or {}).get("bewijslast", [])]


def test_beeld_koppelt_bewijslast_aan_een_bron(conn: sqlite3.Connection) -> None:
    items = _bewijslast()
    client = _Client(
        {
            "bewijs_aanwezig": [
                {"bewijslast": items[0], "bron": "d1", "toelichting": "MT-verslag dekt dit"}
            ],
            "bewijs_ontbreekt": [{"bewijslast": items[1], "toelichting": "niet gevonden"}],
            "tegenspraak": [],
            "waarom_nu": "de helft van de bewijslast ontbreekt",
        }
    )

    beeld = ca.bekijk(conn, "5.1", norm="9001", client=client)

    assert beeld.bewijs_aanwezig[0]["bron"] == "d1"
    assert beeld.titel
    assert 0 < beeld.dekkingsgraad < 1
    assert beeld.usd > 0


def test_een_voorstel_veld_wordt_geweigerd(conn: sqlite3.Connection) -> None:
    """De grens van deze change, en de test die faalt als iemand hem oprekt."""
    items = _bewijslast()
    client = _Client(
        {
            "bewijs_aanwezig": [{"bewijslast": items[0], "bron": "d1", "toelichting": "x"}],
            "bewijs_ontbreekt": [],
            "tegenspraak": [],
            "waarom_nu": "x",
            "voorstel": "NC",
        }
    )

    with pytest.raises(AntwoordOnverifieerbaarError, match="verboden veld"):
        ca.bekijk(conn, "5.1", norm="9001", client=client)


@pytest.mark.parametrize("veld", ["classificatie", "oordeel", "advies", "aanbeveling", "triage"])
def test_elk_oordeelsveld_wordt_geweigerd(veld: str) -> None:
    assert ca.verboden_velden({veld: "x"}) == [veld]
    assert ca.verboden_velden({"bewijs_aanwezig": []}) == []


def test_verzonnen_bewijslast_wordt_geweigerd(conn: sqlite3.Connection) -> None:
    """Een eis die niet in de norm staat, hoort niet in een auditdossier."""
    client = _Client(
        {
            "bewijs_aanwezig": [],
            "bewijs_ontbreekt": [{"bewijslast": "Zelfbedachte eis", "toelichting": "x"}],
            "tegenspraak": [],
            "waarom_nu": "x",
        }
    )

    with pytest.raises(AntwoordOnverifieerbaarError, match="niet in de norm staat"):
        ca.bekijk(conn, "5.1", norm="9001", client=client)


def test_verzonnen_bron_wordt_geweigerd(conn: sqlite3.Connection) -> None:
    items = _bewijslast()
    client = _Client(
        {
            "bewijs_aanwezig": [
                {"bewijslast": items[0], "bron": "d-verzonnen", "toelichting": "x"}
            ],
            "bewijs_ontbreekt": [],
            "tegenspraak": [],
            "waarom_nu": "x",
        }
    )

    with pytest.raises(AntwoordOnverifieerbaarError, match="niet zijn meegegeven"):
        ca.bekijk(conn, "5.1", norm="9001", client=client)


def test_tegenspraak_verwijst_ook_naar_meegegeven_bronnen(conn: sqlite3.Connection) -> None:
    client = _Client(
        {
            "bewijs_aanwezig": [],
            "bewijs_ontbreekt": [],
            "tegenspraak": [{"waarover": "x", "bronnen": ["d1", "d-verzonnen"]}],
            "waarom_nu": "x",
        }
    )

    with pytest.raises(AntwoordOnverifieerbaarError, match="d-verzonnen"):
        ca.bekijk(conn, "5.1", norm="9001", client=client)


def test_antwoord_zonder_json_is_een_storing(conn: sqlite3.Connection) -> None:
    with pytest.raises(AntwoordOnverifieerbaarError, match="geen JSON"):
        ca.bekijk(conn, "5.1", norm="9001", client=_Client("Ik denk dat het wel goed zit."))


def test_afgekapt_antwoord_is_een_storing(conn: sqlite3.Connection) -> None:
    client = _Client({"bewijs_aanwezig": [], "bewijs_ontbreekt": []}, stop_reason="max_tokens")
    with pytest.raises(AntwoordOnverifieerbaarError, match="afgekapt"):
        ca.bekijk(conn, "5.1", norm="9001", client=client)


def test_clausule_zonder_bewijslast_bevraagt_geen_model(conn: sqlite3.Connection) -> None:
    """Een model dat mag bedenken wát de norm verwacht, verzint eisen die er niet staan."""

    class _Weigert:
        messages = None

        def create(self, **kw: Any) -> Any:
            raise AssertionError("er mag geen model bevraagd zijn")

    beeld = ca.bekijk(conn, "0", norm="9001", client=_Weigert())

    assert beeld.bewijs_aanwezig == [] and beeld.bewijs_ontbreekt == []


def test_thinking_staat_uit_en_het_budget_is_gezet(conn: sqlite3.Connection) -> None:
    items = _bewijslast()
    client = _Client(
        {
            "bewijs_aanwezig": [{"bewijslast": items[0], "bron": "d1", "toelichting": "x"}],
            "bewijs_ontbreekt": [],
            "tegenspraak": [],
            "waarom_nu": "x",
        }
    )
    ca.bekijk(conn, "5.1", norm="9001", client=client)

    assert client.verzoeken[0]["thinking"] == {"type": "disabled"}
    assert client.verzoeken[0]["max_tokens"] == ca.MAX_TOKENS


def test_ordening_is_berekend_en_geeft_per_regel_een_reden() -> None:
    """De ordening is een uitspraak over aandacht; berekend zodat hij na te rekenen is."""
    volledig = ca.Clausulebeeld(
        norm="9001",
        clausule_id="4.1",
        titel="Context",
        bewijs_aanwezig=[{"bewijslast": "a", "bron": "d1"}],
    )
    gat = ca.Clausulebeeld(
        norm="9001",
        clausule_id="5.1",
        titel="Leiderschap",
        bewijs_aanwezig=[{"bewijslast": "a", "bron": "d1"}],
        bewijs_ontbreekt=[{"bewijslast": "b"}, {"bewijslast": "c"}],
    )
    strijdig = ca.Clausulebeeld(
        norm="9001",
        clausule_id="9.2",
        titel="Interne audit",
        tegenspraak=[{"waarover": "x", "bronnen": ["d1"]}],
    )

    geordend = ca.orden([volledig, gat, strijdig])

    assert [b.clausule_id for b, _ in geordend] == ["9.2", "5.1", "4.1"]
    assert "tegenspraak" in geordend[0][1]
    assert "2 van 3" in geordend[1][1]
    assert "volledig gedekt" in geordend[2][1]


def test_dekkingsgraad_telt_items_en_geen_rijen() -> None:
    """Het model levert één rij per bron; vijf bronnen voor één eis is nog steeds één eis.

    Gemeten tegen het echte corpus op 2026-08-22: clausule 9.2 meldde "2 van 8 bewijsstukken
    niet gevonden" terwijl de norm er vier kent — vijf rijen voor hetzelfde item.
    """
    beeld = ca.Clausulebeeld(
        norm="9001",
        clausule_id="9.2",
        titel="Interne audit",
        bewijs_aanwezig=[
            {"bewijslast": "Auditplannen en auditverslagen", "bron": f"d{i}"} for i in range(5)
        ]
        + [{"bewijslast": "Kwalificatie auditoren", "bron": "d9"}],
        bewijs_ontbreekt=[{"bewijslast": "Jaarlijks auditprogramma"}, {"bewijslast": "NC-lijst"}],
    )

    assert beeld.gedekte_items == {"Auditplannen en auditverslagen", "Kwalificatie auditoren"}
    assert beeld.dekkingsgraad == 0.5, "2 van 4 items, niet 6 van 8 rijen"
    assert "2 van 4" in ca.orden([beeld])[0][1]


def test_item_dat_zowel_gedekt_als_ontbrekend_heet_telt_als_gedekt() -> None:
    """Het model kan een item in beide lijsten zetten; dan is er bewijs, en telt dat."""
    beeld = ca.Clausulebeeld(
        norm="9001",
        clausule_id="5.1",
        titel="x",
        bewijs_aanwezig=[{"bewijslast": "Beleid", "bron": "d1"}],
        bewijs_ontbreekt=[{"bewijslast": "Beleid"}],
    )

    assert beeld.open_items == set()
    assert beeld.dekkingsgraad == 1.0


def test_record_bevat_geen_oordeelsveld() -> None:
    record = ca.Clausulebeeld(norm="9001", clausule_id="5.1", titel="x").als_record()

    assert not (set(record) & ca.VERBODEN_VELDEN)
    assert "dekkingsgraad" in record
