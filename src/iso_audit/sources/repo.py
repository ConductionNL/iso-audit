"""Repository-source-adapter — GitHub en Codeberg als auditbron.

Alle andere bronnen in dit tool zijn **documentbronnen**: wat de organisatie over zichzelf heeft
opgeschreven. Een repository is iets anders. §8.25 (veilige ontwikkeling), §8.28 (veilig
programmeren), §8.31 (scheiding ontwikkel/productie), §8.32 (wijzigingsbeheer), §8.9
(configuratiebeheer) en §8.4 (toegang tot broncode) gaan allemaal over dingen die daar zichtbaar
zijn en nergens anders aantoonbaar. Het vier-ogen-principe is geen belofte in een handboek maar
een schakelaar op een branch, met een geschiedenis eronder.

Gemeten op 2026-08-26 over de twaalf recentst gepushte actieve ConductionNL-repo's: zes van de
twaalf zonder `SECURITY.md`, zes zonder `CODEOWNERS`, nul met pre-commit — en **nul van de twaalf**
met een hoofdbranch die review verplicht stelt. Dat laatste is precies het soort bevinding
waarvoor deze bron bestaat.

Wat deze adapter *niet* doet:

- **Geen source-tree inlezen.** Een repository is geen documentmap; 700 bestanden leveren ruis,
  een run van uren en een dekking die niets zegt. Alleen :data:`BEWIJSPADEN`.
- **Geen namen.** Uitspraken over wijzigingen zijn aggregaten. Een NC gaat over een proces dat
  niet werkt, niet over een collega — dezelfde regel als in de review-prompt.
- **Geen git clone.** Dat betekent willekeurige bestanden op de schijf van een pod met
  `readOnlyRootFilesystem`, en code van buiten binnenhalen. De API's leveren wat we nodig hebben.
- **Geen schrijfrichting.** Het Source-protocol is read-only; schrijven gaat via een Sink.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass

import requests

from iso_audit.clients.forge import (
    CLIENTS,
    ForgeClient,
    ForgeError,
    GitHubClient,
    Repositoriegegevens,
    Wijzigingen,
)
from iso_audit.config.verbinding import normaliseer
from iso_audit.sources import register
from iso_audit.sources.base import Document, Finding

logger = logging.getLogger(__name__)

GITHUB_TOKEN_ENV = "REPO_GITHUB_TOKEN"
CODEBERG_TOKEN_ENV = "REPO_CODEBERG_TOKEN"
REPOS_ENV = "REPO_LOCATIES"
"""Komma-gescheiden `forge:eigenaar/naam`, bv. `github:ConductionNL/iso-audit`.

De komma is het opslagformaat van de env-var, niet iets dat een auditor intypt — in de UI staan
de repositories als losse rijen, net als de Drive-mappen en de Nextcloud-paden.

De pipeline bouwt een adapter zonder argumenten (`sources.get(naam)()`), dus dit is de weg waarlangs
de configuratie binnenkomt: het configuratiescherm schrijft de env-var via `Settings`."""

BEWIJSPADEN: tuple[str, ...] = (
    "README.md",
    "profile/README.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODEOWNERS",
    ".github/CODEOWNERS",
    "LICENSE",
    ".github/dependabot.yml",
    "renovate.json",
    ".pre-commit-config.yaml",
)
"""De bestanden die bewijs dragen — expliciet, geen glob-magie.

Kort en bekend, want dat is wat een repository aan bewijs oplevert: §5.2 rollen (CODEOWNERS),
§8.28 veilig programmeren (pre-commit, CONTRIBUTING), §8.8 kwetsbaarheden (dependabot/renovate)
en 9001 §7.5 gedocumenteerde informatie (README, LICENSE).

`profile/README.md` is het **org-profiel**: in de speciale repo `<org>/.github` staat de tekst
die GitHub op de organisatiepagina toont. Daar staat wat een organisatie over zichzelf zegt te
zijn en te maken, en dat is 9001 §4.1-materiaal. Tot 2026-08-26 stond `README.md` zelfs helemaal
niet in deze lijst terwijl de tekst hierboven al beweerde van wel."""

WORKFLOWMAPPEN_PREFIX: tuple[str, ...] = (".github/workflows/", ".forgejo/workflows/")
"""Geautomatiseerde poorten: §8.25 en §8.31. Beide forges, want de mapnaam verschilt."""

MAX_PR = 20
"""Over hoeveel recente pull requests wordt geaggregeerd.

