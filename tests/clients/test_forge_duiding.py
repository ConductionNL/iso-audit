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


def test_409_is_een_lege_repository_en_geen_storing() -> None:
    """Gemeten tijdens de eerste org-brede run: 11 van de 385 repository's gaven 409.

    GitHub antwoordt letterlijk *"Git Repository is empty."* op de bestandslijst van een
    repository zonder commits. Dat is een waarneming — er is niets om te auditen — en geen gat in
    de dekking. "De forge gaf een onverwacht antwoord (409)" liet de auditor zoeken naar een
    storing die er niet was.
    """
    tekst = duiding(_Antwoord(409))
    assert "leeg" in tekst
    assert "onverwacht" not in tekst


# --- tijdelijke storingen ---------------------------------------------------


def test_een_verbroken_verbinding_wordt_opnieuw_geprobeerd() -> None:
    """Op 2026-08-30 verbrak GitHub de verbinding halverwege 386 repository's.

    Eén hik hoort geen repository te kosten. Twee pogingen en dan pas opgeven: langer doorgaan
    maakt een echte storing traag zichtbaar, en dat is erger dan een repository die in de dekking
    staat als niet-gelezen.
    """
    import requests

    from iso_audit.clients.forge import _haal

    class _Sessie:
        def __init__(self) -> None:
            self.pogingen = 0

        def get(self, url: str, timeout: int) -> object:
            self.pogingen += 1
            if self.pogingen == 1:
                raise requests.ConnectionError("Remote end closed connection")
            return _Antwoord(200)

    sessie = _Sessie()
    antwoord = _haal(sessie, "https://api.github.com/repos/x/y")  # type: ignore[arg-type]
    assert antwoord.status_code == 200
    assert sessie.pogingen == 2


def test_een_blijvende_storing_wordt_doorgegeven() -> None:
    """Eindeloos herhalen verbergt een echte storing achter traagheid."""
    import pytest
    import requests

    from iso_audit.clients.forge import _haal

    class _Kapot:
        def __init__(self) -> None:
            self.pogingen = 0

        def get(self, url: str, timeout: int) -> object:
            self.pogingen += 1
            raise requests.ConnectionError("blijft stuk")

    kapot = _Kapot()
    with pytest.raises(requests.RequestException):
        _haal(kapot, "https://api.github.com/repos/x/y")  # type: ignore[arg-type]
    assert kapot.pogingen == 2
