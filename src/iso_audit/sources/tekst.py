"""Tekst uit bestandsbytes — gedeeld door elke bron die bestanden leest.

## Waarom dit een eigen module is

Deze lezers stonden in `sources/drive.py` en raken Drive niet: het zijn functies van bytes naar
tekst. Toen `nextcloud-bron` erbij kwam, was de keuze een tweede set lezers of één gedeelde.

Een tweede set maakt van "leest het tool xlsx-tabellen?" een vraag met twee antwoorden, die na
één wijziging uit elkaar lopen. Dat is precies het soort stille verschil waar de
dekkingsmeldingen van 2026-08-18 voor bestaan — dus één set, hier.

Wat **niet** hier hoort: de Google-exports (Docs, Sheets, Slides). Die vragen een Drive-API en
zijn dus wél bronspecifiek.

## De regel die deze module draagt

Een geslaagde extractie die nul tekens oplevert, is een **storing** en geen leeg document. Een
gescande PDF als leeg document opgenomen classificeert de pipeline als "geen bewijs" — een
oordeel over iets wat niemand heeft gelezen, op een clausule waar het bewijs bestaat.
"""

from __future__ import annotations

import io
from collections.abc import Callable

import docx
import openpyxl
import pptx
import pypdf

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

GESCANDE_FORMATEN: frozenset[str] = frozenset({"application/pdf"})
"""Formaten waarbij "geen tekst" op een scan kan duiden.

Voor de rest kan het dat niet. Een `.docx` zonder tekst is geen scan maar een document
waarvan de inhoud buiten het bereik van de lezer valt — tot 2026-08-21 stond in de melding
"mogelijk een scan of een leeg bestand" voor élk formaat, en dat wees de auditor de verkeerde
kant op bij precies het bestand dat wél te repareren was."""


class LeegDocumentError(Exception):
    """De extractie lukte, maar leverde geen tekst op.

    Bewust een eigen fout en geen lege string: een gescande PDF levert nul tekens, en als
    document met lege inhoud opgenomen classificeert de pipeline hem als "geen bewijs" — een
    oordeel over iets wat niemand heeft gelezen, op een clausule waar het bewijs bestaat.
    Dezelfde regel als bij de classificatie sinds 2026-08-17, waar een afgekapt antwoord ook
    geen leeg oordeel meer is.
    """


def tekst_uit_docx(inhoud: bytes) -> str:
    """Alinea's **en** tabelcellen.

    De tabellen ontbraken tot 2026-08-21, en dat is geen detail: een actiepuntenlijst of een
    RI&E-overzicht is één tabel en levert dan nul alinea's op. Gemeten in de eerste
    productierun — `Actiepunten uit Waveland.docx` kwam binnen als "geen tekst, mogelijk een
    scan", wat voor een docx onmogelijk is.

    Tekstvakken en koppen/voetteksten blijven buiten bereik: die zitten niet in het
    `document.body`-model van python-docx. Een docx die daardoor leeg blijft, wordt gemeld als
    onleesbaar — zichtbaar, niet stil.
    """
    doc = docx.Document(io.BytesIO(inhoud))
    delen = [p.text for p in doc.paragraphs]
    for tabel in doc.tables:
        for rij in tabel.rows:
            cellen = [c.text.strip() for c in rij.cells if c.text.strip()]
            if cellen:
                delen.append("\t".join(cellen))
    tekst = "\n".join(delen)
    if not tekst.strip():
        # Geen tekst én tekeningen in de body: dan is de inhoud ingevoegde afbeeldingen, en
        # dat is een feit in plaats van een vermoeden. Gemeten op 2026-08-21:
        # `Actiepunten uit Waveland.docx` is 569 KB met drie lege alinea's, nul tabellen en
        # zes `w:drawing`-elementen — screenshots in een Word-bestand. "Mogelijk een scan"
        # zei daar het verkeerde over; alleen OCR zou hier iets opleveren.
        tekeningen = doc.element.body.xml.count("w:drawing")
        if tekeningen:
            raise LeegDocumentError(
                f"bevat {tekeningen} ingevoegde afbeelding(en) en geen tekst; "
                "zonder OCR is hier niets uit te lezen"
            )
    return tekst


