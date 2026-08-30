"""Eén netwerkhikje mag zeven minuten werk niet weggooien.

Op 2026-08-30 viel de repo-ingest om na 386 repository's te hebben opgehaald:
`ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection
without response'))`. GitHub verbrak de verbinding halverwege, en omdat de fout niet werd
gevangen leverde de hele bron niets — waarna de run afbrak met "Bron(nen) leverden niets".

Zeven minuten ophalen, en dan alles kwijt door één hik. Een bron die honderden keren over het
netwerk gaat, moet daar tegen kunnen: wat mislukt komt in de dekking, de rest gaat door.

Wat níet gebeurt: stil doorgaan. Een repository die niet gelezen kon worden staat in
`overgeslagen`, want een audit die stilzwijgend een deel van zijn scope mist, is een audit die
iets beweert wat niet is gecontroleerd.
"""

from __future__ import annotations

import requests

from iso_audit.clients.forge import Bestand, Repositoriegegevens, Wijzigingen
from iso_audit.sources.repo import RepoSource


class _HaperendeForge:
    """Levert drie repository's; de tweede verbreekt de verbinding."""

    forge = "github"

    def __init__(self) -> None:
        self.gelezen: list[str] = []

    def repositories(self, eigenaar: str) -> tuple[list[str], str]:
        return ["een", "twee", "drie"], ""

    def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
        if naam == "twee":
            raise requests.ConnectionError("Remote end closed connection without response")
        self.gelezen.append(naam)
        return Repositoriegegevens(
            naam=f"{eigenaar}/{naam}",
            forge="github",
            url="",
            prive=False,
            gearchiveerd=False,
            hoofdbranch="main",
            gewijzigd="2026-08-30T08:00:00Z",
        )

    def paden(self, eigenaar: str, naam: str) -> tuple[list[str], str]:
        return ["LICENSE"], ""

    def bestand(self, eigenaar: str, naam: str, pad: str) -> Bestand:
        return Bestand(pad=pad, inhoud="EUPL-1.2")

    def bestanden_in_map(self, e: str, n: str, m: str) -> tuple[list[str], str]:
        return [], ""

    def wijzigingen(self, e: str, n: str, a: int) -> Wijzigingen:
        return Wijzigingen()


def _bron(client: object) -> RepoSource:
    bron = RepoSource([{"forge": "github", "eigenaar": "Org", "naam": "*"}])
    bron._clients["github"] = client  # type: ignore[assignment]
    return bron


def test_de_andere_repositories_worden_gewoon_gelezen() -> None:
    client = _HaperendeForge()
    docs = list(_bron(client).list_documents())
    assert docs, "de bron leverde niets terwijl twee van de drie leesbaar waren"
    assert client.gelezen == ["een", "drie"]


def test_de_mislukte_repository_komt_in_de_dekking() -> None:
    """Stil overslaan zou een audit opleveren die iets beweert wat niet is gecontroleerd."""
    bron = _bron(_HaperendeForge())
    list(bron.list_documents())
    assert any("twee" in sleutel for sleutel in bron.overgeslagen), bron.overgeslagen


def test_de_melding_noemt_de_netwerkfout_en_geen_lege_repository() -> None:
    bron = _bron(_HaperendeForge())
    list(bron.list_documents())
    reden = next(r for s, r in bron.overgeslagen.items() if "twee" in s)
    assert "bereikbaar" in reden or "verbinding" in reden.lower()


def test_het_aggregaat_telt_alleen_wat_gelezen_is() -> None:
    """ "2 van de 2" en niet "2 van de 3": over de derde weten we niets."""
    bron = _bron(_HaperendeForge())
    docs = list(bron.list_documents())
    tekst = bron.fetch_content(next(d for d in docs if d.inhoud_uri.endswith("#LICENSE")))
    assert "2 van de 2" in tekst, tekst.splitlines()[:4]


def test_een_bestandsfout_laat_de_rest_staan() -> None:
    """Ook bij het ophalen van de inhoud: één hik is geen reden om alles weg te gooien."""

    class _BestandHapert(_HaperendeForge):
        def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
            self.gelezen.append(naam)
            return Repositoriegegevens(
                naam=f"{eigenaar}/{naam}",
                forge="github",
                url="",
                prive=False,
                gearchiveerd=False,
                hoofdbranch="main",
                gewijzigd="2026-08-30T08:00:00Z",
            )

        def bestand(self, eigenaar: str, naam: str, pad: str) -> Bestand:
            if naam == "twee":
                raise requests.ConnectionError("hik")
            return Bestand(pad=pad, inhoud="EUPL-1.2")

    bron = _bron(_BestandHapert())
    docs = list(bron.list_documents())
    assert docs
    assert any("twee" in s for s in bron.overgeslagen), bron.overgeslagen