Twintig en niet honderd: gemeten 0,45s per API-aanroep, en elke PR kost een extra aanroep voor
zijn reviews. Twintig is genoeg om een patroon te zien en houdt een repo onder de tien seconden.
Instelbaar via `REPO_MAX_PR` — een hardgecodeerde grens is niet te testen.

**Let op bij een hele organisatie.** Gemeten op 2026-08-26 telt ConductionNL 414 repository's
(385 actief). Zonder PR-aggregaat kost dat 1.540 aanroepen, ongeveer twaalf minuten. Mét, op 20,
wordt het 9.625 aanroepen en dat is bijna twee keer de limiet van 5.000 per uur. Zet `REPO_MAX_PR`
op 0 voor een org-brede run, of kies een handvol repository's."""

ALLE = "*"
"""Wildcard voor "alle repository's van deze eigenaar", bv. `github:ConductionNL/*`.

414 namen intypen is geen configuratie maar een overschrijffout die wacht om te gebeuren. De
scope wordt daarmee "alle repository's van deze organisatie op het moment van de run", en welke
dat waren komt in de dekking te staan — anders is achteraf niet te zeggen wat er geauditeerd is."""

MAX_BESTAND = 200_000
"""Tekens per opgehaald bestand. Een CODEOWNERS van 200 kB is geen bewijs maar een ongeluk."""


@dataclass(frozen=True, slots=True)
class RepoVerwijzing:
    """Eén geconfigureerde repository. De forge staat er expliciet bij."""

    forge: str
    eigenaar: str
    naam: str

    @property
    def sleutel(self) -> str:
        return f"{self.forge}:{self.eigenaar}/{self.naam}"


class RepoConfigError(Exception):
    """De repository-configuratie klopt niet."""


def lees_verwijzingen(ruw: list[dict[str, str]]) -> list[RepoVerwijzing]:
    """Valideer de geconfigureerde repositories.

    Een onbekende forge is een **fout** en geen stille overslag: afleiden uit de URL is precies de
    aanname die pas opvalt als iemand een spiegel gebruikt of er een derde forge bijkomt.
    """
    verwijzingen: list[RepoVerwijzing] = []
    for regel in ruw:
        forge = (regel.get("forge") or "").strip().lower()
        if forge not in CLIENTS:
            raise RepoConfigError(
                f"onbekende forge {forge!r}; kies uit {', '.join(sorted(CLIENTS))}"
            )
        eigenaar = (regel.get("eigenaar") or "").strip()
        naam = (regel.get("naam") or "").strip()
        if not eigenaar or not naam:
            raise RepoConfigError(f"repository zonder eigenaar of naam: {regel!r}")
        verwijzingen.append(RepoVerwijzing(forge=forge, eigenaar=eigenaar, naam=naam))
    return verwijzingen


def _app_credential() -> object | None:
    """De GitHub-App-credential, als de drie velden gezet zijn.

    Een App is eigendom van de organisatie en blijft werken als iemand vertrekt; een persoonlijk
    token niet. Daarom heeft dit voorrang. Ontbreekt één van de drie velden, dan is er geen App
    en valt het terug op het persoonlijke token — geen halve configuratie stil accepteren.
    """
    from iso_audit.clients import github_app

    app_id = os.environ.get(github_app.APP_ID_ENV, "").strip()
    installatie = os.environ.get(github_app.INSTALLATIE_ENV, "").strip()
    sleutel = os.environ.get(github_app.PRIVATE_KEY_ENV, "").strip()
    if not (app_id and installatie and sleutel):
        return None
    return github_app.AppCredential(app_id, installatie, sleutel)


