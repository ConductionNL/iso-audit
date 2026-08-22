"""Nextcloud/WebDAV-lezen met een app-wachtwoord.

## Waarom WebDAV en niet de Nextcloud-API

Nextcloud heeft een eigen OCS-API, maar bestanden lezen gaat via WebDAV op
`/remote.php/dav/files/<gebruiker>/`. Dat is een standaard, en dat is hier het argument: dezelfde
adapter werkt tegen ownCloud, Seafile met WebDAV en een gewone Apache met `mod_dav`. De OCS-API
zou het aan één product binden zonder iets op te leveren dat dit tool nodig heeft.

## `Depth: 1` en niet `infinity`

`PROPFIND` met `Depth: infinity` zou de hele boom in één antwoord geven. Veel servers weigeren
dat (Nextcloud onder andere), en waar het mag is een fout halverwege niet te lokaliseren in een
antwoord van megabytes. Recursie per map, net als de Drive-adapter.

## App-wachtwoord, geen gebruikerswachtwoord

Nextcloud kent app-specifieke wachtwoorden: per applicatie één credential, apart intrekbaar,
zonder toegang tot de webinterface. Zelfde argument als bij het Google-service-account — de
auditcapability hoort niet aan de sessie van een medewerker te hangen.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET  # nosec B405 — zie WebdavAntwoordError
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlparse

import requests

logger = logging.getLogger("iso_audit.audit")

_DAV = "{DAV:}"

_DOCTYPE = re.compile(r"<!DOCTYPE", re.IGNORECASE)
_DOCTYPE_VENSTER = 2048
"""Hoeveel tekens vooraan op een DOCTYPE worden nagekeken. Een DTD staat in de prolog; verderop
is `<!DOCTYPE` gewoon tekst in een bestandsnaam."""

MAX_ANTWOORD = 32 * 1024 * 1024
"""Bovengrens op een PROPFIND-antwoord. Eén map met duizenden bestanden blijft ruim daaronder."""


class WebdavAntwoordError(Exception):
    """Het antwoord van de server is niet te vertrouwen of te groot.

    Nagemeten op 2026-08-22 met deze Python (3.12.13) en expat 2.7.3: een klassieke
    entity-expansie ("billion laughs") wordt **niet** door de parser geweigerd — een kleine
    invoer leverde 3000 tekens op, en dat schaalt door. `xml.etree.ElementTree` heeft daar geen
    bescherming voor.

    De weigering zit daarom in een DOCTYPE-check vóór het parsen: entiteiten vereisen een DTD, en
    een WebDAV-antwoord heeft er nooit legitiem een. Dat is twee regels en geen afhankelijkheid;
    `defusedxml` zou hetzelfde doen met meer oppervlak, en een extra pakket in een repo die zelf
    onder ISO 27001-scope valt is een beslissing.

    Het gaat niet om wantrouwen tegen Nextcloud: het gaat erom dat een gecompromitteerde of
    verkeerd geconfigureerde server dit proces niet mag laten omvallen — dezelfde reden waarom
    een leeg extractieresultaat een storing is en geen leeg document.
    """


_TIMEOUT = 60
"""Seconden per verzoek. Ruim voor een PROPFIND op een grote map, krap genoeg dat een
onbereikbare server een run niet laat hangen."""

_PROPFIND_BODY = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:resourcetype/>
    <d:getcontenttype/>
    <d:getlastmodified/>
    <d:getcontentlength/>
  </d:prop>
</d:propfind>
"""
"""Alleen de vier eigenschappen die `Document` nodig heeft.

Zonder `<d:prop>` levert Nextcloud álle eigenschappen op inclusief permissies, favorites en
share-informatie — meer antwoord voor hetzelfde doel, en meer om per ongeluk op te leunen."""

