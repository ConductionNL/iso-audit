"""Website-source-adapter — wat de organisatie publiek belooft.

Een publieke toezegging is een verplichting die je aangaat. Een privacyverklaring, een
securitypagina, een claim over certificering: dat zijn externe beloften die tegen de interne
praktijk gelegd horen te worden (§5.31 wettelijke en contractuele eisen, §5.34 privacy, en voor
9001 §8.2 eisen aan producten en diensten). Het gat tussen wat je publiceert en wat je doet, is
een klassieke NC — en die miste dit tool structureel, niet omdat hij moeilijk te zien is maar
omdat de bron er niet was.

**Geen crawler.** De sitemap die de site zelf publiceert, of een opgegeven lijst URL's. Links
volgen is niet te begrenzen, niet te herhalen en niet uit te leggen aan wie vraagt wat het tool
heeft gezien.

`robots.txt` wordt gerespecteerd: het tool leest een site die het niet bezit.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterator
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree  # nosec B405 — zie `_wortel`

import requests

from iso_audit.sources import register
from iso_audit.sources.base import Document, Finding

logger = logging.getLogger(__name__)

WEBSITES_ENV = "WEBSITE_URLS"
TIMEOUT = 20
MAX_PAGINAS = 200
"""Hoeveel pagina's er ten hoogste worden gelezen per site.

Gemeten 2026-08-26: de sitemap van conduction.nl noemt 146 URL's, dus 200 dekt de site zonder
plafond te raken. Instelbaar via `WEBSITE_MAX_PAGINAS`; een hardgecodeerde grens is niet te
testen. Overschrijding is een **melding** en geen stille afkapping."""

MAX_PAGINA_TEKENS = 200_000
VERTRAGING_ENV = "WEBSITE_VERTRAGING"
GEBRUIKERSAGENT = "iso-audit (ISO 9001/27001 audittool; read-only)"

_TAGS_WEG = re.compile(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", re.S | re.I)
"""Wat op elke pagina hetzelfde is, is geen inhoud van díe pagina.

