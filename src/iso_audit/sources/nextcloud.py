"""Nextcloud-source-adapter — documenten lezen via WebDAV.

Implementeert hetzelfde `Source`-protocol als Drive, Jira en Planning. De pipeline hoeft niet
te weten dat het Nextcloud is; dat is precies de belofte die `iso_audit.sources` doet en die
tot nu toe onbewezen was — Drive, Jira en Planning zijn alle drie Google- of
Atlassian-specifiek.

De tekstextractie is gedeeld met Drive (`sources/tekst.py`): PDF, docx, xlsx, pptx en de
tekstformaten. Een tweede set lezers per bron zou van "leest het tool xlsx-tabellen?" een vraag
met twee antwoorden maken.

Wat hier wél bronspecifiek is: WebDAV-listing, de Nextcloud-systeemmappen (prullenbak,
versies), en de URL-vorm waarmee een auditor het document opent.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from collections.abc import Iterator
from typing import Any

import requests

from iso_audit.clients import nextcloud as dav
from iso_audit.config.verbinding import normaliseer
from iso_audit.sources import register
from iso_audit.sources.base import Document, Finding
from iso_audit.sources.tekst import (
    ODF_MIMES,
    LeegDocumentError,
    leeg_reden,
    lees_bytes,
)

logger = logging.getLogger(__name__)

BASIS_URL_ENV = "NEXTCLOUD_BASE_URL"
GEBRUIKER_ENV = "NEXTCLOUD_USER"
WACHTWOORD_ENV = "NEXTCLOUD_APP_PASSWORD"
PADEN_ENV = "NEXTCLOUD_PATHS"
"""Eén of meer paden onder de gebruikersmap, komma-gescheiden. Leeg = de hele gebruikersmap.

Komma is het opslagformaat van de env-var, niet iets dat een auditor intypt — in de UI staan de
paden als losse rijen, zoals bij Drive."""

ONDERSTEUNDE_MIME_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/html": "html",
    "text/csv": "csv",
    **ODF_MIMES,
}
"""Dezelfde formaten als Drive, minus de Google-native types die hier niet bestaan.