OVERGESLAGEN_PADEN: tuple[str, ...] = (
    "/trashbin/",
    "/versions/",
    "/uploads/",
)
"""Nextcloud-eigen mappen die geen bewijs bevatten.

Prullenbak: verwijderd is verwijderd. Versies: alleen de huidige versie telt als bewijs, anders
levert één document evenveel bevindingen als het versies heeft. Uploads: onafgemaakte chunked
uploads.

Deze worden **gemeld** overgeslagen, niet stil — dat is de regel uit `landschap-dekking`, en bij
een nieuwe bron is de verleiding het grootst om "die map hoort er niet bij" ongezegd te laten."""


@dataclass(frozen=True)
class Verbinding:
    """Waar en met welke credential er gelezen wordt.

    Immutable, zoals elke runtime-configuratie in dit tool: een bron die halverwege een run van
    server wisselt, levert een run met twee scopes.
    """

    basis_url: str
    gebruiker: str
    app_wachtwoord: str

    @property
    def dav_root(self) -> str:
        """De WebDAV-wortel voor deze gebruiker, altijd met een afsluitende slash."""
        basis = self.basis_url.rstrip("/")
        return f"{basis}/remote.php/dav/files/{self.gebruiker}/"


@dataclass(frozen=True)
class Item:
    """Eén bestand of map uit een PROPFIND-antwoord."""

    pad: str
    """Pad ten opzichte van de DAV-wortel, zonder leidende slash."""
    is_map: bool
    mime: str
    gewijzigd: str
    bytes_groot: int

    @property
    def naam(self) -> str:
        return self.pad.rstrip("/").rsplit("/", 1)[-1]


def _sessie(verbinding: Verbinding) -> requests.Session:
    s = requests.Session()
    s.auth = (verbinding.gebruiker, verbinding.app_wachtwoord)
    return s


