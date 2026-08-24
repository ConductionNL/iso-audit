"""Tests voor de OpenDocument-lezer in `iso_audit.sources.tekst`.

De fixtures worden hier met `zipfile` opgebouwd en niet als binair bestand meegeleverd: een
ODF-bestand is een zip met `content.xml`, en een test die dat zelf samenstelt laat zien welke
XML-vorm de lezer aankan. Een meegeleverd `.odt` verbergt precies dat.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from iso_audit.sources import tekst

_NS = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"'
)


def _odf(body: str, *, prolog: str = '<?xml version="1.0" encoding="UTF-8"?>') -> bytes:
    """Een minimaal geldig ODF-bestand: een zip met alleen `content.xml`."""
    xml = f"{prolog}<office:document-content {_NS}><office:body>{body}</office:body></office:document-content>"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_bestand:
        zip_bestand.writestr("mimetype", "application/vnd.oasis.opendocument.text")
        zip_bestand.writestr("content.xml", xml)
    return buffer.getvalue()


def test_odt_alineas_en_koppen_in_documentorde() -> None:
    inhoud = _odf(
        "<office:text>"
        "<text:h>Informatiebeveiligingsbeleid</text:h>"
        "<text:p>Vastgesteld door de directie.</text:p>"
        "<text:p/>"
        "<text:p>Jaarlijks herzien.</text:p>"
        "</office:text>"
    )
    assert tekst.tekst_uit_odf(inhoud) == (
        "Informatiebeveiligingsbeleid\nVastgesteld door de directie.\nJaarlijks herzien."
    )


def test_odt_opmaak_binnen_een_alinea_blijft_een_regel() -> None:
    """`text:span` splitst een alinea niet: opmaak is geen inhoudsgrens."""
    inhoud = _odf(
        "<office:text><text:p>De <text:span>eigenaar</text:span> is de CISO.</text:p></office:text>"
    )
    assert tekst.tekst_uit_odf(inhoud) == "De eigenaar is de CISO."


def test_ods_rij_blijft_een_rij() -> None:
    """Cellen van één rij worden met tabs samengevoegd, net als bij xlsx.

    Cel-per-regel zou de betekenis weggooien: "Beleid", "CISO" en "2026-01-01" onder elkaar
    zegt niet meer welke eigenaar bij welk beleid hoort.
    """
    inhoud = _odf(
        "<office:spreadsheet><table:table>"
        "<table:table-row>"
        "<table:table-cell><text:p>Beheersmaatregel</text:p></table:table-cell>"
        "<table:table-cell><text:p>Eigenaar</text:p></table:table-cell>"
        "</table:table-row>"
        "<table:table-row>"
        "<table:table-cell><text:p>A.5.1</text:p></table:table-cell>"
        "<table:table-cell><text:p>CISO</text:p></table:table-cell>"
        "</table:table-row>"
        "</table:table></office:spreadsheet>"
    )
    assert tekst.tekst_uit_odf(inhoud) == "Beheersmaatregel\tEigenaar\nA.5.1\tCISO"


def test_ods_lege_cellen_vallen_weg_maar_de_rij_blijft() -> None:
    inhoud = _odf(
        "<office:spreadsheet><table:table><table:table-row>"
        "<table:table-cell><text:p>A.8.24</text:p></table:table-cell>"
        "<table:table-cell/>"
        "<table:table-cell><text:p>open</text:p></table:table-cell>"
        "</table:table-row></table:table></office:spreadsheet>"
    )
    assert tekst.tekst_uit_odf(inhoud) == "A.8.24\topen"


def test_odp_tekst_uit_kaders() -> None:
    inhoud = _odf(
        "<office:presentation><draw:page>"
        "<draw:frame><draw:text-box><text:p>Awareness-training</text:p></draw:text-box></draw:frame>"
        "<draw:frame><draw:text-box><text:p>Twee keer per jaar</text:p></draw:text-box></draw:frame>"
        "</draw:page></office:presentation>"
    )
    assert tekst.tekst_uit_odf(inhoud) == "Awareness-training\nTwee keer per jaar"


def test_odf_zonder_tekst_levert_lege_string() -> None:
    """Geen `LeegDocumentError` hier: de caller beslist wat leeg betekent, net als bij pdf."""
    inhoud = _odf("<office:drawing><draw:page/></office:drawing>")
    assert tekst.tekst_uit_odf(inhoud) == ""


def test_doctype_wordt_geweigerd() -> None:
    """Entity-expansie: `ElementTree` blokkeert die niet, dus de DOCTYPE wordt geweigerd.

    Gemeten op 2026-08-22 tegen de PROPFIND-parser: een kleine bom leverde 3000 tekens op.
    Een ODF-bestand komt van een gedeelde schijf waar iedereen kan uploaden, dus dezelfde regel.
    """
    inhoud = _odf(
        "<office:text><text:p>x</text:p></office:text>",
        prolog='<?xml version="1.0"?><!DOCTYPE office:document-content [<!ENTITY a "aaa">]>',
    )
    with pytest.raises(tekst.OnleesbaarDocumentError, match="DOCTYPE"):
        tekst.tekst_uit_odf(inhoud)


def test_te_grote_content_xml_wordt_geweigerd() -> None:
    """De grens geldt op de uitgepakte grootte, niet op de zip: dat is de zip-bom-kant."""
    groot = "<text:p>" + "a" * (tekst.MAX_ODF_INHOUD + 1) + "</text:p>"
    inhoud = _odf(f"<office:text>{groot}</office:text>")
    assert len(inhoud) < tekst.MAX_ODF_INHOUD  # de zip zelf is klein — comprimeert weg
    with pytest.raises(tekst.OnleesbaarDocumentError, match="overschrijdt"):
        tekst.tekst_uit_odf(inhoud)


def test_zonder_content_xml_wordt_geweigerd() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_bestand:
        zip_bestand.writestr("mimetype", "application/vnd.oasis.opendocument.text")
    with pytest.raises(tekst.OnleesbaarDocumentError, match=r"content\.xml"):
        tekst.tekst_uit_odf(buffer.getvalue())


def test_geen_zip_wordt_geweigerd() -> None:
    with pytest.raises(tekst.OnleesbaarDocumentError):
        tekst.tekst_uit_odf(b"dit is geen zip")


@pytest.mark.parametrize(
    "mime",
    [
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
        "application/vnd.oasis.opendocument.graphics",
    ],
)
def test_lees_bytes_kiest_de_odf_lezer(mime: str) -> None:
    """Zonder deze koppeling zou `lees_bytes` de zip als utf-8 decoderen: onzin, geen fout."""
    inhoud = _odf("<office:text><text:p>Toegangsbeleid</text:p></office:text>")
    assert tekst.lees_bytes(inhoud, mime) == "Toegangsbeleid"


def test_odf_is_geen_gescand_formaat() -> None:
    """ "Mogelijk een scan" hoort niet bij een odt; die melding is voor pdf."""
    reden = tekst.leeg_reden("application/vnd.oasis.opendocument.text")
    assert "scan" not in reden