Bewust een eigen tabel en geen import uit `sources/drive`: die bevat Google-MIME's die op een
WebDAV-server nooit voorkomen, en een gedeelde tabel zou suggereren dat beide bronnen hetzelfde
aankunnen."""

NIET_LEESBAAR: dict[str, str] = {
    "image/jpeg": "afbeelding; de tekst zit in de pixels en er is geen OCR",
    "image/png": "afbeelding; de tekst zit in de pixels en er is geen OCR",
    "image/gif": "afbeelding; de tekst zit in de pixels en er is geen OCR",
    "image/tiff": "afbeelding; de tekst zit in de pixels en er is geen OCR",
    "image/svg+xml": "vectorafbeelding; geen doorlopende tekst",
    "video/mp4": "video; geen tekst te extraheren",
    "application/zip": "archief; de inhoud wordt niet uitgepakt",
}


def _paden(expliciet: str | list[str] | None = None) -> list[str]:
    """De te lezen paden; een lege lijst betekent de hele gebruikersmap."""
    if isinstance(expliciet, list):
        return [p.strip().strip("/") for p in expliciet if p.strip()]
    ruw = expliciet if expliciet is not None else os.environ.get(PADEN_ENV, "")
    return [p.strip().strip("/") for p in ruw.split(",") if p.strip()]


def _verbinding() -> dav.Verbinding:
    """Bouw de verbinding uit de omgeving; raise als er iets ontbreekt.

    Geen stille defaults: een bron die zonder configuratie "werkt" leest niets en meldt dat
    niet — dezelfde regel die op 2026-08-16 de hardcoded planning-sheet wegnam.
    """
    ontbreekt = [v for v in (BASIS_URL_ENV, GEBRUIKER_ENV, WACHTWOORD_ENV) if not os.environ.get(v)]
    if ontbreekt:
        raise OSError(f"Nextcloud niet geconfigureerd; ontbreekt: {', '.join(ontbreekt)}")
    return dav.Verbinding(
        basis_url=os.environ[BASIS_URL_ENV],
        gebruiker=os.environ[GEBRUIKER_ENV],
        app_wachtwoord=os.environ[WACHTWOORD_ENV],
    )


@register
class NextcloudSource:
    """Nextcloud (of elke WebDAV-server) als bron van auditbewijs."""

    naam = "nextcloud"

    def __init__(self, paden: str | list[str] | None = None) -> None:
        """Configuratie eenmalig vastzetten — immutable runtime-conf, zoals elke bron."""
        self._verbinding = _verbinding()
        self._paden = _paden(paden)
        self._overgeslagen: Counter[str] = Counter()
        self._gezien = 0
        self._gelezen = 0

    @property
    def paden(self) -> list[str]:
        return list(self._paden)

    def list_documents(self, filter: dict[str, object] | None = None) -> Iterator[Document]:
        """Yield documenten uit alle geconfigureerde paden.

        Dedup op pad: een bestand dat onder twee geconfigureerde paden valt (`/a` en `/a/b`)
        telt één keer, zoals de Drive-adapter op file-id dedupliceert.
        """
        del filter
        self._overgeslagen.clear()
        self._gezien = 0
        self._gelezen = 0
        logger.info("NextcloudSource list_documents: paden=%s", self._paden or ["<hele map>"])

        gezien_paden: set[str] = set()
        for pad in self._paden or [""]:
            skips: dict[str, int] = {}
            items = dav.lijst_recursief(self._verbinding, pad, overgeslagen=skips)
            for reden, aantal in skips.items():
                self._overgeslagen[reden] += aantal
                # Ook wat de client al oversloeg telt als gezien: anders klopt
                # `gezien = gelezen + overgeslagen` niet, en dat is precies de rekensom die
                # een auditor maakt. Zelfde semantiek als de Drive-teller.
                self._gezien += aantal
            for item in items:
                if item.pad in gezien_paden:
                    continue
                gezien_paden.add(item.pad)
                self._gezien += 1
                if item.mime in NIET_LEESBAAR:
                    logger.info("Niet leesbaar: %s (%s)", item.naam, item.mime)
                    self._overgeslagen[f"{item.mime}: {NIET_LEESBAAR[item.mime]}"] += 1
                    continue
                if item.mime not in ONDERSTEUNDE_MIME_TYPES:
                    logger.info("Onbekend type, niet gelezen: %s (%s)", item.naam, item.mime)
                    self._overgeslagen[f"onbekend type: {item.mime or '(geen)'}"] += 1
                    continue
                self._gelezen += 1
                yield Document(
                    id=item.pad,
                    titel=item.naam,
                    bron=self.naam,
                    type=ONDERSTEUNDE_MIME_TYPES[item.mime],
                    laatst_gewijzigd=item.gewijzigd,
                    inhoud_uri=item.pad,
                )
        logger.info(
            "NextcloudSource: %d bestand(en) gezien, %d gelezen, %d niet gelezen",
            self._gezien,
            self._gelezen,
            sum(self._overgeslagen.values()),
        )
        for reden, aantal in sorted(self._overgeslagen.items(), key=lambda p: (-p[1], p[0])):
            logger.info("Niet gelezen (%d): %s", aantal, reden)

    def fetch_content(self, doc: Document) -> str:
        """Lees de tekst van één document.

        :raises LeegDocumentError: de extractie lukte maar leverde geen tekst op.
        """
        if doc.bron != self.naam:
            raise ValueError(
                f"NextcloudSource krijgt document uit bron={doc.bron!r}, verwacht {self.naam!r}"
            )
        mime_voor_type = {v: k for k, v in ONDERSTEUNDE_MIME_TYPES.items()}
        mime = mime_voor_type.get(doc.type)
        if not mime:
            raise ValueError(f"Onbekend Document-type voor NextcloudSource: {doc.type!r}")
        tekst = lees_bytes(dav.download(self._verbinding, doc.inhoud_uri), mime)
        if not tekst.strip():
            raise LeegDocumentError(f"extractie leverde geen tekst op; {leeg_reden(mime)}")
        return tekst

    def list_findings(self, sessie_id: str) -> Iterator[Finding]:
        """Nextcloud levert geen findings — een lege iterator."""
        del sessie_id
        return iter([])

    def dekking(self) -> dict[str, Any]:
        """Wat de laatste listing zag, las en oversloeg — voor het run-record."""
        return {
            "gezien": self._gezien,
            "gelezen": self._gelezen,
            "overgeslagen": dict(self._overgeslagen),
        }

    def probe(self) -> dict[str, object]:
        """Status per geconfigureerd pad, voor het configuratiescherm.

        Per pad een eigen regel: één verkeerd pad mag een werkende configuratie niet als kapot
        laten ogen, en een samengevatte status verbergt precies welk pad stuk is. Zelfde vorm
        als de Drive-probe sinds 2026-08-17.
        """
        locaties: list[dict[str, object]] = []
        for pad in self._paden or [""]:
            ok, reden = dav.bereikbaar(self._verbinding, pad)
            locaties.append(
                {
                    "id": pad or "/",
                    "naam": pad or "hele gebruikersmap",
                    "soort": "map",
                    "status": "ok" if ok else "fail",
                    "reden": reden,
                }
            )
        bruikbaar = [loc for loc in locaties if loc["status"] == "ok"]
        if bruikbaar:
            return {"status": "ok", "naam": self.naam, "locaties": locaties}
        eerste = locaties[0] if locaties else None
        return {
            "status": "fail",
            "naam": self.naam,
            "tenant": self._verbinding.basis_url,
            "soort": "niet_bereikbaar",
            "reden": str(eerste["reden"]) if eerste else "Geen pad geconfigureerd.",
            "locaties": locaties,
        }

    def healthcheck(self) -> dict[str, object]:
        """Verifieer dat elk geconfigureerd pad te lezen is."""
        try:
            per_pad = {
                pad or "/": len(dav.lijst_map(self._verbinding, pad)) for pad in self._paden or [""]
            }
        except requests.RequestException as e:
            soort, tekst = normaliseer(e, bron=self.naam)
            return {
                "status": "fail",
                "naam": self.naam,
                "tenant": self._verbinding.basis_url,
                "soort": soort,
                "reden": tekst,
            }
        return {
            "status": "ok",
            "naam": self.naam,
            "per_pad": per_pad,
            "aantal_bestanden": sum(per_pad.values()),
        }