Gemeten 2026-08-28: 135 van de 137 pagina's van conduction.nl matchten op §5.34 omdat in de
voettekst "© 2026 Privacy · Terms · ISO" staat. Een clausule-koppeling die op boilerplate matcht,
levert honderd bevindingen op over een eis waar de pagina niets over zegt."""

_MAIN = re.compile(r"<main[^>]*>(.*?)</main>", re.S | re.I)
_MARKUP = re.compile(r"<[^>]+>")
_WITRUIMTE = re.compile(r"\s+")


def zichtbare_tekst(html: str) -> str:
    """De leesbare tekst van een pagina, zonder markup.

    Opgeslagen als tekst en niet als HTML, net als bij een PDF of ODF-document: de classificatie
    leest tekst, en opgeslagen markup maakt elke latere zoekopdracht onbetrouwbaar.

    Navigatie en voettekst tellen niet mee: die staan op élke pagina en zeggen dus niets over
    déze. Zie `_TAGS_WEG` voor wat dat concreet aanrichtte.
    """
    zonder = _TAGS_WEG.sub(" ", html)
    # `<main>` is de inhoud van déze pagina. Geen `<main>`? Dan de hele body minus wat hierboven
    # al weg is — liever te veel dan niets, want een lege pagina leest als "hier staat niets"
    # terwijl er wel degelijk iets stond.
    kern = _MAIN.search(zonder)
    if kern:
        zonder = kern.group(1)
    return _WITRUIMTE.sub(" ", _MARKUP.sub(" ", zonder)).strip()


def urls_uit_sitemap_met_datum(xml: str) -> list[tuple[str, str]]:
    """De `<loc>`-waarden uit een sitemap, elk met zijn `<lastmod>` (leeg als die ontbreekt).

    De datum draagt de incrementele ingest: zonder wijzigingstijd kan `mag_overslaan` nooit
    overslaan, en haalde élke run alle 137 pagina's opnieuw op.
    """
    wortel = _wortel(xml)
    uit: list[tuple[str, str]] = []
    for el in wortel:
        loc = ""
        datum = ""
        for kind in el:
            naam = kind.tag.rsplit("}", 1)[-1]
            if naam == "loc":
                loc = (kind.text or "").strip()
            elif naam == "lastmod":
                datum = (kind.text or "").strip()
        if loc:
            uit.append((loc, datum))
    return uit


def _wortel(xml: str) -> ElementTree.Element:
    """Parse de sitemap; weiger een DOCTYPE."""
    if "<!DOCTYPE" in xml[:2000].upper():
        raise ValueError("sitemap met DOCTYPE wordt niet gelezen")
    try:
        # nosec B314 — DOCTYPE wordt hierboven geweigerd, dus entity-expansie kan niet. Zelfde
        # afweging als bij `sources/tekst.py` voor ODF: `defusedxml` erbij halen voor één
        # aanroep met een expliciete DOCTYPE-check ervoor is een afhankelijkheid zonder winst.
        return ElementTree.fromstring(xml)  # nosec B314
    except ElementTree.ParseError as fout:
        raise ValueError(f"sitemap is geen geldige XML: {fout}") from fout


def urls_uit_sitemap(xml: str) -> list[str]:
    """De `<loc>`-waarden uit een sitemap.

    `ElementTree` blokkeert entity-expansie niet, dus een sitemap met een DOCTYPE wordt geweigerd
    in plaats van geparsed — zelfde regel als bij `sources/tekst.py` voor ODF.
    """
    wortel = _wortel(xml)
    return [
        (el.text or "").strip()
        for el in wortel.iter()
        if el.tag.endswith("}loc") or el.tag == "loc"
        if (el.text or "").strip()
    ]


def normaliseer_adres(adres: str) -> str:
    """Maak van een ingevuld adres een bruikbare URL.

    De auditor vulde `www.conduction.nl` in en de bron leverde nul pagina's: `urljoin` maakt van
    een adres zonder schema `/sitemap.xml`, en dat is geen URL. De melding klopte, maar een tool
    dat een normale schrijfwijze afwijst en dan netjes uitlegt waarom, heeft nog steeds niets
    gelezen.

    `https://` en niet `http://`: een auditbron over een publieke website hoort niet stilletjes
    onversleuteld op te halen. Staat er al een schema, dan blijft dat staan — ook `http://`, want
    dat kan een bewuste keuze zijn voor een interne omgeving en overrulen zou de scope stil
    wijzigen.
    """
    schoon = adres.strip().rstrip("/")
    if not schoon:
        return ""
    if "://" not in schoon:
        schoon = f"https://{schoon}"
    return schoon


@register
class WebsiteSource:
    """Bron-adapter voor gepubliceerde webpagina's."""

    naam = "website"

    def __init__(self, sites: list[str] | str | None = None) -> None:
        ruw = sites if sites is not None else os.environ.get(WEBSITES_ENV, "")
        if isinstance(ruw, str):
            ruw = [s.strip() for s in ruw.split(",") if s.strip()]
        self._sites: list[str] = [a for a in (normaliseer_adres(x) for x in ruw) if a]
        self._max = int(os.environ.get("WEBSITE_MAX_PAGINAS") or MAX_PAGINAS)
        self._vertraging = float(os.environ.get(VERTRAGING_ENV) or 0.2)
        self._sessie = requests.Session()
        self._sessie.headers["User-Agent"] = GEBRUIKERSAGENT
        self.overgeslagen: dict[str, str] = {}
        """Wat er niet is gelezen en waarom — gaat mee in de dekking."""

    def _robots(self, basis: str) -> RobotFileParser:
        parser = RobotFileParser()
        parser.set_url(urljoin(basis, "/robots.txt"))
        try:
            antwoord = self._sessie.get(urljoin(basis, "/robots.txt"), timeout=TIMEOUT)
            parser.parse(antwoord.text.splitlines() if antwoord.ok else [])
        except requests.RequestException:
            # Geen robots.txt bereikbaar: dan is er niets dat iets verbiedt. Niet aannemen dat
            # alles verboden is — dan leest het tool stil niets en heet dat "geen bevindingen".
            parser.parse([])
        return parser

    def _urls(self, site: str) -> list[tuple[str, str]]:
        try:
            antwoord = self._sessie.get(urljoin(site, "/sitemap.xml"), timeout=TIMEOUT)
        except requests.RequestException as fout:
            self.overgeslagen[site] = f"sitemap niet op te halen: {fout}"
            return []
        if not antwoord.ok:
            self.overgeslagen[site] = f"geen sitemap (HTTP {antwoord.status_code})"
            return []
        try:
            return urls_uit_sitemap_met_datum(antwoord.text)
        except ValueError as fout:
            self.overgeslagen[site] = str(fout)
            return []

    def list_documents(self, filter: dict[str, object] | None = None) -> Iterator[Document]:
        for site in self._sites:
            robots = self._robots(site)
            urls = self._urls(site)
            toegestaan = [(u, d) for u, d in urls if robots.can_fetch(GEBRUIKERSAGENT, u)]
            if len(toegestaan) < len(urls):
                self.overgeslagen[f"{site} (robots.txt)"] = (
                    f"{len(urls) - len(toegestaan)} pagina('s) uitgesloten door robots.txt"
                )
            if len(toegestaan) > self._max:
                self.overgeslagen[f"{site} (maximum)"] = (
                    f"{len(toegestaan) - self._max} pagina('s) niet gelezen; het maximum staat "
                    f"op {self._max}"
                )
                toegestaan = toegestaan[: self._max]
            for url, gewijzigd in toegestaan:
                yield Document(
                    id=url,
                    titel=urlparse(url).path or url,
                    bron=self.naam,
                    type="webpagina",
                    # `<lastmod>` uit de sitemap; leeg als de site het niet vult. Zonder deze
                    # tijd kan de incrementele ingest niets overslaan en haalt élke run alle
                    # pagina's opnieuw op.
                    laatst_gewijzigd=gewijzigd,
                    inhoud_uri=url,
                )

    def fetch_content(self, doc: Document) -> str:
        if doc.bron != self.naam:
            raise ValueError(
                f"WebsiteSource krijgt document uit bron={doc.bron!r}, verwacht {self.naam!r}"
            )
        if self._vertraging:
            import time

            time.sleep(self._vertraging)
        antwoord = self._sessie.get(doc.inhoud_uri, timeout=TIMEOUT)
        if not antwoord.ok:
            self.overgeslagen[doc.inhoud_uri] = f"HTTP {antwoord.status_code}"
            return ""
        return zichtbare_tekst(antwoord.text)[:MAX_PAGINA_TEKENS]

    def list_findings(self, sessie_id: str) -> Iterator[Finding]:
        return iter(())

    def healthcheck(self) -> dict[str, object]:
        if not self._sites:
            # Zie `RepoSource.healthcheck` voor waarom `soort` hier meemoet.
            #
            # Extra reden om het hier goed te doen: een website heeft geen token nodig, dus
            # "niet gekoppeld" zonder uitleg laat een auditor zoeken naar een credential die
            # niet bestaat.
            return {
                "status": "niet_gekoppeld",
                "naam": self.naam,
                "soort": "niet_geconfigureerd",
                "reden": (
                    "Er is nog geen website ingevuld. Een website heeft geen token nodig; "
                    "vul een adres in zoals https://www.conduction.nl."
                ),
            }
        return {
            "status": "ok",
            "naam": self.naam,
            "locaties": [{"naam": s} for s in self._sites],
        }
