"""Wat niet gelezen kon worden, zegt waaróm — en of het aan het token lag.

Een bron die stilzwijgend niets teruggeeft, levert een audit op waarin "geen workflows
gevonden" en "ik mocht de workflowmap niet lezen" er identiek uitzien. Het eerste is een
bevinding, het tweede een gat in de dekking. Ze verwisselen is precies de fout die dit project
het vaakst heeft gemaakt.

Vier statussen met vier betekenissen:

- **401** — het token is niet meegestuurd of niet geldig.
- **403 met een lege limiet** — de API-limiet is op. Zonder token is dat 60 per uur, en dan
  stopt een run halverwege op iets wat als "bron leeg" leest.
- **403** — het token bestaat maar mist dit recht. Dit is het geval bij `Administration: read`
  voor branch-bescherming.
- **404** — bestaat niet. Bij GitHub óók het antwoord voor iets dat je niet mág zien, en die
  dubbelzinnigheid hoort in de melding te staan in plaats van te worden weggepoetst.
"""

from __future__ import annotations

import pytest

from iso_audit.clients.forge import duiding


class _Antwoord:
    def __init__(self, status: int, headers: dict[str, str] | None = None) -> None:
        self.status_code = status
        self.headers = headers or {}


def test_401_wijst_het_token_aan() -> None:
    tekst = duiding(_Antwoord(401))
    assert "token" in tekst
    assert "401" in tekst


def test_403_met_lege_limiet_noemt_de_limiet() -> None:
    """Zonder token is dat 60 per uur — dan stopt een run halverwege."""
    tekst = duiding(_Antwoord(403, {"x-ratelimit-remaining": "0", "x-ratelimit-limit": "60"}))
    assert "limiet" in tekst
    assert "60" in tekst


def test_403_zonder_limietuitputting_wijst_op_ontbrekende_rechten() -> None:
    tekst = duiding(_Antwoord(403, {"x-ratelimit-remaining": "4999"}))
    assert "recht" in tekst
    assert "limiet" not in tekst


def test_404_noemt_beide_mogelijkheden() -> None:
    """GitHub geeft 404 voor "bestaat niet" én voor "mag je niet zien"."""
    tekst = duiding(_Antwoord(404))
    assert "bestaat niet" in tekst
    assert "token" in tekst


def test_een_onbekende_status_wordt_gewoon_genoemd() -> None:
    assert "502" in duiding(_Antwoord(502))


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_er_komt_altijd_een_leesbare_reden(status: int) -> None:
    """Een lege reden is hetzelfde als geen melding."""
    assert len(duiding(_Antwoord(status))) > 20


def test_ook_de_repository_aanroep_duidt_de_status() -> None:
    """Gevonden door de proefrun van 2026-08-26: een privérepo gaf "gaf 404" — een kale status.

    Dat is precies waar de duiding voor bestaat, en juist de eerste aanroep per repository
    miste hem. Een auditor die "gaf 404" leest, weet niet of de repo weg is of dat hij hem niet
    mag zien.
    """
    import inspect

    from iso_audit.clients import forge

    for klasse in (forge.GitHubClient, forge.CodebergClient):
        bron = inspect.getsource(klasse.repository)
        assert "duiding(antwoord)" in bron, klasse.__name__
        assert "gaf {antwoord.status_code}" not in bron, klasse.__name__