def tekst_uit_xlsx(inhoud: bytes) -> str:
    """Celtekst per blad, met de bladnaam als kop.

    `data_only=True` geeft de laatst berekende waarde in plaats van de formule: in een
    RI&E-actielijst is "hoog" het bewijs, niet `=ALS(...)`.
    """
    boek = openpyxl.load_workbook(io.BytesIO(inhoud), data_only=True, read_only=True)
    regels: list[str] = []
    for blad in boek.worksheets:
        regels.append(f"## {blad.title}")
        for rij in blad.iter_rows(values_only=True):
            cellen = [str(c) for c in rij if c is not None and str(c).strip()]
            if cellen:
                regels.append("\t".join(cellen))
    boek.close()
    return "\n".join(regels)


def tekst_uit_pptx(inhoud: bytes) -> str:
    """Tekst per dia, inclusief tabellen — om dezelfde reden als bij docx."""
    presentatie = pptx.Presentation(io.BytesIO(inhoud))
    regels: list[str] = []
    for nummer, dia in enumerate(presentatie.slides, start=1):
        regels.append(f"## Dia {nummer}")
        for vorm in dia.shapes:
            tekst = getattr(vorm, "text", "")
            if tekst and tekst.strip():
                regels.append(tekst)
            if getattr(vorm, "has_table", False):
                for rij in vorm.table.rows:
                    cellen = [c.text.strip() for c in rij.cells if c.text.strip()]
                    if cellen:
                        regels.append("\t".join(cellen))
    return "\n".join(regels)


def tekst_uit_pdf(inhoud: bytes) -> str:
    """Doorlopende tekst per pagina via `pypdf`. Geen OCR.

    Een gescande PDF levert hier nul tekens op; die wordt door de caller als onleesbaar
    gemeld en niet als leeg document opgenomen.
    """
    lezer = pypdf.PdfReader(io.BytesIO(inhoud))
    return "\n".join(pagina.extract_text() or "" for pagina in lezer.pages)


_BINAIRE_LEZERS: dict[str, Callable[[bytes], str]] = {
    DOCX_MIME: tekst_uit_docx,
    XLSX_MIME: tekst_uit_xlsx,
    PPTX_MIME: tekst_uit_pptx,
    "application/pdf": tekst_uit_pdf,
}
"""Per binair formaat één lezer. De rest wordt als tekst gedecodeerd."""


def lees_bytes(inhoud: bytes, mime: str) -> str:
    """Tekst uit `inhoud` volgens `mime`; onbekende types worden als tekst gedecodeerd.

    Raist geen `LeegDocumentError` — de caller beslist wat een leeg resultaat betekent, omdat
    de reden per bron verschilt: een Drive-export kan leeg zijn doordat de export faalde, een
    WebDAV-download doordat het bestand zelf leeg is.
    """
    lezer = _BINAIRE_LEZERS.get(mime)
    return lezer(inhoud) if lezer else inhoud.decode("utf-8", errors="replace")


PLATTE_TEKST: frozenset[str] = frozenset({"text/plain", "text/markdown", "text/csv", "text/html"})
"""Formaten waarbij "geen tekst" simpelweg "leeg bestand" betekent.

Er valt niets te vermoeden over tekstvakken of scans in een `.txt` van nul bytes."""


def leeg_reden(mime: str) -> str:
    """Waarom een geslaagde extractie geen tekst opleverde, per formaat.

    Eén reden voor alle formaten was juist de fout: "mogelijk een scan" bij een docx wees de
    auditor de verkeerde kant op bij precies het bestand dat wél te repareren was. En bij een
    lege `.txt` op de Nextcloud-canary (2026-08-22) stond er "mogelijk staat de inhoud in
    tekstvakken" — over een bestand van nul bytes.
    """
    if mime in GESCANDE_FORMATEN:
        return "mogelijk een scan of een leeg bestand"
    if mime in PLATTE_TEKST:
        return "het bestand is leeg"
    return "mogelijk staat de inhoud in afbeeldingen, tekstvakken of koppen"
