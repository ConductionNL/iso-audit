"""Tests voor `POST /assistent/vraag` — de route rond de Bronbevrager.

Wat hier wordt afgedwongen: de vraag komt achter dezelfde gate als de rest, hij mag niet
tijdens een run gesteld worden, en een onverifieerbaar antwoord komt niet als antwoord
terug maar als storing — mét een regel in de trail.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from iso_audit.store import initialiseer, now

from .conftest import PortaalClient, maak_portaal


class _Blok:
    def __init__(self, tekst: str) -> None:
        self.type = "text"
        self.text = tekst


class _Usage:
    input_tokens = 400
    output_tokens = 150
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0


class _Respons:
    def __init__(self, tekst: str) -> None:
        self.content = [_Blok(tekst)]
        self.stop_reason = "end_turn"
        self.usage = _Usage()


class _Client:
    def __init__(self, antwoord: str) -> None:
        self.antwoord = antwoord
        self.messages = self

    def create(self, **kw: Any) -> _Respons:
        return _Respons(self.antwoord)


@pytest.fixture
def portaal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PortaalClient:
    """Portaal met een eigen DB, zodat een test nooit de echte audit-DB raakt."""
    db = tmp_path / "audit.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(db))
    conn = sqlite3.connect(db)
    initialiseer(conn)
    conn.execute(
        "INSERT INTO documents (id, naam, tekst, herkomst, ingested_at) VALUES (?,?,?,?,?)",
        ("d1", "Cryptobeleid.docx", "sleutelbeheer", "Drive", now()),
    )
    conn.execute(
        "INSERT INTO clause_matches (doc_id, herkomst, clausule_id, norm) VALUES (?,?,?,?)",
        ("d1", "Drive", "8.24", "27001"),
    )
    conn.commit()
    conn.close()
    return maak_portaal(tmp_path)


def _stub(monkeypatch: pytest.MonkeyPatch, antwoord: str) -> None:
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: _Client(antwoord))


def _rijen(tmp_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(tmp_path / "audit.db")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM assistent_vragen ORDER BY id").fetchall()
    finally:
        conn.close()


def test_lege_vraag_wordt_geweigerd(portaal: PortaalClient) -> None:
    r = portaal.post("/assistent/vraag", json={"vraag": "   "})
    assert r.status_code == 400


def test_geldige_vraag_geeft_antwoord_met_bronnen(
    portaal: PortaalClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub(monkeypatch, "Het cryptobeleid raakt 8.24 [bron:d1].")

    r = portaal.post("/assistent/vraag", json={"vraag": "Welk bewijs hebben wij voor 8.24?"})

    assert r.status_code == 200
    body = r.json()
    assert body["gebruikt"] == ["d1"]
    assert [b["id"] for b in body["meegegeven"]] == [b["id"] for b in body["meegegeven"]]
    assert any(b["id"] == "d1" for b in body["meegegeven"])
    rijen = _rijen(tmp_path)
    assert len(rijen) == 1 and rijen[0]["storing"] is None


def test_onverifieerbaar_antwoord_is_502_en_staat_in_de_trail(
    portaal: PortaalClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Geen antwoord met een waarschuwing eronder: dan leest de auditor het antwoord."""
    _stub(monkeypatch, "Er is beleid [bron:d-verzonnen].")

    r = portaal.post("/assistent/vraag", json={"vraag": "Bewijs voor 8.24?"})

    assert r.status_code == 502
    rijen = _rijen(tmp_path)
    assert len(rijen) == 1
    assert rijen[0]["antwoord"] == ""
    assert "niet zijn meegegeven" in rijen[0]["storing"]


def test_vraag_zonder_dekking_bevraagt_geen_model(
    portaal: PortaalClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _weiger(*a: Any, **k: Any) -> Any:
        raise AssertionError("er mag geen model bevraagd zijn zonder bronnen")

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _weiger)

    r = portaal.post("/assistent/vraag", json={"vraag": "Wat is de beste encryptie?"})

    assert r.status_code == 200
    assert r.json()["geen_dekking"] is True
