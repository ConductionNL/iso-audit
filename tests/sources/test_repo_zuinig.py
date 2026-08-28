"""Een run over een hele organisatie past binnen de API-limiet.

Gemeten op 2026-08-28 voor de 385 actieve ConductionNL-repository's: de aanpak van dat moment
kostte **13.860 aanroepen** op een limiet van 5.000 per uur — bijna drie keer over. Twee
oorzaken, allebei fouten van mij:

1. **`REPO_MAX_PR=0` deed niet wat de hint beloofde.** GitHub negeert `per_page=0` en gebruikt
   zijn eigen default: gemeten kwamen er 21 pull requests terug, elk met een eigen
   review-aanroep. De hint zei "zet op 0 bij een hele organisatie" en de code deed het
   tegenovergestelde. Nu betekent 0: het aggregaat wordt overgeslagen, en dat staat ook in de
   instellingentekst zodat een lezer niet denkt dat er niets te vinden was.

2. **Elk bewijspad werd opgehaald, ook de niet-bestaande.** Tien vaste paden per repository,
   terwijl er gemiddeld vier bestaan. Eén `git/trees`-aanroep noemt alle paden in de repository,
   en daarna hoeft alleen wat er is te worden opgehaald.

Samen: van 36 naar 7 aanroepen per repository, ofwel 2.695 voor de hele organisatie — dat past,
en het duurt ongeveer twintig minuten.

Wat níet verandert: welke paden als bewijs tellen, en dat een ontbrekend pad een waarneming is.
Dat een `SECURITY.md` ontbreekt, is juist de bevinding — die informatie komt nu uit de boom in
plaats van uit een 404.
"""

from __future__ import annotations

import pytest

from iso_audit.clients.forge import Repositoriegegevens, Wijzigingen
from iso_audit.sources.repo import RepoSource, metadata_tekst


class _TellendeClient:
    """Telt aanroepen, zodat de kosten meetbaar zijn in plaats van geschat."""

    forge = "github"

    def __init__(self, boom: list[str] | None = None) -> None:
        self.aanroepen: list[str] = []
        self._boom = boom if boom is not None else ["README.md", "SECURITY.md"]

    def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
        self.aanroepen.append("repository")
        return Repositoriegegevens(
            naam=f"{eigenaar}/{naam}",
            forge="github",
            url="",
            prive=False,
            gearchiveerd=False,
            hoofdbranch="main",
        )

    def repositories(self, eigenaar: str) -> tuple[list[str], str]:
        self.aanroepen.append("repositories")
        return ["een"], ""

    def paden(self, eigenaar: str, naam: str) -> tuple[list[str], str]:
        self.aanroepen.append("paden")
        return list(self._boom), ""

    def bestand(self, eigenaar: str, naam: str, pad: str):
        from iso_audit.clients.forge import Bestand

        self.aanroepen.append(f"bestand:{pad}")
        return Bestand(pad=pad, inhoud="inhoud")

    def bestanden_in_map(self, eigenaar: str, naam: str, map_: str) -> tuple[list[str], str]:
        self.aanroepen.append("bestanden_in_map")
        return [], ""

    def wijzigingen(self, eigenaar: str, naam: str, aantal: int) -> Wijzigingen:
        # Spiegelt het contract van de echte client: bij `aantal <= 0` gaat er geen enkel
        # verzoek uit. Zou deze nepclient dat niet nadoen, dan telde de test een aanroep die in
        # werkelijkheid geen HTTP kost — en meet hij iets anders dan de limiet waar het om gaat.
        if aantal <= 0:
            return Wijzigingen(onbekend=True, reden="niet opgevraagd (ingesteld op 0)")
        self.aanroepen.append("wijzigingen")
        return Wijzigingen(bekeken=aantal)


def _bron(client: _TellendeClient, max_pr: str = "20") -> RepoSource:
    import os

    os.environ["REPO_MAX_PR"] = max_pr
    bron = RepoSource([{"forge": "github", "eigenaar": "ConductionNL", "naam": "iso-audit"}])
    bron._clients["github"] = client  # type: ignore[assignment]
    return bron


def test_de_boom_wordt_een_keer_opgehaald_in_plaats_van_elk_pad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tien vaste paden ophalen waarvan er vier bestaan, is zes aanroepen weggooien."""
    monkeypatch.setenv("REPO_MAX_PR", "20")
    client = _TellendeClient(boom=["README.md", "SECURITY.md"])
    bron = _bron(client)
    list(bron.list_documents())
    assert client.aanroepen.count("paden") == 1
    assert "bestanden_in_map" not in client.aanroepen


def test_alleen_bestaande_paden_worden_documenten(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_MAX_PR", "20")
    client = _TellendeClient(boom=["README.md", "SECURITY.md", "src/main.py"])
    docs = list(_bron(client).list_documents())
    paden = {d.inhoud_uri.split("#", 1)[1] for d in docs if d.type == "repository-bestand"}
    assert paden == {"README.md", "SECURITY.md"}, "alleen bewijspaden, en alleen bestaande"


def test_max_pr_nul_slaat_het_aggregaat_over(monkeypatch: pytest.MonkeyPatch) -> None:
    """GitHub negeert `per_page=0` en geeft er 21 terug — gemeten. Overslaan moet in onze code."""
    monkeypatch.setenv("REPO_MAX_PR", "0")
    client = _TellendeClient()
    bron = _bron(client, max_pr="0")
    docs = list(bron.list_documents())
    inst = next(d for d in docs if d.type == "repository-instellingen")
    bron.fetch_content(inst)
    assert "wijzigingen" not in client.aanroepen


def test_bij_nul_zegt_de_tekst_dat_er_niet_gekeken_is(monkeypatch: pytest.MonkeyPatch) -> None:
    """ "Geen samenvoegingen gevonden" en "we hebben niet gekeken" zijn niet hetzelfde."""
    tekst = metadata_tekst(
        Repositoriegegevens(
            naam="x/y",
            forge="github",
            url="",
            prive=False,
            gearchiveerd=False,
            hoofdbranch="main",
        ),
        Wijzigingen(onbekend=True, reden="niet opgevraagd (ingesteld op 0)"),
    )
    assert "niet opgevraagd" in tekst


def test_een_org_run_past_binnen_de_limiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """De hele reden van deze wijziging, als getal.

    385 repository's mogen niet meer dan 5.000 aanroepen kosten.
    """
    monkeypatch.setenv("REPO_MAX_PR", "0")
    client = _TellendeClient(boom=["README.md", "SECURITY.md", "LICENSE", "CODEOWNERS"])
    bron = _bron(client, max_pr="0")
    for doc in bron.list_documents():
        bron.fetch_content(doc)
    per_repo = len(client.aanroepen)
    assert per_repo * 385 < 5000, f"{per_repo} aanroepen per repo = {per_repo * 385} voor 385"