def uit_tekst(ruw: str) -> list[dict[str, str]]:
    """Parseer `forge:eigenaar/naam` uit de env-var naar de configuratievorm.

    Strikt: een regel zonder forge of zonder `eigenaar/naam` is een fout en geen overslag. Een
    stil overgeslagen repository is een bron die de auditor dénkt te hebben.
    """
    regels: list[dict[str, str]] = []
    for stuk in (s.strip() for s in ruw.split(",")):
        if not stuk:
            continue
        forge, scheider, pad = stuk.partition(":")
        if not scheider or "/" not in pad:
            raise RepoConfigError(
                f"repository {stuk!r} moet de vorm forge:eigenaar/naam hebben, "
                "bijvoorbeeld github:ConductionNL/iso-audit"
            )
        eigenaar, _, naam = pad.partition("/")
        regels.append({"forge": forge.strip(), "eigenaar": eigenaar.strip(), "naam": naam.strip()})
    return regels


def metadata_tekst(gegevens: Repositoriegegevens, wijzigingen: Wijzigingen) -> str:
    """De repository-instellingen als leesbare tekst, zodat de classificatie ze kan wegen.

    Expliciet uitgeschreven en niet als JSON: de classificatie leest tekst, en een auditor die
    dit in het detailrapport terugziet moet het zonder toelichting begrijpen.

    "Niet vast te stellen" is een eigen uitkomst en wordt nooit als "niet ingesteld" geschreven.
    Een onbekende instelling als bevinding rapporteren is een verzonnen bevinding.
    """

    onbekend = gegevens.bescherming_reden or "niet vast te stellen met het gebruikte token"

    def ja_nee(waarde: bool | None, ja: str, nee: str) -> str:
        if waarde is None:
            return onbekend
        return ja if waarde else nee

    regels = [
        f"Repository {gegevens.naam} op {gegevens.forge}.",
        f"Zichtbaarheid: {'privé' if gegevens.prive else 'publiek'}.",
        f"Status: {'gearchiveerd' if gegevens.gearchiveerd else 'actief'}.",
        f"Hoofdbranch: {gegevens.hoofdbranch}.",
        "Branch-bescherming op de hoofdbranch: "
        + ja_nee(gegevens.branch_beschermd, "ingesteld", "niet ingesteld")
        + ".",
        "Verplichte review vóór samenvoegen: "
        + ja_nee(gegevens.review_verplicht, "ja", "nee")
        + ".",
    ]
    if wijzigingen.onbekend:
        regels.append(
            "Recente samenvoegingen: "
            + (wijzigingen.reden or "niet vast te stellen met het gebruikte token")
            + "."
        )
    elif wijzigingen.bekeken:
        regels.append(
            f"Van de laatste {wijzigingen.bekeken} samengevoegde wijzigingen zijn er "
            f"{wijzigingen.zonder_review} zonder goedkeurende review samengevoegd."
        )
    else:
        regels.append("Recente samenvoegingen: geen in het bekeken venster.")
    if gegevens.beschrijving:
        regels.append(f"Omschrijving: {gegevens.beschrijving}")
    return "\n".join(regels)


WORKFLOWSLEUTEL = ".github/workflows/"
"""Sleutel waaronder de workflowbestanden worden geaggregeerd.

Eindigt op een schuine streep zodat `bron_clausules.voor_repo_document` hem als workflowpad
herkent en aan §8.25, §8.31 en §8.32 koppelt."""

MAX_GENOEMD = 40
"""Hoeveel repository's er bij naam worden genoemd in een aggregaat.

Driehonderd namen op een rij leest niemand, en het aantal staat er toch bij. Wat afvalt wordt
geteld — stil weglaten zou van "in 258 repository's ontbreekt dit" een onbewijsbare bewering
maken."""


def _noem(namen: list[str]) -> str:
    """Een leesbare opsomming, met het aantal weggelaten namen erachter."""
    if not namen:
        return "geen"
    getoond = sorted(namen)[:MAX_GENOEMD]
    rest = len(namen) - len(getoond)
    return ", ".join(getoond) + (f" en {rest} andere" if rest else "")


