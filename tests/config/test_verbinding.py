"""Een faalpad mag nooit een leveranciersrespons doorgeven aan de client.

Dit is de test achter een echt lek: tot 2026-08-14 gaf `_check_source` `str(exc)[:200]`
door aan het configuratiescherm, en die tekst komt uit de client van de leverancier.
"""

from __future__ import annotations

import logging

import pytest

from iso_audit.api import session as sess
from iso_audit.config import verbinding as vb


class _Kapot:
    """Adapter die faalt met een melding waar een credential in staat."""

    def probe(self) -> dict[str, object]:
        raise RuntimeError(
            "401 Unauthorized bij GET "
            "https://org.atlassian.net/rest/api/3/search?token=sk-geheim-abc123"
        )


# --- classificatie --------------------------------------------------------


@pytest.mark.parametrize(
    ("melding", "verwacht"),
    [
        ("401 Unauthorized", "auth"),
        ("403 Forbidden", "auth"),
        ("PERMISSION_DENIED on files.list", "auth"),
        ("invalid_grant", "auth"),
        ("unauthorized_client", "auth"),
        ("invalid x-api-key", "auth"),
        ("404 Not Found", "niet_gevonden"),
        ("File notFound", "niet_gevonden"),
        ("Connection timed out", "netwerk"),
        ("temporary failure in name resolution", "netwerk"),
        ("503 Service Unavailable", "netwerk"),
        ("iets volstrekt anders", "onbekend"),
    ],
)
def test_classificeer(melding: str, verwacht: str) -> None:
    assert vb.classificeer(melding) == verwacht


def test_elke_soort_heeft_een_leesbare_tekst() -> None:
    for soort, tekst in vb.TEKST.items():
        assert tekst.endswith("."), soort
        assert len(tekst) > 20, soort


# --- normaliseren lekt niet ----------------------------------------------


def test_normaliseer_geeft_het_geheim_niet_terug(caplog: pytest.LogCaptureFixture) -> None:
    fout = RuntimeError("401 bij https://org.atlassian.net/x?token=sk-geheim-abc123")
    with caplog.at_level(logging.WARNING, logger="iso_audit.audit"):
        soort, tekst = vb.normaliseer(fout, bron="jira")

    assert soort == "auth"
    assert "sk-geheim-abc123" not in tekst
    assert "atlassian.net" not in tekst
    # Voor diagnose hoort de ruwe melding wél in het serverlog.
    assert "sk-geheim-abc123" in caplog.text


def test_check_source_lekt_geen_credential_naar_de_client(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Regressie op het lek: deze `reden` gaat rechtstreeks de browser in."""
    from iso_audit import sources as registry

    monkeypatch.setattr(registry, "get", lambda _naam: _Kapot)
    with caplog.at_level(logging.WARNING, logger="iso_audit.audit"):
        uit = sess._check_source("jira")

    assert uit["connected"] is False
    assert uit["soort"] == "auth"
    tekst = str(uit["reden"])
    assert "sk-geheim-abc123" not in tekst
    assert "atlassian.net" not in tekst
    assert "401" not in tekst, "geen ruwe statuscode richting de auditor"


def test_miro_melding_noemt_geen_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Het configuratiescherm is niet de plek om variabelenamen te leren."""
    monkeypatch.delenv("MIRO_API_TOKEN", raising=False)
    uit = sess._check_source("miro")
    assert uit["connected"] is False
    assert "MIRO_API_TOKEN" not in str(uit["reden"])


# --- anthropic ------------------------------------------------------------


def test_anthropic_check_faalt_netjes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zonder credential is het antwoord 'niet verbonden', geen stacktrace."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ongeldig-voor-de-test")
    monkeypatch.setattr(vb, "normaliseer", lambda exc, bron: ("auth", vb.TEKST["auth"]))

    class _Kapotte:
        def __init__(self) -> None: ...

        @property
        def models(self) -> object:
            raise RuntimeError("401 invalid x-api-key sk-ongeldig-voor-de-test")

    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", _Kapotte)
    uit = vb.anthropic_check("claude-haiku-4-5")

    assert uit["connected"] is False
    assert "sk-ongeldig" not in str(uit["reden"])
