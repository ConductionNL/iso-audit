"""De repository-bron: bewijs uit de forge, met scherpe grenzen.

Alle andere bronnen zijn documentbronnen — wat de organisatie over zichzelf heeft opgeschreven.
Een repository is de plek waar §8.4, §8.9, §8.25, §8.28, §8.31 en §8.32 zichtbaar zijn en nergens
anders aantoonbaar.

Gemeten op 2026-08-26 over de twaalf recentst gepushte actieve ConductionNL-repo's: zes zonder
`SECURITY.md`, zes zonder `CODEOWNERS`, nul met pre-commit, en **nul van de twaalf** met een
hoofdbranch die review verplicht stelt.

Wat hier bewaakt wordt zijn de grenzen. Elke grens die wegvalt, maakt van deze bron iets anders
dan een auditbron: een crawler, een namenlijst, of een schrijvende integratie.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from iso_audit.clients import forge
from iso_audit.clients.forge import Bestand, Repositoriegegevens, Wijzigingen
from iso_audit.sources.repo import (
    BEWIJSPADEN,
    RepoConfigError,
    RepoSource,
    lees_verwijzingen,
    metadata_tekst,
)

# --- configuratie -----------------------------------------------------------


def test_de_forge_moet_expliciet_worden_benoemd() -> None:
    """Afleiden uit de URL is de aanname die pas opvalt bij een spiegel of een derde forge."""
    with pytest.raises(RepoConfigError, match="onbekende forge"):
        lees_verwijzingen([{"eigenaar": "ConductionNL", "naam": "iso-audit"}])


def test_een_onbekende_forge_is_een_fout_en_geen_overslag() -> None:
    with pytest.raises(RepoConfigError, match="gitlab"):
        lees_verwijzingen([{"forge": "gitlab", "eigenaar": "x", "naam": "y"}])


def test_beide_forges_in_een_configuratie() -> None:
    """De website-code staat op Codeberg en de rest op GitHub; één forge is niet genoeg."""
    verwijzingen = lees_verwijzingen(
        [
            {"forge": "github", "eigenaar": "ConductionNL", "naam": "iso-audit"},
            {"forge": "codeberg", "eigenaar": "conduction", "naam": "website"},
        ]
    )
    assert [v.sleutel for v in verwijzingen] == [
        "github:ConductionNL/iso-audit",
        "codeberg:conduction/website",
    ]


def test_een_repository_zonder_naam_wordt_geweigerd() -> None:
    with pytest.raises(RepoConfigError, match="eigenaar of naam"):
        lees_verwijzingen([{"forge": "github", "eigenaar": "ConductionNL"}])


# --- read-only --------------------------------------------------------------


@pytest.mark.parametrize("client", ["GitHubClient", "CodebergClient"])
def test_de_clients_schrijven_nergens(client: str) -> None:
    """Het Source-protocol is read-only; schrijven gaat via een Sink.

    Deze test kijkt naar de broncode en niet naar gedrag, want een schrijf-aanroep die er per
    ongeluk in komt, wordt in een unit-test met nepantwoorden niet zichtbaar.
    """
    bron = inspect.getsource(getattr(forge, client))
    for methode in (".post(", ".put(", ".patch(", ".delete("):
        assert methode not in bron, f"{client} bevat {methode}"


def test_de_module_haalt_niets_binnen_via_git() -> None:
    """Een clone betekent willekeurige bestanden op de schijf van een read-only pod."""
    bron = Path("src/iso_audit/sources/repo.py").read_text(encoding="utf-8")
    for verdacht in ("git clone", "subprocess", "os.system"):
        assert verdacht not in bron.replace("Geen git clone", ""), verdacht


# --- geen personen ----------------------------------------------------------


def test_de_instellingstekst_noemt_aantallen_en_geen_namen() -> None:
    """Een NC gaat over een proces dat niet werkt, niet over een collega."""
    tekst = metadata_tekst(
        Repositoriegegevens(
            naam="ConductionNL/iso-audit",
            forge="github",
            url="https://github.com/ConductionNL/iso-audit",
            prive=False,
            gearchiveerd=False,
            hoofdbranch="main",
            branch_beschermd=False,
            review_verplicht=False,
        ),
        Wijzigingen(bekeken=20, zonder_review=4),
    )
    assert "4 zonder goedkeurende review" in tekst
    assert "20" in tekst


def test_niet_vast_te_stellen_is_iets_anders_dan_niet_ingesteld() -> None:
    """Een onbekende instelling als bevinding rapporteren is een verzonnen bevinding."""
    tekst = metadata_tekst(
        Repositoriegegevens(
            naam="x/y",
            forge="github",
            url="",
            prive=True,
            gearchiveerd=False,
            hoofdbranch="main",
            branch_beschermd=None,
            review_verplicht=None,
        ),
        Wijzigingen(onbekend=True),
    )
    assert tekst.count("niet vast te stellen") == 3
    assert "niet ingesteld" not in tekst


def test_de_instellingstekst_meldt_ontbrekende_bescherming() -> None:
    """Nul van de twaalf repo's had dit op 2026-08-26; dat moet leesbaar in het bewijs staan."""
    tekst = metadata_tekst(
        Repositoriegegevens(
            naam="x/y",
            forge="github",
            url="",
            prive=False,
            gearchiveerd=False,
            hoofdbranch="main",
            branch_beschermd=False,
            review_verplicht=False,
        ),
        Wijzigingen(bekeken=0),
    )
    assert "niet ingesteld" in tekst
    assert "Verplichte review vóór samenvoegen: nee" in tekst