def instellingen_tekst(repos: list[tuple[RepoVerwijzing, Repositoriegegevens]]) -> str:
    """De instellingen van álle repository's als één telling.

    "1 van de 3 repository's stelt review verplicht" is de bevinding; drie losse regels die elk
    hetzelfde zeggen, zijn dat niet. De repository's zónder worden bij naam genoemd, want daar
    gaat de bevinding over.
    """
    totaal = len(repos)
    zonder_review = [v.naam for v, g in repos if g.review_verplicht is False]
    met_review = [v.naam for v, g in repos if g.review_verplicht is True]
    onbekend = [v.naam for v, g in repos if g.review_verplicht is None]
    onbeschermd = [v.naam for v, g in repos if g.branch_beschermd is False]
    prive = [v.naam for v, g in repos if g.prive]

    regels = [
        f"Repository-instellingen over {totaal} repository(s).",
        "",
        f"Verplichte review vóór samenvoegen: {len(met_review)} van de {totaal}.",
        f"  Zonder verplichte review: {_noem(zonder_review)}.",
    ]
    if onbekend:
        regels.append(f"  Niet vast te stellen met het gebruikte token: {_noem(onbekend)}.")
    regels += [
        "",
        f"Branch-bescherming op de hoofdbranch: {totaal - len(onbeschermd) - len(onbekend)} "
        f"van de {totaal} ingesteld.",
        f"  Zonder bescherming: {_noem(onbeschermd)}.",
        "",
        f"Zichtbaarheid: {len(prive)} privé, {totaal - len(prive)} publiek.",
    ]
    return "\n".join(regels)


def bewijspad_tekst(pad: str, per_repo: dict[str, str], alle: list[str]) -> str:
    """Eén bewijssoort over alle repository's: hoeveel, welke niet, en welke inhoud.

    De inhoud gaat **ontdubbeld** mee. Honderdachtentwintig `SECURITY.md`-bestanden zijn in de
    praktijk een handvol varianten van hetzelfde sjabloon, en juist het verschil daartussen is
    wat een auditor wil zien — niet honderdachtentwintig keer dezelfde tekst.
    """
    aanwezig = sorted(per_repo)
    ontbreekt = sorted(set(alle) - set(aanwezig))
    varianten: dict[str, list[str]] = {}
    for naam, inhoud in per_repo.items():
        varianten.setdefault(inhoud.strip(), []).append(naam)

    regels = [
        f"{pad} over {len(alle)} repository(s).",
        "",
        f"Aanwezig in {len(aanwezig)} van de {len(alle)}.",
        f"  Ontbreekt in: {_noem(ontbreekt)}.",
        "",
        f"Inhoud ({len(varianten)} unieke variant(en)):",
    ]
    for i, (inhoud, namen) in enumerate(
        sorted(varianten.items(), key=lambda x: -len(x[1])), start=1
    ):
        regels += [
            "",
            f"--- variant {i}, in {len(namen)} repository(s) ({_noem(namen)}):",
            inhoud,
        ]
    return "\n".join(regels)


