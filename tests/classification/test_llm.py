"""Tests voor `iso_audit.classification.llm` — pure helpers + mocked anthropic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import anthropic

from iso_audit.classification import llm


def _fake_response(text: str) -> Any:
    # `type` expliciet zetten: de API geeft blokken met een type terug, en zonder dat
    # veld kan deze stub het echte gedrag van Sonnet 5 en Opus 5 — een thinking-blok in
    # plaats van een tekstblok — niet nabootsen. Zie `classification/respons.py`.
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


# ---------- _bouw_sub_overzicht ----------


def test_bouw_sub_overzicht_bevat_sub_punten() -> None:
    """Subpunten uit NORMTEKSTEN_9001 verschijnen in `<cid><sp_id>: <eis>` formaat."""
    overzicht = llm._bouw_sub_overzicht()
    # 9001 §4.1 heeft sub-punten in de bron-data.
    assert "4.1a:" in overzicht or "4.1b:" in overzicht


def test_bouw_system_prompt_bevat_overzicht() -> None:
    prompt = llm._bouw_system_prompt()
    assert "ISO 9001" in prompt
    assert "Beschikbare sub-clausules" in prompt
    # Volgt het JSON-formaat-voorschrift.
    assert '"resultaten"' in prompt


# ---------- _classificeer_batch ----------


def test_classificeer_batch_happy_path() -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response(
        '{"resultaten": [{"doc_id": "d1", "matches": [{"clausule": "4.1", "sub_punt": "a"}]}]}'
    )
    docs = [{"id": "d1", "naam": "Beleid", "tekst": "x" * 100}]
    res = llm._classificeer_batch(docs, client)
    assert res == [{"doc_id": "d1", "matches": [{"clausule": "4.1", "sub_punt": "a"}]}]
    client.messages.create.assert_called_once()
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == llm.MODEL


def test_classificeer_batch_tekst_truncatie() -> None:
    """Documenttekst wordt geknipt op MAX_TEKST."""
    client = MagicMock()
    client.messages.create.return_value = _fake_response('{"resultaten": []}')
    docs = [{"id": "d1", "naam": "X", "tekst": "y" * (llm.MAX_TEKST + 200)}]
    llm._classificeer_batch(docs, client)
    invoer = client.messages.create.call_args.kwargs["messages"][0]["content"]
    # MAX_TEKST chars + naam/id prefix; geen 700 y's achter elkaar.
    assert "y" * (llm.MAX_TEKST + 1) not in invoer


def test_classificeer_batch_geen_json_in_response() -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response("Sorry, geen JSON")
    res = llm._classificeer_batch([{"id": "d1", "naam": "X", "tekst": ""}], client)
    assert res == []


def test_classificeer_batch_invalid_json() -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_response("{ this is not json }")
    res = llm._classificeer_batch([{"id": "d1", "naam": "X", "tekst": ""}], client)
    assert res == []


def test_classificeer_batch_api_error() -> None:
    """anthropic.APIError → lege resultaten, geen raise."""
    client = MagicMock()
    err = anthropic.APIError(message="boom", request=MagicMock(), body=None)
    client.messages.create.side_effect = err
    res = llm._classificeer_batch([{"id": "d1", "naam": "X", "tekst": ""}], client)
    assert res == []


# ---------- run (geïntegreerde flow met mocks) ----------


def test_run_droog_doet_geen_db_mutatie(monkeypatch: Any) -> None:
    """In droog-mode worden GEEN bestaande clause_matches verwijderd."""
    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchall.return_value = []  # geen documenten

    monkeypatch.setattr(llm, "anthropic", MagicMock(Anthropic=MagicMock()))
    with (
        patch("iso_audit.store.verbinding", return_value=fake_conn),
        patch("iso_audit.store.upsert_clause_match") as mock_upsert,
    ):
        llm.run(batch_grootte=4, droog=True)

    # Géén DELETE-call op clause_matches.
    delete_calls = [
        c for c in fake_conn.execute.call_args_list if "DELETE" in str(c.args[0]).upper()
    ]
    assert not delete_calls
    mock_upsert.assert_not_called()


def test_run_geen_documenten(monkeypatch: Any) -> None:
    """Lege document-tabel → run completes zonder API-call."""
    fake_conn = MagicMock()
    fake_conn.execute.return_value.fetchall.return_value = []

    fake_anthropic_module = MagicMock()
    fake_client = MagicMock()
    fake_anthropic_module.Anthropic.return_value = fake_client
    fake_anthropic_module.APIError = anthropic.APIError
    monkeypatch.setattr(llm, "anthropic", fake_anthropic_module)

    with patch("iso_audit.store.verbinding", return_value=fake_conn):
        llm.run(droog=True)
    # Geen messages.create-call (geen API-check in droog-mode + geen docs).
    fake_client.messages.create.assert_not_called()
