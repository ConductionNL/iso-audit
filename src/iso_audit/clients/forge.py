"""HTTP-clients voor GitHub en Codeberg — alleen ophalen en veldvertaling.

De grens is scherp en dat is met opzet: een client doet HTTP en vertaalt JSON-velden naar
:class:`Repositoriegegevens`, en **niets** wat met de norm te maken heeft. Welke paden bewijs
dragen en hoe branch-protectie zich verhoudt tot het vier-ogen-principe, staat in
`sources/repo.py`.

Waarom één adapter met twee clients en niet twee adapters — tegen de huisregel "liever herhaling
dan abstractie" in: wat verschilt is de HTTP-aanroep, wat níet verschilt is de auditinhoud. Die
logica twee keer neerzetten laat haar uiteenlopen, en dan levert het tool per forge ander bewijs
zonder dat iemand het merkt. Zie `openspec/changes/code-en-website-bronnen/design.md`.

Codeberg draait Forgejo, dat een Gitea-compatibele API heeft; de twee clients zijn daarmee
vergelijkbaar van omvang.

Read-only. Er staat hier geen enkele POST, PUT, PATCH of DELETE, en `tests/sources/test_repo.py`
faalt zodra dat verandert.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 20
"""Seconden per aanroep. Gemeten 2026-08-26: een GitHub-aanroep duurt 0,45s, dus dit is ruim —
maar een bron zonder timeout laat een run eindeloos hangen op een trage forge."""


@dataclass(frozen=True, slots=True)
class Repositoriegegevens:
    """Wat een forge over één repository vertelt, bron-onafhankelijk.

    Alles hierin is een feit van de forge. De weging ervan gebeurt elders.
    """

    naam: str
    forge: str
    url: str
    prive: bool
    gearchiveerd: bool
    hoofdbranch: str
    beschrijving: str = ""
    review_verplicht: bool | None = None
    """`None` betekent: niet vast te stellen met dit token, en dat is iets anders dan `False`.
    Een onbekende instelling als "niet beschermd" rapporteren is een verzonnen bevinding."""
    branch_beschermd: bool | None = None
    bescherming_reden: str = ""
    """Waarom de bescherming niet vast te stellen was."""


@dataclass(frozen=True, slots=True)
class Wijzigingen:
    """Aggregaat over recente pull requests. Nooit personen — zie de spec."""

    bekeken: int = 0
    zonder_review: int = 0
    onbekend: bool = False
    """Kon niet worden vastgesteld; dan is 0-van-0 misleidend."""
    reden: str = ""
    """Waarom niet — inclusief of het aan het token lag."""


@dataclass
class Bestand:
    """Eén opgehaald bewijsbestand."""

    pad: str
    inhoud: str = ""
    aanwezig: bool = True
    reden: str = ""
    _extra: dict[str, Any] = field(default_factory=dict)


class ForgeClient(Protocol):
    """Wat `sources/repo.py` van een forge nodig heeft."""

    forge: str

    def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens: ...
    def repositories(self, eigenaar: str) -> tuple[list[str], str]: ...
    def bestand(self, eigenaar: str, naam: str, pad: str) -> Bestand: ...
    def bestanden_in_map(self, eigenaar: str, naam: str, map_: str) -> tuple[list[str], str]: ...
    def wijzigingen(self, eigenaar: str, naam: str, aantal: int) -> Wijzigingen: ...


class ForgeError(Exception):
    """De forge antwoordde niet zoals verwacht."""


def duiding(antwoord: Any) -> str:
    """Waarom deze aanroep niets opleverde, in auditor-taal.

    Een bron die stilzwijgend niets teruggeeft, laat "geen workflows gevonden" en "ik mocht de
    workflowmap niet lezen" er identiek uitzien. Het eerste is een bevinding, het tweede een gat
    in de dekking.

    De 404 is bewust dubbelzinnig geformuleerd: GitHub geeft die óók terug voor iets dat je niet
    mág zien. Dat wegpoetsen tot "bestaat niet" zou een rechtenprobleem als bevinding
    presenteren.
    """
    status = int(getattr(antwoord, "status_code", 0))
    koppen = getattr(antwoord, "headers", {}) or {}
    if status == 401:
        return (
            "het token is niet meegestuurd of niet geldig (401); zonder geldig token is dit "
            "niet te lezen"
        )
    if status == 403:
        resterend = str(koppen.get("x-ratelimit-remaining", "")).strip()
        if resterend == "0":
            limiet = str(koppen.get("x-ratelimit-limit", "?"))
            return (
                f"de API-limiet is bereikt ({limiet} aanroepen per uur); zonder token is die 60, "
                "met token 5000"
            )
        return (
            "het token mist het recht hiervoor (403) — voor branch-bescherming is dat "
            "'Administration: read'"
        )
    if status == 404:
        return "bestaat niet, of het token mag het niet zien (404) — GitHub geeft beide zo terug"
    return f"de forge gaf een onverwacht antwoord ({status})"


def _haal(sessie: requests.Session, url: str) -> requests.Response:
    logger.debug("forge-GET %s", url)
    return sessie.get(url, timeout=TIMEOUT)


class GitHubClient:
    """GitHub via de REST-API v3."""

    forge = "github"
    basis = "https://api.github.com"

    def __init__(self, token: str = "", basis: str = "", credential: object | None = None) -> None:
        self.basis = basis or self.basis
        self._sessie = requests.Session()
        self._sessie.headers.update({"Accept": "application/vnd.github+json"})
        # Een App-credential heeft voorrang op een persoonlijk token: een PAT hangt aan één
        # persoon en valt stil als die vertrekt, en dan staat er in de volgende audit "bron niet
        # beschikbaar" waar bewijs had moeten staan. Het token wordt per aanroep opgehaald omdat
        # een installatietoken maar een uur leeft; `AppCredential` cachet het zelf.
        self._credential = credential
        if not credential and token:
            self._sessie.headers["Authorization"] = f"Bearer {token}"

    def _get(self, pad: str) -> requests.Response:
        """Elke GET loopt hierlangs, zodat de Authorization-kop nooit vergeten kan worden.

        Eerder stond die kop-actie in elke methode los. Dat werkt tot iemand een methode
        toevoegt en het vergeet — en dan valt de App-authenticatie stil op één plek, wat als
        "geen rechten" leest. Eén doorgang is een eigenschap in plaats van een afspraak.
        """
        if self._credential is not None:
            token = self._credential.token()  # type: ignore[attr-defined]
            self._sessie.headers["Authorization"] = f"Bearer {token}"
        return _haal(self._sessie, f"{self.basis}{pad}")

    def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
        antwoord = self._get(f"/repos/{eigenaar}/{naam}")
        if antwoord.status_code != 200:
            raise ForgeError(f"github {eigenaar}/{naam}: {duiding(antwoord)}")
        d = antwoord.json()
        branch = d.get("default_branch") or "main"
        beschermd, review, reden = self._bescherming(eigenaar, naam, branch)
        return Repositoriegegevens(
            naam=f"{eigenaar}/{naam}",
            forge=self.forge,
            url=d.get("html_url", ""),
            prive=bool(d.get("private")),
            gearchiveerd=bool(d.get("archived")),
            hoofdbranch=branch,
            beschrijving=d.get("description") or "",
            branch_beschermd=beschermd,
            review_verplicht=review,
            bescherming_reden=reden,
        )

    def _bescherming(
        self, eigenaar: str, naam: str, branch: str
    ) -> tuple[bool | None, bool | None, str]:
        """404 = geen bescherming; 403 = geen recht om het te zien, en dat is niet hetzelfde."""
        antwoord = self._get(f"/repos/{eigenaar}/{naam}/branches/{branch}/protection")
        if antwoord.status_code == 404:
            # Met voldoende rechten betekent 404 hier echt "geen bescherming ingesteld".
            return False, False, ""
        if antwoord.status_code != 200:
            return None, None, duiding(antwoord)
        d = antwoord.json()
        return True, bool(d.get("required_pull_request_reviews")), ""

    def repositories(self, eigenaar: str) -> tuple[list[str], str]:
        """Alle niet-gearchiveerde repositories van een organisatie.

        Gearchiveerde vallen af: die tonen hoe er ooit gewerkt werd, niet hoe er nu gewerkt
        wordt, en een audit gaat over het heden. Hoeveel er afvielen komt in de dekking.
        """
        namen: list[str] = []
        gearchiveerd = 0
        for pagina in range(1, 11):
            antwoord = self._get(f"/orgs/{eigenaar}/repos?per_page=100&page={pagina}")
            if antwoord.status_code != 200:
                return namen, duiding(antwoord)
            blok = antwoord.json()
            if not blok:
                break
            for repo in blok:
                if repo.get("archived"):
                    gearchiveerd += 1
                    continue
                namen.append(str(repo.get("name", "")))
        reden = f"{gearchiveerd} gearchiveerde repository(s) overgeslagen" if gearchiveerd else ""
        return namen, reden

    def bestand(self, eigenaar: str, naam: str, pad: str) -> Bestand:
        antwoord = self._get(f"/repos/{eigenaar}/{naam}/contents/{pad}")
        if antwoord.status_code == 404:
            # Hier bewust "bestaat niet" zonder tokenvoorbehoud: dit pad wordt alleen opgehaald
            # nadat `repository()` 200 gaf, dus de repo is leesbaar en contents kennen geen
            # rechten per pad. Een 404 is dan echte afwezigheid — en juist dát is de bevinding
            # (6 van 12 repo's zonder SECURITY.md, gemeten 2026-08-26).
            return Bestand(pad=pad, aanwezig=False, reden="bestaat niet")
        if antwoord.status_code != 200:
            return Bestand(pad=pad, aanwezig=False, reden=duiding(antwoord))
        return Bestand(pad=pad, inhoud=_decodeer(antwoord.json()))

    def bestanden_in_map(self, eigenaar: str, naam: str, map_: str) -> tuple[list[str], str]:
        """De bestanden in een map, plus waarom er geen zijn.

        Een map die niet gelezen mócht worden ziet er anders uit dan een lege map, en dat
        verschil hoort in de dekking terecht te komen. 404 is hier geen fout: veel repo's
        hebben simpelweg geen workflows.
        """
        antwoord = self._get(f"/repos/{eigenaar}/{naam}/contents/{map_}")
        if antwoord.status_code == 404:
            return [], ""
        if antwoord.status_code != 200:
            return [], duiding(antwoord)
        d = antwoord.json()
        if not isinstance(d, list):
            return [], ""
        return [str(x.get("path", "")) for x in d if x.get("type") == "file"], ""

    def wijzigingen(self, eigenaar: str, naam: str, aantal: int) -> Wijzigingen:
        """Aggregaat over de laatste gesloten pull requests. Geen namen — zie de spec."""
        antwoord = self._get(f"/repos/{eigenaar}/{naam}/pulls?state=closed&per_page={aantal}")
        if antwoord.status_code != 200:
            return Wijzigingen(onbekend=True, reden=duiding(antwoord))
        gemerged = [p for p in antwoord.json() if p.get("merged_at")]
        zonder = 0
        for pr in gemerged:
            nummer = pr.get("number")
            rev = self._get(f"/repos/{eigenaar}/{naam}/pulls/{nummer}/reviews")
            if rev.status_code != 200:
                return Wijzigingen(onbekend=True, reden=duiding(rev))
            if not [r for r in rev.json() if r.get("state") == "APPROVED"]:
                zonder += 1
        return Wijzigingen(bekeken=len(gemerged), zonder_review=zonder)


class CodebergClient:
    """Codeberg draait Forgejo; de API is Gitea-compatibel."""

    forge = "codeberg"
    basis = "https://codeberg.org/api/v1"

    def __init__(self, token: str = "", basis: str = "") -> None:
        self.basis = basis or self.basis
        self._sessie = requests.Session()
        if token:
            self._sessie.headers["Authorization"] = f"token {token}"

    def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
        antwoord = _haal(self._sessie, f"{self.basis}/repos/{eigenaar}/{naam}")
        if antwoord.status_code != 200:
            raise ForgeError(f"codeberg {eigenaar}/{naam}: {duiding(antwoord)}")
        d = antwoord.json()
        branch = d.get("default_branch") or "main"
        beschermd, review, reden = self._bescherming(eigenaar, naam, branch)
        return Repositoriegegevens(
            naam=f"{eigenaar}/{naam}",
            forge=self.forge,
            url=d.get("html_url", ""),
            prive=bool(d.get("private")),
            gearchiveerd=bool(d.get("archived")),
            hoofdbranch=branch,
            beschrijving=d.get("description") or "",
            branch_beschermd=beschermd,
            review_verplicht=review,
            bescherming_reden=reden,
        )

    def _bescherming(
        self, eigenaar: str, naam: str, branch: str
    ) -> tuple[bool | None, bool | None, str]:
        antwoord = _haal(
            self._sessie, f"{self.basis}/repos/{eigenaar}/{naam}/branch_protections/{branch}"
        )
        if antwoord.status_code == 404:
            return False, False, ""
        if antwoord.status_code != 200:
            return None, None, duiding(antwoord)
        d = antwoord.json()
        return (
            True,
            bool(d.get("enable_approvals_whitelist") or d.get("required_approvals", 0) > 0),
            "",
        )

    def repositories(self, eigenaar: str) -> tuple[list[str], str]:
        """Zie `GitHubClient.repositories`. Forgejo pagineert met `limit`/`page`."""
        namen: list[str] = []
        gearchiveerd = 0
        for pagina in range(1, 11):
            antwoord = _haal(
                self._sessie, f"{self.basis}/orgs/{eigenaar}/repos?limit=50&page={pagina}"
            )
            if antwoord.status_code != 200:
                return namen, duiding(antwoord)
            blok = antwoord.json()
            if not blok:
                break
            for repo in blok:
                if repo.get("archived"):
                    gearchiveerd += 1
                    continue
                namen.append(str(repo.get("name", "")))
        reden = f"{gearchiveerd} gearchiveerde repository(s) overgeslagen" if gearchiveerd else ""
        return namen, reden

    def bestand(self, eigenaar: str, naam: str, pad: str) -> Bestand:
        antwoord = _haal(self._sessie, f"{self.basis}/repos/{eigenaar}/{naam}/contents/{pad}")
        if antwoord.status_code == 404:
            # Hier bewust "bestaat niet" zonder tokenvoorbehoud: dit pad wordt alleen opgehaald
            # nadat `repository()` 200 gaf, dus de repo is leesbaar en contents kennen geen
            # rechten per pad. Een 404 is dan echte afwezigheid — en juist dát is de bevinding
            # (6 van 12 repo's zonder SECURITY.md, gemeten 2026-08-26).
            return Bestand(pad=pad, aanwezig=False, reden="bestaat niet")
        if antwoord.status_code != 200:
            return Bestand(pad=pad, aanwezig=False, reden=duiding(antwoord))
        return Bestand(pad=pad, inhoud=_decodeer(antwoord.json()))

    def bestanden_in_map(self, eigenaar: str, naam: str, map_: str) -> tuple[list[str], str]:
        """Zie `GitHubClient.bestanden_in_map`."""
        antwoord = _haal(self._sessie, f"{self.basis}/repos/{eigenaar}/{naam}/contents/{map_}")
        if antwoord.status_code == 404:
            return [], ""
        if antwoord.status_code != 200:
            return [], duiding(antwoord)
        d = antwoord.json()
        if not isinstance(d, list):
            return [], ""
        return [str(x.get("path", "")) for x in d if x.get("type") == "file"], ""

    def wijzigingen(self, eigenaar: str, naam: str, aantal: int) -> Wijzigingen:
        antwoord = _haal(
            self._sessie,
            f"{self.basis}/repos/{eigenaar}/{naam}/pulls?state=closed&limit={aantal}",
        )
        if antwoord.status_code != 200:
            return Wijzigingen(onbekend=True, reden=duiding(antwoord))
        gemerged = [p for p in antwoord.json() if p.get("merged")]
        zonder = 0
        for pr in gemerged:
            nummer = pr.get("number")
            rev = _haal(
                self._sessie, f"{self.basis}/repos/{eigenaar}/{naam}/pulls/{nummer}/reviews"
            )
            if rev.status_code != 200:
                return Wijzigingen(onbekend=True, reden=duiding(rev))
            if not [r for r in rev.json() if r.get("state") == "APPROVED"]:
                zonder += 1
        return Wijzigingen(bekeken=len(gemerged), zonder_review=zonder)


CLIENTS: dict[str, type[GitHubClient] | type[CodebergClient]] = {
    "github": GitHubClient,
    "codeberg": CodebergClient,
}
"""De forges die dit tool kent. Een onbekende naam is een fout, geen stille overslag —
zie `sources/repo.py`."""


def _decodeer(d: dict[str, Any]) -> str:
    """Beide forges leveren bestandsinhoud base64-gecodeerd in het `content`-veld."""
    import base64

    ruw = d.get("content") or ""
    if not ruw:
        return ""
    try:
        return base64.b64decode(ruw).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""
