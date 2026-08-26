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
from xml.etree import ElementTree

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

_TAGS_WEG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_MARKUP = re.compile(r"<[^>]+>")
_WITRUIMTE = re.compile(r"\s+")


def zichtbare_tekst(html: str) -> str:
    """De leesbare tekst van een pagina, zonder markup.

    Opgeslagen als tekst en niet als HTML, net als bij een PDF of ODF-document: de classificatie
    leest tekst, en opgeslagen markup maakt elke latere zoekopdracht onbetrouwbaar.
    """
    zonder = _TAGS_WEG.sub(" ", html)
    return _WITRUIMTE.sub(" ", _MARKUP.sub(" ", zonder)).strip()


def urls_uit_sitemap(xml: str) -> list[str]:
    """De `<loc>`-waarden uit een sitemap.

    `ElementTree` blokkeert entity-expansie niet, dus een sitemap met een DOCTYPE wordt geweigerd
    in plaats van geparsed — zelfde regel als bij `sources/tekst.py` voor ODF.
    """
    if "<!DOCTYPE" in xml[:2000].upper():
        raise ValueError("sitemap met DOCTYPE wordt niet gelezen")
    try:
        wortel = ElementTree.fromstring(xml)
    except ElementTree.ParseError as fout:
        raise ValueError(f"sitemap is geen geldige XML: {fout}") from fout
    return [
        (el.text or "").strip()
        for el in wortel.iter()
        if el.tag.endswith("}loc") or el.tag == "loc"
        if (el.text or "").strip()
    ]


@register
class WebsiteSource:
    """Bron-adapter voor gepubliceerde webpagina's."""

    naam = "website"

    def __init__(self, sites: list[str] | str | None = None) -> None:
        ruw = sites if sites is not None else os.environ.get(WEBSITES_ENV, "")
        if isinstance(ruw, str):
            ruw = [s.strip() for s in ruw.split(",") if s.strip()]
        self._sites: list[str] = list(ruw)
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

    def _urls(self, site: str) -> list[str]:
        try:
            antwoord = self._sessie.get(urljoin(site, "/sitemap.xml"), timeout=TIMEOUT)
        except requests.RequestException as fout:
            self.overgeslagen[site] = f"sitemap niet op te halen: {fout}"
            return []
        if not antwoord.ok:
            self.overgeslagen[site] = f"geen sitemap (HTTP {antwoord.status_code})"
            return []
        try:
            return urls_uit_sitemap(antwoord.text)
        except ValueError as fout:
            self.overgeslagen[site] = str(fout)
            return []

    def list_documents(self, filter: dict[str, object] | None = None) -> Iterator[Document]:
        for site in self._sites:
            robots = self._robots(site)
            urls = self._urls(site)
            toegestaan = [u for u in urls if robots.can_fetch(GEBRUIKERSAGENT, u)]
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
            for url in toegestaan:
                yield Document(
                    id=url,
                    titel=urlparse(url).path or url,
                    bron=self.naam,
                    type="webpagina",
                    laatst_gewijzigd="",
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
            return {
                "status": "niet_gekoppeld",
                "naam": self.naam,
                "reden": "geen websites geconfigureerd",
            }
        return {
            "status": "ok",
            "naam": self.naam,
            "locaties": [{"naam": s} for s in self._sites],
        }
