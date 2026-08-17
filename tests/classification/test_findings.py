"""Tests voor `iso_audit.classification.findings` — pure helpers + integratie."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from iso_audit import store
from iso_audit.classification import findings

# ---------- _parse_json_list ----------


def test_parse_json_list_valid() -> None:
    out = findings._parse_json_list('Prelude [{"a": 1}, {"b": 2}] Trailing')
    assert out == [{"a": 1}, {"b": 2}]


def test_parse_json_list_geen_array() -> None:
    assert findings._parse_json_list("Geen JSON hier") == []


def test_parse_json_list_zonder_sluit_bracket() -> None:
    """Geen sluitbracket → graceful lege lijst."""
    assert findings._parse_json_list("[invalid json") == []


def test_parse_json_list_invalid_inhoud_raised() -> None:
    """Wél brackets maar invalide inhoud → JSONDecodeError."""
    import json as _json

    with pytest.raises(_json.JSONDecodeError):
        findings._parse_json_list("[foo bar baz]")


# ---------- _is_miro_mistag ----------


@pytest.mark.parametrize(
    "tekst, verwacht",
    [
        ("Misclassificatie van item", True),
        ("Hoort niet bij clausule X", True),
        ("Item verwijst alleen naar bordtitel", True),
        ("Vraag over iets dat niet bij deze clausule hoort", True),
        ("**Hoort niet bij clausule** ergens", True),  # markdown-prefix
        ("Normale OFI-beschrijving", False),
        ("", False),
    ],
)
def test_is_miro_mistag(tekst: str, verwacht: bool) -> None:
    assert findings._is_miro_mistag(tekst) is verwacht


# ---------- _systeem_voor ----------


def test_systeem_voor_miro() -> None:
    assert findings._systeem_voor(scherpte=1.0, herkomst="Miro") is findings._SYSTEM_MIRO


def test_systeem_voor_drive_scherp() -> None:
    assert findings._systeem_voor(scherpte=1.0) is findings._SYSTEM_SCHERP


def test_systeem_voor_drive_genuanceerd_onder_drempel() -> None:
    assert findings._systeem_voor(scherpte=0.5) is findings._SYSTEM_GENUANCEERD


def test_systeem_voor_grens_0_75() -> None:
    """Bij scherpte=0.75 exact → scherp."""
    assert findings._systeem_voor(scherpte=0.75) is findings._SYSTEM_SCHERP


# ---------- _bouw_doc_user_prompt ----------


def test_bouw_doc_user_prompt_bevat_titel_en_clausules() -> None:
    doc = {"naam": "Beleid", "tekst": "Inhoud van het document"}
    out = findings._bouw_doc_user_prompt(doc, ["10.2", "4.1"], {"10.2": {"titel": "NC"}})
    assert "Document: Beleid" in out
    assert "Inhoud van het document" in out
    assert "- 10.2: NC" in out
    assert "- 4.1: 4.1" in out  # fallback titel = id


def test_bouw_doc_user_prompt_tekst_truncatie() -> None:
    doc = {"naam": "X", "tekst": "y" * (findings.MAX_TEKST + 500)}
    out = findings._bouw_doc_user_prompt(doc, ["1.1"], {})
    assert "y" * (findings.MAX_TEKST + 1) not in out


# ---------- _bouw_miro_user_prompt ----------


def test_bouw_miro_user_prompt() -> None:
    notities = [
        {"miro_item_id": "m1", "clausule": "8.16", "tekst": "logging item"},
        {"id": "m2", "clausule": "5.27", "tekst": "incident item"},
    ]
    clausules = {"8.16": {"titel": "Monitoring"}}
    out = findings._bouw_miro_user_prompt(notities, clausules)
    assert "ID: m1" in out
    assert "Monitoring" in out
    assert "ID: m2" in out


# ---------- _maak_system_param ----------


def test_maak_system_param_ephemeral_cache() -> None:
    p = findings._maak_system_param("Tekst")
    assert p == [
        {
            "type": "text",
            "text": "Tekst",
            "cache_control": {"type": "ephemeral"},
        }
    ]


# ---------- Kostenteller ----------


def test_kostenteller_voeg_toe_accumuleert() -> None:
    teller = findings.Kostenteller(model="claude-haiku-4-5-20251001")
    usage = MagicMock(
        input_tokens=100,
        output_tokens=50,
        cache_creation_input_tokens=200,
        cache_read_input_tokens=300,
    )
    teller.voeg_toe(usage, elapsed_s=1.5)
    teller.voeg_toe(usage, elapsed_s=2.0)
    assert teller.calls == 2
    assert teller.input_tokens == 200
    assert teller.output_tokens == 100
    assert teller.cache_write_tokens == 400
    assert teller.cache_read_tokens == 600
    assert teller.elapsed_s == 3.5


def test_kostenteller_kosten_haiku() -> None:
    teller = findings.Kostenteller(model="claude-haiku-4-5-20251001")
    # 1M input tokens à $1.00 = $1.00. Was $0.80 tot 2026-08-14: de prijzentabel stond
    # te laag, waardoor kostenregels in auditrapporten ~25% te laag uitvielen.
    teller.input_tokens = 1_000_000
    assert teller.kosten_usd() == pytest.approx(1.00)


def test_kostenteller_alias_en_gedateerde_haiku_kosten_gelijk() -> None:
    """Historische runs staan op de gedateerde ID; die mag niet anders uitpakken."""
    alias = findings.Kostenteller(model="claude-haiku-4-5")
    gedateerd = findings.Kostenteller(model="claude-haiku-4-5-20251001")
    alias.input_tokens = 1_000_000
    gedateerd.input_tokens = 1_000_000
    assert alias.kosten_usd() == pytest.approx(gedateerd.kosten_usd())


def test_kostenteller_kosten_onbekend_model() -> None:
    teller = findings.Kostenteller(model="onbekend-model")
    teller.input_tokens = 1_000_000
    assert teller.kosten_usd() == 0.0


def test_kostenteller_rapport_string() -> None:
    teller = findings.Kostenteller(calls=5)
    r = teller.rapport()
    assert "calls=5" in r
    assert "kosten=$" in r


# ---------- _classificeer_doc ----------


def _blok(soort: str, text: str = "") -> Any:
    """Eén responsblok met een expliciet `type`, zoals de API het teruggeeft.

    Het `type` zetten is niet cosmetisch: tot 2026-08-17 zette deze fixture het niet, en
    daardoor kon hij het echte gedrag van Sonnet 5 en Opus 5 — een thinking-blok vóór (of in
    plaats van) het tekstblok — niet nabootsen. De bug die daaruit volgde was in de tests
    onzichtbaar.
    """
    blok = MagicMock()
    blok.type = soort
    blok.text = text
    return blok


def _fake_resp(text: str, blokken: list[Any] | None = None) -> Any:
    """Bouw een minimaal anthropic-response-object met `.content` + `.usage`.

    `blokken` overschrijft de inhoud, voor responsen die niet met een tekstblok beginnen.
    """
    resp = MagicMock()
    resp.content = blokken if blokken is not None else [_blok("text", text)]
    resp.usage = MagicMock(
        input_tokens=10,
        output_tokens=20,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
    )
    return resp


def test_classificeer_doc_happy() -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_resp(
        '[{"clausule": "10.2", "classificatie": "OFI", "beschrijving": "..", "onderbouwing": ".."}]'
    )
    teller = findings.Kostenteller()
    doc = {"naam": "Doc", "tekst": "x"}
    out = findings._classificeer_doc(doc, ["10.2"], {"10.2": {"titel": "NC"}}, client, teller)
    assert out == [
        {"clausule": "10.2", "classificatie": "OFI", "beschrijving": "..", "onderbouwing": ".."}
    ]
    assert teller.calls == 1


_JSON_BEVINDING = (
    '[{"clausule": "10.2", "classificatie": "OFI", "beschrijving": "..", "onderbouwing": ".."}]'
)


def test_thinking_wordt_expliciet_uitgezet() -> None:
    """Weglaten is niet "uit": dan bepaalt het gekozen model het gedrag.

    Gemeten op 2026-08-17 tegen de echte API: zonder deze parameter leverde
    `claude-sonnet-5` op een classificatie-achtige vraag alléén een thinking-blok en géén
    tekstblok. Dat maakte de uitkomst afhankelijk van welk model de auditor koos.
    """
    client = MagicMock()
    client.messages.create.return_value = _fake_resp(_JSON_BEVINDING)
    findings._classificeer_doc(
        {"naam": "Doc", "tekst": "x"},
        ["10.2"],
        {"10.2": {"titel": "NC"}},
        client,
        findings.Kostenteller(),
    )
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["thinking"] == {"type": "disabled"}


def test_tekstblok_wordt_gevonden_achter_een_thinking_blok() -> None:
    """`content[0]` is een aanname; het tekstblok hoort op type gevonden te worden.

    Dit is precies wat Sonnet 5 en Opus 5 teruggaven: een thinking-blok eerst.
    """
    client = MagicMock()
    client.messages.create.return_value = _fake_resp(
        "", blokken=[_blok("thinking"), _blok("text", _JSON_BEVINDING)]
    )
    teller = findings.Kostenteller()
    out = findings._classificeer_doc(
        {"naam": "Doc", "tekst": "x"}, ["10.2"], {"10.2": {"titel": "NC"}}, client, teller
    )
    assert out and out[0]["clausule"] == "10.2"
    assert teller.fouten == 0


def test_respons_zonder_tekstblok_is_een_storing() -> None:
    """Tokens verbruikt en geen antwoord kunnen lezen is een fout, geen leeg oordeel.

    Tot 2026-08-17 gaf dit stil een lege lijst: geen foutenteller, geen logregel. De run
    meldde zich klaar met nul bevindingen — de ernstigste vorm van valse dekking voor een
    audittool, want het rapport is leeg en lijkt compleet.
    """
    client = MagicMock()
    client.messages.create.return_value = _fake_resp("", blokken=[_blok("thinking")])
    teller = findings.Kostenteller()
    out = findings._classificeer_doc(
        {"naam": "Doc", "tekst": "x"}, ["10.2"], {"10.2": {"titel": "NC"}}, client, teller
    )
    assert out == []
    assert teller.fouten == 1, "een onleesbaar antwoord moet als fout meetellen"


def test_leesbaar_antwoord_zonder_bevindingen_blijft_geldig() -> None:
    """Het model dat expliciet niets rapporteert is een oordeel, geen storing."""
    client = MagicMock()
    client.messages.create.return_value = _fake_resp("[]")
    teller = findings.Kostenteller()
    out = findings._classificeer_doc(
        {"naam": "Doc", "tekst": "x"}, ["10.2"], {"10.2": {"titel": "NC"}}, client, teller
    )
    assert out == []
    assert teller.fouten == 0, "leeg oordeel is geen fout"


def test_output_budget_is_per_item_en_uitgelegd() -> None:
    """Het budget moet meeschalen met het aantal items.

    Belangrijker dan het getal: zodra thinking aangaat begrenst `max_tokens` thinking én
    antwoord samen. Bij één clausule is dit 214 tokens, en gemeten op 2026-08-17 ging dat
    budget volledig op aan thinking — `stop_reason` was `max_tokens` en er kwam geen
    tekstblok. Deze test faalt als iemand het budget losmaakt van het aantal items.
    """
    assert findings._max_tokens_voor(1) == 214
    assert findings._max_tokens_voor(5) == 814
    assert findings._max_tokens_voor(5) > findings._max_tokens_voor(1)


def test_classificeer_doc_api_error() -> None:
    client = MagicMock()
    err = anthropic.APIError(message="boom", request=MagicMock(), body=None)
    client.messages.create.side_effect = err
    teller = findings.Kostenteller()
    out = findings._classificeer_doc({"naam": "x", "tekst": ""}, ["1.1"], {}, client, teller)
    assert out == []
    assert teller.fouten == 1


def test_classificeer_doc_json_parse_error() -> None:
    """Brackets aanwezig maar inhoud invalide → fout-teller geraakt."""
    client = MagicMock()
    client.messages.create.return_value = _fake_resp("[foo bar baz]")
    teller = findings.Kostenteller()
    out = findings._classificeer_doc({"naam": "x", "tekst": ""}, ["1.1"], {}, client, teller)
    assert out == []
    assert teller.fouten == 1


# ---------- _classificeer_miro_batch ----------


def test_classificeer_miro_batch_happy() -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_resp(
        '[{"id": "m1", "classificatie": "NC", "beschrijving": "..", "onderbouwing": ".."}]'
    )
    teller = findings.Kostenteller()
    notities = [{"miro_item_id": "m1", "clausule": "8.16", "tekst": "x"}]
    out = findings._classificeer_miro_batch(notities, {}, client, teller)
    assert out[0]["id"] == "m1"


def test_classificeer_miro_batch_api_error() -> None:
    client = MagicMock()
    err = anthropic.APIError(message="boom", request=MagicMock(), body=None)
    client.messages.create.side_effect = err
    teller = findings.Kostenteller()
    out = findings._classificeer_miro_batch([{"id": "m1"}], {}, client, teller)
    assert out == []
    assert teller.fouten == 1


# ---------- DB helpers ----------


@pytest.fixture
def db_pad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    pad = tmp_path / "audit.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(pad))
    conn = store.verbinding(str(pad))
    store.initialiseer(conn)
    conn.close()
    return str(pad)


def test_gedaan_per_doc(db_pad: str) -> None:
    conn = store.verbinding(db_pad)
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "document_naam, classified_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        ("d1", "Drive", "10.2", "9001", "OFI", "Doc1"),
    )
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "document_naam, classified_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        ("d1", "Drive", "8.16", "9001", "NC", "Doc1"),
    )
    # Jira deelt het document-pad → moet meetellen in de dedup.
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "document_naam, classified_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        ("AUD-7", "Jira", "5.30", "9001", "NC", "AUD-7"),
    )
    # Miro heeft een eigen pad → mag NIET in deze dedup verschijnen.
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "document_naam, classified_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        ("m1", "Miro", "10.2", "9001", "OFI", "Sticky1"),
    )
    conn.commit()
    result = findings._gedaan_per_doc(conn, "9001")
    conn.close()
    assert result == {"d1": {"10.2", "8.16"}, "AUD-7": {"5.30"}}


def test_gedaan_miro(db_pad: str) -> None:
    conn = store.verbinding(db_pad)
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "document_naam, classified_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        ("m1", "Miro", "10.2", "9001", "OFI", "Sticky1"),
    )
    conn.commit()
    result = findings._gedaan_miro(conn, "9001")
    conn.close()
    assert result == {"m1"}


def test_upsert_bevindingen_overwrite(db_pad: str) -> None:
    """Tweede call op zelfde key overschrijft de eerste (UPSERT)."""
    conn = store.verbinding(db_pad)
    bev1 = {
        "_doc_id": "d1",
        "herkomst": "Drive",
        "clausule": "10.2",
        "document_naam": "Doc",
        "classificatie": "OFI",
        "beschrijving": "v1",
        "onderbouwing": "",
        "pre_classificatie": None,
    }
    findings._upsert_bevindingen(conn, [bev1], "9001")
    bev1["classificatie"] = "NC"
    bev1["beschrijving"] = "v2"
    findings._upsert_bevindingen(conn, [bev1], "9001")
    rows = conn.execute("SELECT classificatie, beschrijving FROM bevindingen").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["classificatie"] == "NC"
    assert rows[0]["beschrijving"] == "v2"


# ---------- schat_kosten ----------


def test_schat_kosten_lege_input(db_pad: str) -> None:
    result = findings.schat_kosten([], [], {"clausules": {}})
    assert result["calls"] == 0
    assert result["kosten_usd_schatting"] == 0.0


def test_schat_kosten_één_doc(db_pad: str) -> None:
    doc = {"id": "d1", "naam": "Beleid", "tekst": "x" * 500, "clausules": ["10.2"]}
    result = findings.schat_kosten([doc], [], {"clausules": {"10.2": {"titel": "NC"}}})
    assert result["calls"] == 1
    # Eerste call → cache-write op de system-prompt.
    assert result["input_cache_write"] > 0
    assert result["input_cache_read"] == 0
    assert result["kosten_usd_schatting"] > 0


def test_schat_kosten_rehash_negeert_checkpoint(db_pad: str) -> None:
    # Maak een bestaande bevinding.
    conn = store.verbinding(db_pad)
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "document_naam, classified_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        ("d1", "Drive", "10.2", "9001", "OFI", "Doc"),
    )
    conn.commit()
    conn.close()

    doc = {"id": "d1", "naam": "Doc", "tekst": "x", "clausules": ["10.2"]}
    cm = {"clausules": {"10.2": {"titel": "NC"}}}

    # Zonder rehash: niets te doen.
    r1 = findings.schat_kosten([doc], [], cm, norm="9001", rehash=False)
    assert r1["calls"] == 0

    # Met rehash: één call.
    r2 = findings.schat_kosten([doc], [], cm, norm="9001", rehash=True)
    assert r2["calls"] == 1


# ---------- review_en_bevestig ----------


def test_review_auto_accept() -> None:
    bev = [
        {
            "clausule": "10.2",
            "clausule_titel": "NC",
            "classificatie": "OFI",
            "herkomst": "Drive",
            "document_naam": "Doc",
            "beschrijving": "x",
        }
    ]
    result = findings.review_en_bevestig(bev, auto_accept=True)
    assert result == bev


def test_review_interactief_corrigeer_naar_nc() -> None:
    bev = [
        {
            "clausule": "10.2",
            "clausule_titel": "NC",
            "classificatie": "OFI",
            "herkomst": "Drive",
            "document_naam": "Doc",
            "beschrijving": "x",
        }
    ]
    with patch("builtins.input", return_value="nc"):
        result = findings.review_en_bevestig(bev, auto_accept=False)
    assert result[0]["classificatie"] == "NC"


def test_review_interactief_skip() -> None:
    bev = [
        {
            "clausule": "10.2",
            "clausule_titel": "NC",
            "classificatie": "OFI",
            "herkomst": "Drive",
            "document_naam": "Doc",
            "beschrijving": "x",
        }
    ]
    with patch("builtins.input", return_value="s"):
        result = findings.review_en_bevestig(bev, auto_accept=False)
    assert result == []


def test_review_interactief_accepteer() -> None:
    bev = [
        {
            "clausule": "10.2",
            "clausule_titel": "NC",
            "classificatie": "OFI",
            "herkomst": "Drive",
            "document_naam": "Doc",
            "beschrijving": "x",
        }
    ]
    with patch("builtins.input", return_value=""):
        result = findings.review_en_bevestig(bev, auto_accept=False)
    assert result == bev


# ---------- classificeer_alle_bevindingen (integratie met mocks) ----------


def test_classificeer_alle_lege_input(db_pad: str) -> None:
    """Lege docs + lege Miro → lege output, geen API-calls."""
    fake_client = MagicMock()
    with patch.object(findings.anthropic, "Anthropic", return_value=fake_client):
        out = findings.classificeer_alle_bevindingen([], [], {"clausules": {}})
    assert out == []
    fake_client.messages.create.assert_not_called()


def test_classificeer_alle_drive_doc_volledige_flow(db_pad: str) -> None:
    """Eén doc met één clausule wordt geclassificeerd; UPSERT in DB."""
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_resp(
        '[{"clausule": "10.2", "classificatie": "NC", "beschrijving": "geen evaluatie", '
        '"onderbouwing": "§10.2"}]'
    )
    docs = [{"id": "d1", "naam": "Memo", "tekst": "x", "clausules": ["10.2"]}]
    cm = {"clausules": {"10.2": {"titel": "Corrigerende maatregel"}}}
    with patch.object(findings.anthropic, "Anthropic", return_value=fake_client):
        out = findings.classificeer_alle_bevindingen(docs, [], cm, norm="9001")
    assert len(out) == 1
    assert out[0]["classificatie"] == "NC"
    assert out[0]["doc_id"] == "d1"
    assert out[0]["clausule"] == "10.2"


def test_classificeer_alle_rehash_overschrijft(db_pad: str) -> None:
    """Met rehash=True wordt een bestaande bevinding overschreven."""
    # Seed: bestaande bevinding met OFI.
    conn = store.verbinding(db_pad)
    conn.execute(
        "INSERT INTO bevindingen (doc_id, herkomst, clausule_id, norm, classificatie, "
        "document_naam, classified_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        ("d1", "Drive", "10.2", "9001", "OFI", "Memo"),
    )
    conn.commit()
    conn.close()

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_resp(
        '[{"clausule": "10.2", "classificatie": "NC", "beschrijving": "fresh", '
        '"onderbouwing": "§10.2"}]'
    )
    docs = [{"id": "d1", "naam": "Memo", "tekst": "x", "clausules": ["10.2"]}]
    cm = {"clausules": {"10.2": {"titel": "NC"}}}
    with patch.object(findings.anthropic, "Anthropic", return_value=fake_client):
        out = findings.classificeer_alle_bevindingen(docs, [], cm, norm="9001", rehash=True)
    assert out[0]["classificatie"] == "NC"
    assert out[0]["beschrijving"] == "fresh"


def test_classificeer_alle_mistag_wordt_geskipt(db_pad: str) -> None:
    """Miro-mistag wordt herkend en niet als bevinding opgeslagen."""
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_resp(
        '[{"id": "m1", "classificatie": "NC", '
        '"beschrijving": "Misclassificatie van item", "onderbouwing": ""}]'
    )
    miro = [{"miro_item_id": "m1", "clausule": "8.16", "tekst": "x"}]
    with patch.object(findings.anthropic, "Anthropic", return_value=fake_client):
        out = findings.classificeer_alle_bevindingen([], miro, {"clausules": {}}, norm="9001")
    assert out == []


def test_classificeer_alle_miro_zonder_clausule_skip(db_pad: str) -> None:
    """Miro-notitie zonder clausule wordt niet aan API gestuurd."""
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_resp("[]")
    miro = [{"miro_item_id": "m1", "clausule": "", "tekst": "x"}]
    with patch.object(findings.anthropic, "Anthropic", return_value=fake_client):
        findings.classificeer_alle_bevindingen([], miro, {"clausules": {}}, norm="9001")
    # API-call wordt wel gedaan voor de batch (met dit item erin), maar de
    # respons-verwerking skipt het ongekoppelde item via skip_teller.
    # De DB blijft leeg op dit item.
    conn = store.verbinding(db_pad)
    rows = conn.execute("SELECT * FROM bevindingen").fetchall()
    conn.close()
    assert rows == []