def _tekst(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _parse_propfind(xml: str, zelf_pad: str, wortel_pad: str) -> list[Item]:
    """Zet een `207 Multi-Status` om in items, de opgevraagde map zelf niet meegerekend.

    De server geeft de map waarop je `PROPFIND` deed als eerste `<response>` terug. Die
    meenemen zou elke map als kind van zichzelf opleveren en de recursie oneindig maken.

    `zelf_pad` is de opgevraagde map (om over te slaan), `wortel_pad` de DAV-wortel (om af te
    knippen). Die twee moeten uit elkaar: knip je op de opgevraagde map, dan is `Sub/` het
    resultaat in plaats van `Audit/Sub/`, en zoekt de recursie in de verkeerde map. Precies dat
    gebeurde bij de eerste test op 2026-08-22.
    """
    if len(xml) > MAX_ANTWOORD:
        raise WebdavAntwoordError(
            f"PROPFIND-antwoord van {len(xml)} tekens overschrijdt de grens van {MAX_ANTWOORD}"
        )
    if _DOCTYPE.search(xml[:_DOCTYPE_VENSTER]):
        raise WebdavAntwoordError(
            "PROPFIND-antwoord bevat een DOCTYPE; geweigerd wegens entity-expansie"
        )
    wortel = ET.fromstring(xml)  # nosec B314 — DOCTYPE geweigerd en lengte begrensd, zie boven
    items: list[Item] = []
    for respons in wortel.findall(f"{_DAV}response"):
        href = unquote(_tekst(respons.find(f"{_DAV}href")))
        pad = urlparse(href).path
        if pad.rstrip("/") == zelf_pad.rstrip("/"):
            continue
        propstat = respons.find(f"{_DAV}propstat")
        prop = propstat.find(f"{_DAV}prop") if propstat is not None else None
        if prop is None:
            continue
        resourcetype = prop.find(f"{_DAV}resourcetype")
        is_map = resourcetype is not None and resourcetype.find(f"{_DAV}collection") is not None
        groot = _tekst(prop.find(f"{_DAV}getcontentlength"))
        items.append(
            Item(
                pad=pad[len(wortel_pad) :].lstrip("/") if pad.startswith(wortel_pad) else pad,
                is_map=is_map,
                mime=_tekst(prop.find(f"{_DAV}getcontenttype")).split(";")[0],
                gewijzigd=_tekst(prop.find(f"{_DAV}getlastmodified")),
                bytes_groot=int(groot) if groot.isdigit() else 0,
            )
        )
    return items


def lijst_map(
    verbinding: Verbinding, pad: str = "", *, sessie: requests.Session | None = None
) -> list[Item]:
    """Eén niveau van een map opvragen. `pad` is relatief aan de DAV-wortel.

    :raises requests.HTTPError: bij een statuscode die geen 207 is.
    """
    s = sessie or _sessie(verbinding)
    url = urljoin(verbinding.dav_root, pad.lstrip("/"))
    if not url.endswith("/"):
        url += "/"
    antwoord = s.request(
        "PROPFIND",
        url,
        data=_PROPFIND_BODY.encode("utf-8"),
        headers={"Depth": "1", "Content-Type": "application/xml"},
        timeout=_TIMEOUT,
    )
    antwoord.raise_for_status()
    return _parse_propfind(antwoord.text, urlparse(url).path, urlparse(verbinding.dav_root).path)


def lijst_recursief(
    verbinding: Verbinding,
    pad: str = "",
    *,
    sessie: requests.Session | None = None,
    overgeslagen: dict[str, int] | None = None,
) -> list[Item]:
    """Alle bestanden onder `pad`, submappen gevolgd, de mappen zelf niet meegeleverd.

    `overgeslagen` telt per reden mee wat er is overgeslagen. Meegeven en niet zelf loggen: de
    bron-adapter bouwt daar de dekking van, en die hoort in het run-record.
    """
    s = sessie or _sessie(verbinding)
    tellers = overgeslagen if overgeslagen is not None else {}
    uit: list[Item] = []
    for item in lijst_map(verbinding, pad, sessie=s):
        vol_pad = f"/{item.pad}"
        if any(deel in vol_pad for deel in OVERGESLAGEN_PADEN):
            tellers["Nextcloud-systeemmap (prullenbak, versies of uploads)"] = (
                tellers.get("Nextcloud-systeemmap (prullenbak, versies of uploads)", 0) + 1
            )
            continue
        if item.naam.startswith("."):
            tellers["verborgen bestand of map"] = tellers.get("verborgen bestand of map", 0) + 1
            continue
        if item.is_map:
            uit.extend(lijst_recursief(verbinding, item.pad, sessie=s, overgeslagen=tellers))
        else:
            uit.append(item)
    return uit


def download(verbinding: Verbinding, pad: str, *, sessie: requests.Session | None = None) -> bytes:
    """Haal de inhoud van één bestand op.

    :raises requests.HTTPError: bij een statuscode buiten 2xx.
    """
    s = sessie or _sessie(verbinding)
    url = urljoin(verbinding.dav_root, pad.lstrip("/"))
    antwoord = s.get(url, timeout=_TIMEOUT)
    antwoord.raise_for_status()
    return antwoord.content


def bereikbaar(verbinding: Verbinding, pad: str = "") -> tuple[bool, str]:
    """Is deze locatie te lezen? Retourneert `(ok, reden)`.

    Bewust geen exception: `probe()` in de bron-adapter moet per locatie een status kunnen
    tonen, en een halve configuratie mag het configuratiescherm niet laten crashen.
    """
    try:
        items = lijst_map(verbinding, pad)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        if code == 401:
            return False, "Aanmelden mislukte; het app-wachtwoord klopt niet of is ingetrokken."
        if code == 404:
            return False, "Dit pad bestaat niet op de server."
        return False, f"De server antwoordde met status {code}."
    except requests.RequestException:
        # Geen `str(e)`: die kan de URL met credential bevatten, en deze tekst gaat naar de
        # browser. Zelfde regel als in `config/verbinding.normaliseer`.
        logger.warning('{"event": "nextcloud_onbereikbaar", "pad": "%s"}', pad)
        return False, "De server is niet bereikbaar."
    return True, f"{len(items)} item(s) op dit niveau."