@register
class RepoSource:
    """Bron-adapter voor repositories op GitHub en Codeberg."""

    naam = "repo"

    def __init__(self, repositories: list[dict[str, str]] | str | None = None) -> None:
        ruw = repositories if repositories is not None else os.environ.get(REPOS_ENV, "")
        self._verwijzingen = lees_verwijzingen(ruw if isinstance(ruw, list) else uit_tekst(ruw))
        self._max_pr = int(os.environ.get("REPO_MAX_PR") or MAX_PR)
        self._clients: dict[str, ForgeClient] = {}
        self._gegevens: dict[str, Repositoriegegevens] = {}
        self.overgeslagen: dict[str, str] = {}
        """Wat er niet gelezen kon worden en waarom — gaat mee in de dekking."""
        self._repos: list[tuple[RepoVerwijzing, Repositoriegegevens]] = []
        self._inhoud: dict[str, dict[str, str]] = {}
        self._verzameld = False

    def _client(self, forge: str) -> ForgeClient:
        if forge in self._clients:
            return self._clients[forge]
        if forge == "github":
            # Rechtstreeks en niet via `CLIENTS`: alleen de GitHub-client kent een
            # App-credential, en via de registry-lookup is dat niet te typeren.
            self._clients[forge] = GitHubClient(
                token=os.environ.get(GITHUB_TOKEN_ENV, ""),
                credential=_app_credential(),
            )
        else:
            self._clients[forge] = CLIENTS[forge](token=os.environ.get(CODEBERG_TOKEN_ENV, ""))
        return self._clients[forge]

    def _uitgevouwen(self) -> list[RepoVerwijzing]:
        """Vervang elke `*` door de repository's die de forge noemt.

        De opgeloste lijst komt in de dekking. "Alle repository's van de organisatie" is een
        prima auditscope, maar alleen als achteraf vaststaat welke dat op dat moment waren.
        """
        uitgevouwen: list[RepoVerwijzing] = []
        for verwijzing in self._verwijzingen:
            if verwijzing.naam != ALLE:
                uitgevouwen.append(verwijzing)
                continue
            namen, reden = self._client(verwijzing.forge).repositories(verwijzing.eigenaar)
            if reden:
                self.overgeslagen[f"{verwijzing.forge}:{verwijzing.eigenaar}/*"] = reden
            logger.info(
                "Organisatie %s:%s leverde %d repository(s)",
                verwijzing.forge,
                verwijzing.eigenaar,
                len(namen),
            )
            uitgevouwen.extend(
                RepoVerwijzing(forge=verwijzing.forge, eigenaar=verwijzing.eigenaar, naam=n)
                for n in namen
            )
        return uitgevouwen

    def _verzamel(self) -> None:
        """Loop de repository's langs en leg per bewijssoort vast wat er is.

        Eén keer, in `list_documents`; `fetch_content` leest dan uit wat hier is verzameld. De
        alternatieve volgorde — per aggregaat opnieuw alle repository's langs — zou het werk zo
        vaak doen als er bewijssoorten zijn.
        """
        if self._verzameld:
            return
        self._verzameld = True
        for verwijzing in self._uitgevouwen():
            client = self._client(verwijzing.forge)
            # Netwerkfouten worden per repository afgevangen. Op 2026-08-30 verbrak GitHub de
            # verbinding na zeven minuten (`RemoteDisconnected`); die fout werd niet gevangen, dus
            # leverde de héle bron niets en brak de run af met "Bron(nen) leverden niets". Zeven
            # minuten ophalen, weg door één hik.
            #
            # Alles voor deze repository gebeurt binnen de `try`, en pas daarna wordt er iets
            # vastgelegd: een halve repository in het aggregaat zou een telling opleveren die
            # niemand kan navertellen. Wat mislukt komt in `overgeslagen` en dus in de dekking —
            # stil doorgaan zou een audit opleveren die iets beweert over wat niemand heeft
            # gelezen.
            try:
                gegevens = client.repository(verwijzing.eigenaar, verwijzing.naam)
                boom, reden = client.paden(verwijzing.eigenaar, verwijzing.naam)
                aanwezig = set(boom)
                inhoud = {
                    pad: client.bestand(verwijzing.eigenaar, verwijzing.naam, pad).inhoud[
                        :MAX_BESTAND
                    ]
                    for pad in BEWIJSPADEN
                    if pad in aanwezig
                }
            except ForgeError as fout:
                # Onze eigen tekst met de duiding erin ("bestaat niet, of het token mag het niet
                # zien (404)"); die hoort niet door de normalisatie, want dan wordt hij vervangen
                # door een algemene zin en is de auditor zijn diagnose kwijt.
                self.overgeslagen[verwijzing.sleutel] = str(fout)
                logger.warning("Repository niet gelezen: %s (%s)", verwijzing.sleutel, fout)
                continue
            except requests.RequestException as fout:
                # Wél normaliseren: dit is de melding van de bibliotheek en die kan een URL met
                # credential bevatten.
                soort, tekst = normaliseer(fout, bron=self.naam)
                self.overgeslagen[verwijzing.sleutel] = tekst
                logger.warning("Repository niet gelezen: %s (%s)", verwijzing.sleutel, soort)
                continue

            self._repos.append((verwijzing, gegevens))
            if reden:
                self.overgeslagen[f"{verwijzing.sleutel}:bestandslijst"] = reden
            for pad, bestandsinhoud in inhoud.items():
                self._inhoud.setdefault(pad, {})[verwijzing.naam] = bestandsinhoud
            workflows = [p for p in boom if p.startswith(WORKFLOWMAPPEN_PREFIX)]
            if workflows:
                self._inhoud.setdefault(WORKFLOWSLEUTEL, {})[verwijzing.naam] = "\n".join(workflows)

    def list_documents(self, filter: dict[str, object] | None = None) -> Iterator[Document]:
        """Eén document per bewijssoort over álle repository's, plus de instellingen.

        Niet één document per repository. Een auditor stelt zijn vraag per **maatregel** — "is
        het intellectueel eigendom geregeld?" — en het antwoord daarop is "95 van de 386
        repository's hebben een licentiebestand", niet vijfennegentig losse constateringen.

        Gemeten op 2026-08-29, vóór deze wijziging: 137 bevindingen uit repository's, waarvan 47
        op A.5.32 die allemaal hetzelfde zeiden. 1.369 modelaanroepen, $4,33.
        """
        self._verzamel()
        if not self._repos:
            return
        laatste = max((g.gewijzigd for _, g in self._repos if g.gewijzigd), default="")
        eigenaars = sorted({v.eigenaar for v, _ in self._repos})
        sleutel = f"{self._repos[0][0].forge}:{'+'.join(eigenaars)}"

        yield Document(
            id=f"{sleutel}#instellingen",
            titel=f"Repository-instellingen over {len(self._repos)} repository(s)",
            bron=self.naam,
            type="repository-instellingen",
            laatst_gewijzigd=laatste,
            inhoud_uri=f"{sleutel}#instellingen",
        )
        for pad in sorted(self._inhoud):
            yield Document(
                id=f"{sleutel}#{pad}",
                titel=f"{pad} over {len(self._repos)} repository(s)",
                bron=self.naam,
                type="repository-bestand",
                laatst_gewijzigd=laatste,
                inhoud_uri=f"{sleutel}#{pad}",
            )

    def fetch_content(self, doc: Document) -> str:
        if doc.bron != self.naam:
            raise ValueError(
                f"RepoSource krijgt document uit bron={doc.bron!r}, verwacht {self.naam!r}"
            )
        self._verzamel()
        _, _, pad = doc.inhoud_uri.partition("#")
        if pad == "instellingen":
            return instellingen_tekst(self._repos)
        return bewijspad_tekst(pad, self._inhoud.get(pad, {}), [v.naam for v, _ in self._repos])

    def list_findings(self, sessie_id: str) -> Iterator[Finding]:
        """Deze bron levert bewijs, geen kant-en-klare bevindingen."""
        return iter(())

    def healthcheck(self) -> dict[str, object]:
        if not self._verwijzingen:
            # `soort` meesturen is geen formaliteit: zonder dat veld haalt `_check_source`
            # de tekst door de normalisatie, en wordt "nog geen repositories ingevuld"
            # vervangen door "De verbinding kon niet worden gelegd. Zie het serverlog." Dat
            # wijst een auditor op een storing terwijl hij alleen nog niets heeft ingevuld.
            # Die normalisatie bestaat om adapter-tekst met credentials tegen te houden; deze
            # tekst is van ons en bevat er geen.
            return {
                "status": "niet_gekoppeld",
                "naam": self.naam,
                "soort": "niet_geconfigureerd",
                "reden": (
                    "Er zijn nog geen repositories ingevuld. Voeg ze toe als "
                    "forge:eigenaar/naam, bijvoorbeeld github:ConductionNL/iso-audit."
                ),
            }
        # Een ontbrekend token is een **waarschuwing** en geen fout: publieke repositories zijn
        # zonder token gewoon leesbaar — gemeten op 2026-08-26 tegen codeberg/nldesign. Wat er
        # dan níet uitkomt is de branch-bescherming, en die blijft eerlijk op "niet vast te
        # stellen" staan in plaats van als "niet ingesteld" te worden gerapporteerd.
        #
        # Bij GitHub komt er een tweede reden bij: zonder token 60 aanroepen per uur, en dat
        # loopt een run stuk op iets wat als "bron doet niets" leest.
        ontbrekend = sorted(
            {
                v.forge
                for v in self._verwijzingen
                if not os.environ.get(
                    GITHUB_TOKEN_ENV if v.forge == "github" else CODEBERG_TOKEN_ENV
                )
            }
        )
        gezondheid: dict[str, object] = {
            "status": "ok",
            "naam": self.naam,
            "locaties": [{"naam": v.sleutel} for v in self._verwijzingen],
        }
        if ontbrekend:
            gezondheid["waarschuwing"] = (
                f"geen token voor {', '.join(ontbrekend)}: publieke repositories worden gelezen, "
                "maar branch-bescherming blijft 'niet vast te stellen'"
                + (" en GitHub beperkt tot 60 aanroepen per uur" if "github" in ontbrekend else "")
            )
        return gezondheid
