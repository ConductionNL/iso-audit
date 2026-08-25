"""Tests voor `iso_audit.classification.thema` — heuristiek + LLM-mocking."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from iso_audit.classification import thema

# ---------- THEMA_LIJST + bepaal_thema (route A) ----------


def test_thema_lijst_is_finite() -> None:
    """Taxonomie heeft een vaste lengte; Overig staat als laatste.

    Het getal groeit alleen met een reden. 25 -> 26 op 2026-08-26: "Ontwikkeling &
    wijzigingsbeheer" erbij, omdat §8.9, §8.25 en §8.33 nergens anders in pasten en daardoor
    elk een eigen memo-blok kregen. Zie `tests/classification/test_thema_hiaten.py`.
    """
    assert thema.THEMA_LIJST[-1] == "Overig"
    assert len(thema.THEMA_LIJST) == 26
    # Geen duplicates.
    assert len(set(thema.THEMA_LIJST)) == len(thema.THEMA_LIJST)


def test_thema_regels_targets_in_taxonomie() -> None:
    """Elk regel-target moet in `THEMA_LIJST` staan (anders dode regel)."""
    geldig = set(thema.THEMA_LIJST)
    for naam, _ in thema.THEMA_REGELS:
        assert naam in geldig, f"Regel-target {naam!r} niet in THEMA_LIJST"


def test_bepaal_thema_lege_bevinding() -> None:
    assert thema.bepaal_thema({}) == "Overig"
    assert (
        thema.bepaal_thema({"beschrijving": "", "onderbouwing": "", "document_naam": ""})
        == "Overig"
    )


@pytest.mark.parametrize(
    "tekst, verwacht",
    [
        ("retournering van laptop bij vertrek", "Offboarding & activa-retournering"),
        ("encryptie van back-ups", "Cryptografie & encryptie"),
        ("logging van inlogpogingen ontbreekt", "Logging & monitoring"),
        ("avg verwerkingsregister", "Privacy & persoonsgegevens"),
        ("contextanalyse 2026", "Context-analyse & belanghebbenden"),
        ("management review notulen", "Directiebeoordeling"),
        ("toegangsrechten review", "Toegangsbeheer"),
    ],
)
def test_bepaal_thema_keyword_match(tekst: str, verwacht: str) -> None:
    assert thema.bepaal_thema({"beschrijving": tekst}) == verwacht


def test_bepaal_thema_first_match_wins() -> None:
    """Specifieker regel (Offboarding) komt vóór algemeen (Toegangsbeheer)."""
    # Tekst die zowel offboarding als toegangsrechten noemt.
    bev = {"beschrijving": "offboarding inclusief intrekken toegangsrechten"}
    assert thema.bepaal_thema(bev) == "Offboarding & activa-retournering"


def test_bepaal_thema_geen_match_naar_overig() -> None:
    bev = {"beschrijving": "iets volstrekt onbekends zonder keywords"}
    assert thema.bepaal_thema(bev) == "Overig"


def test_bepaal_thema_zoekt_in_meerdere_velden() -> None:
    """Match in `document_naam` telt ook."""
    bev = {
        "beschrijving": "geen relevante content hier",
        "onderbouwing": "",
        "document_naam": "Memo afwijking incident",
    }
    assert thema.bepaal_thema(bev) == "Memo & afwijkingsregistratie"


# ---------- _bouw_batch_input (route B helpers) ----------


def test_bouw_batch_input_truncates() -> None:
    batch = [
        {
            "_bev_id": "1",
            "clausule": "10.2",
            "classificatie": "OFI",
            "beschrijving": "x" * (thema.MAX_BESCHRIJVING_CHARS + 200),
            "onderbouwing": "y" * (thema.MAX_ONDERBOUWING_CHARS + 200),
        }
    ]
    out = thema._bouw_batch_input(batch)
    # Beschrijving wordt afgekapt op MAX_BESCHRIJVING_CHARS.
    assert "x" * (thema.MAX_BESCHRIJVING_CHARS + 1) not in out
    assert "y" * (thema.MAX_ONDERBOUWING_CHARS + 1) not in out


def test_bouw_batch_input_multiple_records() -> None:
    batch = [
        {
            "_bev_id": "a",
            "clausule": "10.2",
            "classificatie": "OFI",
            "beschrijving": "x",
            "onderbouwing": "y",
        },
        {
            "_bev_id": "b",
            "clausule_id": "8.16",
            "classificatie": "NC",
            "beschrijving": "p",
            "onderbouwing": "q",
        },
    ]
    out = thema._bouw_batch_input(batch)
    assert "ID: a" in out
    assert "ID: b" in out
    assert "---" in out  # separator


# ---------- _valideer ----------


def test_valideer_onbekend_thema_naar_overig() -> None:
    toewijzingen = {
        "1": "Logging & monitoring",
        "2": "BedachtThema",
        "3": "Overig",
    }
    resultaat = thema._valideer(toewijzingen)
    assert resultaat["1"] == "Logging & monitoring"
    assert resultaat["2"] == "Overig"  # onbekend → fallback
    assert resultaat["3"] == "Overig"


# ---------- classificeer_themas (LLM mock) ----------


def _fake_anthropic_response(text: str) -> Any:
    """Bouw een minimaal anthropic-response-object met `.content[0].text`."""
    # `type` expliciet zetten: de API geeft blokken met een type terug, en zonder dat
    # veld kan deze stub het echte gedrag van Sonnet 5 en Opus 5 — een thinking-blok in
    # plaats van een tekstblok — niet nabootsen. Zie `classification/respons.py`.
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


def test_classificeer_themas_lege_lijst() -> None:
    assert thema.classificeer_themas([]) == {}


def test_classificeer_themas_client_init_fout() -> None:
    """Anthropic-init exception → lege dict (heuristiek behoudt z'n waarde)."""
    with patch.object(thema.anthropic, "Anthropic", side_effect=RuntimeError("no key")):
        assert thema.classificeer_themas([{"id": "1", "beschrijving": "x"}]) == {}


def test_classificeer_themas_happy_path() -> None:
    """Mock anthropic respons; verifieer parsing + valideren."""
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response(
        '{"toewijzingen": [{"id": "1", "thema": "Logging & monitoring"}, '
        '{"id": "2", "thema": "Overig"}]}'
    )
    with patch.object(thema.anthropic, "Anthropic", return_value=fake_client):
        result = thema.classificeer_themas(
            [
                {"id": "1", "beschrijving": "log review ontbreekt"},
                {"id": "2", "beschrijving": "iets onbekends"},
            ]
        )
    assert result == {"1": "Logging & monitoring", "2": "Overig"}


def test_classificeer_themas_geen_json_in_respons() -> None:
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response(
        "Sorry, geen JSON beschikbaar."
    )
    with patch.object(thema.anthropic, "Anthropic", return_value=fake_client):
        result = thema.classificeer_themas([{"id": "1", "beschrijving": "x"}])
    assert result == {}


def test_classificeer_themas_invalid_json() -> None:
    fake_client = MagicMock()
    fake_client.messages.create.return_value = _fake_anthropic_response("{this is not valid json}")
    with patch.object(thema.anthropic, "Anthropic", return_value=fake_client):
        result = thema.classificeer_themas([{"id": "1", "beschrijving": "x"}])
    assert result == {}


def test_classificeer_themas_batch_exception_continues() -> None:
    """Eén batch faalt → tweede batch wordt nog verwerkt."""
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [
        RuntimeError("rate limit"),
        _fake_anthropic_response('{"toewijzingen": [{"id": "2", "thema": "Overig"}]}'),
    ]
    # Force twee batches met BATCH_GROOTTE=50 → twee bevindingen langs één batch
    # voldoet niet. Patch BATCH_GROOTTE naar 1 voor deze test.
    with (
        patch.object(thema.anthropic, "Anthropic", return_value=fake_client),
        patch.object(thema, "BATCH_GROOTTE", 1),
    ):
        result = thema.classificeer_themas(
            [
                {"id": "1", "beschrijving": "x"},
                {"id": "2", "beschrijving": "y"},
            ]
        )
    # Eerste batch faalde; tweede slaagde.
    assert result == {"2": "Overig"}


# ---------- verfijn_overig (hybride) ----------


def test_verfijn_overig_geen_overig() -> None:
    """Heuristiek dekt alles → geen LLM-call nodig."""
    bevindingen = [
        {"id": "1", "beschrijving": "logging review"},
        {"id": "2", "beschrijving": "encryptie van back-ups"},
    ]
    with patch.object(thema, "classificeer_themas") as mock:
        result = thema.verfijn_overig(bevindingen)
    assert result == {}
    mock.assert_not_called()


def test_verfijn_overig_subset_naar_llm() -> None:
    """Alleen `Overig`-bevindingen worden naar LLM gestuurd."""
    bevindingen = [
        {"id": "1", "beschrijving": "logging review"},  # → Logging
        {"id": "2", "beschrijving": "iets onbekends"},  # → Overig
        {"id": "3", "beschrijving": "encryptie van back-ups"},  # → Cryptografie
        {"id": "4", "beschrijving": "ook onbekend"},  # → Overig
    ]
    with patch.object(thema, "classificeer_themas") as mock:
        mock.return_value = {"2": "Risicomanagement", "4": "Overig"}
        result = thema.verfijn_overig(bevindingen)
    # classificeer_themas kreeg alleen #2 en #4.
    mock.assert_called_once()
    passed = mock.call_args[0][0]
    ids = {b["id"] for b in passed}
    assert ids == {"2", "4"}
    assert result == {"2": "Risicomanagement", "4": "Overig"}