# --- geen source-tree -------------------------------------------------------


def test_de_bewijspaden_zijn_kort_en_expliciet() -> None:
    """Zevenhonderd bestanden inlezen levert ruis, uren en een dekking die niets zegt."""
    assert len(BEWIJSPADEN) <= 12
    assert "SECURITY.md" in BEWIJSPADEN
    assert "CODEOWNERS" in BEWIJSPADEN
    assert not any("*" in p for p in BEWIJSPADEN), "geen glob-magie"


# --- health -----------------------------------------------------------------


def test_zonder_repositories_is_de_bron_niet_gekoppeld() -> None:
    assert RepoSource().healthcheck()["status"] == "niet_gekoppeld"


def test_zonder_token_werkt_de_bron_maar_waarschuwt_hij(monkeypatch: pytest.MonkeyPatch) -> None:
    """Publieke repositories zijn zonder token leesbaar — gemeten tegen codeberg/nldesign.

    "Fout" zou hier onwaar zijn en de auditor laten denken dat de bron niets doet. Wat er wél
    ontbreekt is de branch-bescherming, en die blijft eerlijk op "niet vast te stellen" staan.
    """
    monkeypatch.delenv("REPO_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("REPO_CODEBERG_TOKEN", raising=False)
    gezondheid = RepoSource([{"forge": "github", "eigenaar": "x", "naam": "y"}]).healthcheck()
    assert gezondheid["status"] == "ok"
    assert "geen token voor github" in str(gezondheid["waarschuwing"])
    assert "niet vast te stellen" in str(gezondheid["waarschuwing"])


def test_met_token_waarschuwt_de_health_niet(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REPO_GITHUB_TOKEN", "geheim")
    gezondheid = RepoSource([{"forge": "github", "eigenaar": "x", "naam": "y"}]).healthcheck()
    assert "waarschuwing" not in gezondheid


def test_de_bron_levert_geen_kant_en_klare_bevindingen() -> None:
    """Deze bron levert bewijs; de classificatie weegt het."""
    assert list(RepoSource().list_findings("sessie-1")) == []


# --- configuratie uit de omgeving -------------------------------------------


def test_de_pipeline_kan_de_bron_zonder_argumenten_bouwen(monkeypatch: pytest.MonkeyPatch) -> None:
    """`sources.get(naam)()` geeft geen argumenten mee; de env-var is de weg naar binnen."""
    monkeypatch.setenv(
        "REPO_LOCATIES",
        "github:ConductionNL/iso-audit, codeberg:conduction/conduction-website",
    )
    gezondheid = RepoSource().healthcheck()
    assert [x["naam"] for x in gezondheid["locaties"]] == [  # type: ignore[index,union-attr]
        "github:ConductionNL/iso-audit",
        "codeberg:conduction/conduction-website",
    ]


def test_een_regel_zonder_forge_is_een_fout() -> None:
    """Een stil overgeslagen repository is een bron die de auditor dénkt te hebben."""
    from iso_audit.sources.repo import uit_tekst

    with pytest.raises(RepoConfigError, match="forge:eigenaar/naam"):
        uit_tekst("ConductionNL/iso-audit")


def test_een_regel_zonder_eigenaar_is_een_fout() -> None:
    from iso_audit.sources.repo import uit_tekst

    with pytest.raises(RepoConfigError, match="forge:eigenaar/naam"):
        uit_tekst("github:iso-audit")


# --- wat niet gelezen kon worden, zegt waarom -------------------------------


def test_de_instellingstekst_noemt_de_reden_uit_de_forge() -> None:
    """Niet een vaste zin, maar wat er werkelijk misging — 401, 403 of een limiet."""
    tekst = metadata_tekst(
        Repositoriegegevens(
            naam="x/y",
            forge="github",
            url="",
            prive=False,
            gearchiveerd=False,
            hoofdbranch="main",
            branch_beschermd=None,
            review_verplicht=None,
            bescherming_reden="het token mist het recht hiervoor (403)",
        ),
        Wijzigingen(onbekend=True, reden="de API-limiet is bereikt (60 aanroepen per uur)"),
    )
    assert "403" in tekst
    assert "API-limiet" in tekst


def test_een_onleesbare_workflowmap_komt_in_de_dekking() -> None:
    """ "Geen workflows" en "ik mocht de map niet lezen" zien er anders identiek uit."""

    class _Client:
        forge = "github"

        def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
            return Repositoriegegevens(
                naam=f"{eigenaar}/{naam}",
                forge="github",
                url="",
                prive=False,
                gearchiveerd=False,
                hoofdbranch="main",
            )

        def bestand(self, eigenaar: str, naam: str, pad: str) -> object:
            raise AssertionError("niet nodig voor deze test")

        def paden(self, eigenaar: str, naam: str) -> tuple[list[str], str]:
            return [], "het token mist het recht hiervoor (403)"

        def bestanden_in_map(self, eigenaar: str, naam: str, map_: str) -> tuple[list[str], str]:
            return [], "het token mist het recht hiervoor (403)"

        def wijzigingen(self, eigenaar: str, naam: str, aantal: int) -> Wijzigingen:
            return Wijzigingen()

    bron = RepoSource([{"forge": "github", "eigenaar": "x", "naam": "y"}])
    bron._clients["github"] = _Client()  # type: ignore[assignment]
    list(bron.list_documents())
    assert bron.overgeslagen
    assert all("403" in r for r in bron.overgeslagen.values())


def test_een_onleesbare_repository_komt_in_de_dekking() -> None:
    """Een hele repository die stil wegvalt is erger dan een die er niet in zat.

    Gevonden door de proefrun van 2026-08-26: `ConductionNL/hydra` is privé en gaf zonder token
    een 404. De repo verdween uit de audit met alleen een logregel — dan denkt de auditor hem
    geauditeerd te hebben.
    """
    from iso_audit.clients.forge import ForgeError

    class _Weigert:
        forge = "github"

        def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
            raise ForgeError("bestaat niet, of het token mag het niet zien (404)")

        def bestand(self, eigenaar: str, naam: str, pad: str) -> Bestand:
            return Bestand(pad=pad, inhoud="inhoud")

        def paden(self, eigenaar: str, naam: str) -> tuple[list[str], str]:
            return [], ""

        def bestanden_in_map(self, eigenaar: str, naam: str, map_: str) -> tuple[list[str], str]:
            return [], ""

        def wijzigingen(self, eigenaar: str, naam: str, aantal: int) -> Wijzigingen:
            return Wijzigingen()

    bron = RepoSource([{"forge": "github", "eigenaar": "ConductionNL", "naam": "hydra"}])
    bron._clients["github"] = _Weigert()  # type: ignore[assignment]
    assert list(bron.list_documents()) == []
    assert "github:ConductionNL/hydra" in bron.overgeslagen
    assert "404" in bron.overgeslagen["github:ConductionNL/hydra"]


def test_de_readme_en_het_org_profiel_staan_in_de_bewijspaden() -> None:
    """De docstring beweerde dat README meetelde; de lijst had hem niet."""
    assert "README.md" in BEWIJSPADEN
    assert "profile/README.md" in BEWIJSPADEN


# --- een hele organisatie ---------------------------------------------------


def test_een_ster_staat_voor_alle_repositories_van_de_eigenaar() -> None:
    """414 namen intypen is geen configuratie maar een overschrijffout die wacht."""
    verwijzingen = lees_verwijzingen([{"forge": "github", "eigenaar": "ConductionNL", "naam": "*"}])
    assert verwijzingen[0].sleutel == "github:ConductionNL/*"


class _OrgClient:
    forge = "github"

    def __init__(self, namen: list[str], reden: str = "") -> None:
        self._namen = namen
        self._reden = reden

    def repositories(self, eigenaar: str) -> tuple[list[str], str]:
        return self._namen, self._reden

    def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
        return Repositoriegegevens(
            naam=f"{eigenaar}/{naam}",
            forge="github",
            url="",
            prive=False,
            gearchiveerd=False,
            hoofdbranch="main",
        )

    def bestand(self, eigenaar: str, naam: str, pad: str) -> Bestand:
        return Bestand(pad=pad, inhoud="inhoud")

    def paden(self, eigenaar: str, naam: str) -> tuple[list[str], str]:
        return ["README.md"], ""

    def bestanden_in_map(self, eigenaar: str, naam: str, map_: str) -> tuple[list[str], str]:
        return [], ""

    def wijzigingen(self, eigenaar: str, naam: str, aantal: int) -> Wijzigingen:
        return Wijzigingen()


def _bron_met(namen: list[str], reden: str = "") -> RepoSource:
    bron = RepoSource([{"forge": "github", "eigenaar": "ConductionNL", "naam": "*"}])
    bron._clients["github"] = _OrgClient(namen, reden)  # type: ignore[assignment]
    return bron


def test_de_ster_wordt_uitgevouwen_tot_echte_repositories() -> None:
    """De uitvouwing levert één instellingendocument over álle repository's.

    Niet één per repository: sinds 2026-08-29 aggregeert de bron per maatregel, omdat
    vijfennegentig losse constateringen "deze repository heeft een licentiebestand" geen bewijs
    zijn maar één constatering over vijfennegentig repository's.
    """
    docs = list(_bron_met(["iso-audit", "hydra"]).list_documents())
    instellingen = [d for d in docs if d.type == "repository-instellingen"]
    assert len(instellingen) == 1
    assert "2 repository(s)" in instellingen[0].titel


def test_gearchiveerde_repositories_worden_gemeld() -> None:
    """Ze vallen af omdat ze tonen hoe er ooit gewerkt werd — maar stil weglaten mag niet."""
    bron = _bron_met(["iso-audit"], "29 gearchiveerde repository(s) overgeslagen")
    list(bron.list_documents())
    assert "29 gearchiveerde" in bron.overgeslagen["github:ConductionNL/*"]


def test_een_lege_organisatie_levert_geen_documenten() -> None:
    assert list(_bron_met([]).list_documents()) == []
