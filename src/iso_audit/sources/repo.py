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

from iso_audit.clients.forge import (
    CLIENTS,
    Bestand,
    ForgeClient,
    ForgeError,
    Repositoriegegevens,
    Wijzigingen,
)
from iso_audit.sources import register
from iso_audit.sources.base import Document, Finding

logger = logging.getLogger(__name__)

GITHUB_TOKEN_ENV = "GITHUB_TOKEN"
CODEBERG_TOKEN_ENV = "CODEBERG_TOKEN"

BEWIJSPADEN: tuple[str, ...] = (
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
en 9001 §7.5 gedocumenteerde informatie (README, LICENSE)."""

WORKFLOWMAPPEN: tuple[str, ...] = (".github/workflows", ".forgejo/workflows")
"""Geautomatiseerde poorten: §8.25 en §8.31. Beide forges, want de mapnaam verschilt."""

MAX_PR = 20
"""Over hoeveel recente pull requests wordt geaggregeerd.

Twintig en niet honderd: gemeten 0,45s per API-aanroep, en elke PR kost een extra aanroep voor
zijn reviews. Twintig is genoeg om een patroon te zien en houdt een repo onder de tien seconden.
Instelbaar via `REPO_MAX_PR` — een hardgecodeerde grens is niet te testen."""

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


def metadata_tekst(gegevens: Repositoriegegevens, wijzigingen: Wijzigingen) -> str:
    """De repository-instellingen als leesbare tekst, zodat de classificatie ze kan wegen.

    Expliciet uitgeschreven en niet als JSON: de classificatie leest tekst, en een auditor die
    dit in het detailrapport terugziet moet het zonder toelichting begrijpen.

    "Niet vast te stellen" is een eigen uitkomst en wordt nooit als "niet ingesteld" geschreven.
    Een onbekende instelling als bevinding rapporteren is een verzonnen bevinding.
    """

    def ja_nee(waarde: bool | None, ja: str, nee: str) -> str:
        if waarde is None:
            return "niet vast te stellen met het gebruikte token"
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
        regels.append("Recente samenvoegingen: niet vast te stellen met het gebruikte token.")
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


@register
class RepoSource:
    """Bron-adapter voor repositories op GitHub en Codeberg."""

    naam = "repo"

    def __init__(self, repositories: list[dict[str, str]] | None = None) -> None:
        self._verwijzingen = lees_verwijzingen(repositories or [])
        self._max_pr = int(os.environ.get("REPO_MAX_PR") or MAX_PR)
        self._clients: dict[str, ForgeClient] = {}
        self._gegevens: dict[str, Repositoriegegevens] = {}

    def _client(self, forge: str) -> ForgeClient:
        if forge not in self._clients:
            token = os.environ.get(
                GITHUB_TOKEN_ENV if forge == "github" else CODEBERG_TOKEN_ENV, ""
            )
            self._clients[forge] = CLIENTS[forge](token=token)
        return self._clients[forge]

    def list_documents(self, filter: dict[str, object] | None = None) -> Iterator[Document]:
        """Per repository: één document met de instellingen, plus de aanwezige bewijspaden."""
        for verwijzing in self._verwijzingen:
            client = self._client(verwijzing.forge)
            try:
                gegevens = client.repository(verwijzing.eigenaar, verwijzing.naam)
            except ForgeError as fout:
                logger.warning("Repository niet gelezen: %s (%s)", verwijzing.sleutel, fout)
                continue
            self._gegevens[verwijzing.sleutel] = gegevens

            yield Document(
                id=f"{verwijzing.sleutel}#instellingen",
                titel=f"{gegevens.naam} — repository-instellingen",
                bron=self.naam,
                type="repository-instellingen",
                laatst_gewijzigd="",
                inhoud_uri=f"{verwijzing.sleutel}#instellingen",
            )
            for pad in self._paden(client, verwijzing):
                yield Document(
                    id=f"{verwijzing.sleutel}#{pad}",
                    titel=f"{gegevens.naam} — {pad}",
                    bron=self.naam,
                    type="repository-bestand",
                    laatst_gewijzigd="",
                    inhoud_uri=f"{verwijzing.sleutel}#{pad}",
                )

    def _paden(self, client: ForgeClient, verwijzing: RepoVerwijzing) -> list[str]:
        paden = list(BEWIJSPADEN)
        for map_ in WORKFLOWMAPPEN:
            paden.extend(client.bestanden_in_map(verwijzing.eigenaar, verwijzing.naam, map_))
        return paden

    def fetch_content(self, doc: Document) -> str:
        if doc.bron != self.naam:
            raise ValueError(
                f"RepoSource krijgt document uit bron={doc.bron!r}, verwacht {self.naam!r}"
            )
        sleutel, _, rest = doc.inhoud_uri.partition("#")
        forge, _, pad_repo = sleutel.partition(":")
        eigenaar, _, naam = pad_repo.partition("/")
        client = self._client(forge)

        if rest == "instellingen":
            gegevens = self._gegevens.get(sleutel) or client.repository(eigenaar, naam)
            return metadata_tekst(gegevens, client.wijzigingen(eigenaar, naam, self._max_pr))

        bestand: Bestand = client.bestand(eigenaar, naam, rest)
        if not bestand.aanwezig:
            # Een ontbrekend bewijspad is een waarneming en geen fout: "er is geen SECURITY.md"
            # is precies wat een auditor wil weten.
            return f"Het bestand {rest} bestaat niet in {eigenaar}/{naam} ({bestand.reden})."
        return bestand.inhoud[:MAX_BESTAND]

    def list_findings(self, sessie_id: str) -> Iterator[Finding]:
        """Deze bron levert bewijs, geen kant-en-klare bevindingen."""
        return iter(())

    def healthcheck(self) -> dict[str, object]:
        if not self._verwijzingen:
            return {
                "status": "niet_gekoppeld",
                "naam": self.naam,
                "reden": "geen repositories geconfigureerd",
            }
        ontbrekend = sorted(
            {
                v.forge
                for v in self._verwijzingen
                if not os.environ.get(
                    GITHUB_TOKEN_ENV if v.forge == "github" else CODEBERG_TOKEN_ENV
                )
            }
        )
        if ontbrekend:
            return {
                "status": "fout",
                "naam": self.naam,
                "reden": f"geen token voor: {', '.join(ontbrekend)}",
            }
        return {
            "status": "ok",
            "naam": self.naam,
            "locaties": [{"naam": v.sleutel} for v in self._verwijzingen],
        }
