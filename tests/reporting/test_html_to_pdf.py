"""Tests voor `iso_audit.reporting.html_to_pdf`.

**Deze tests renderen echt.** De vorige versie mockte de renderer weg in elke test, en daardoor
bleef de suite groen terwijl PDF-generatie in het productie-image onmogelijk was: er zat geen
Chrome in het image, en de enige plek waar dat bleek was een `logger.warning` aan het eind van
een run (gemeten 2026-08-24: "PDF-conversie mislukt: Geen Chrome/Chromium gevonden"). Een test
die de renderer wegmockt toetst de argumentenlijst en niet of er een PDF uitkomt.
"""

from __future__ import annotations

from pathlib import Path

import pypdf
import pytest

from iso_audit.reporting import html_to_pdf, md_to_html

_HTML = """<!DOCTYPE html><html lang="nl"><head><meta charset="utf-8"><title>t</title></head>
<body><h1>Auditrapport</h1><p>Clausule 5.11 is gedekt.</p></body></html>"""


def test_er_komt_een_leesbare_pdf_uit(tmp_path: Path) -> None:
    html = tmp_path / "rapport.html"
    html.write_text(_HTML, encoding="utf-8")

    resultaat = Path(html_to_pdf.converteer(html))

    assert resultaat == tmp_path / "rapport.pdf"
    assert resultaat.read_bytes().startswith(b"%PDF")
    lezer = pypdf.PdfReader(str(resultaat))
    assert len(lezer.pages) >= 1
    assert "Auditrapport" in (lezer.pages[0].extract_text() or "")


def test_expliciete_uitvoer(tmp_path: Path) -> None:
    html = tmp_path / "in.html"
    html.write_text(_HTML, encoding="utf-8")
    uit = tmp_path / "uit" / "elders.pdf"
    uit.parent.mkdir()

    assert Path(html_to_pdf.converteer(html, uit)) == uit
    assert uit.read_bytes().startswith(b"%PDF")


def test_ontbrekende_invoer(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        html_to_pdf.converteer(tmp_path / "niets.html")


def test_geen_externe_browser_meer_nodig() -> None:
    """Gate: de renderer mag niet weer een binary buiten het image worden.

    Chrome was de vorige keuze en die stond niet in het image. WeasyPrint is een dependency met
    zijn systeembibliotheken al in het Dockerfile, dus `uv sync` en `docker build` garanderen
    samen dat de renderer aanwezig is. Een `subprocess`-aanroep zou die garantie weer opgeven.
    """
    bron = Path(html_to_pdf.__file__).read_text(encoding="utf-8")
    assert "subprocess" not in bron
    assert "shutil.which" not in bron
    # De docstring noemt Chrome wel — als geschiedenis, met de meting erbij. Wat niet mag
    # terugkomen is het opzoeken en aanroepen van een binary.


def test_print_css_zet_de_grid_uit(tmp_path: Path) -> None:
    """Regressie: `.page { display: block }` in het print-blok is 8 minuten waard.

    Gemeten op 2026-08-24 tegen het echte rapport van die dag (767 KB HTML, 345 pagina's):
    met `display: grid` in print liep de render langer dan acht minuten, met `display: block`
    duurde hij 16 seconden. Zelfde HTML, zelfde inhoud, één declaratie verschil — WeasyPrint
    legt een grid-container niet over paginagrenzen uiteen en probeert het hele document als
    één grid-item te plaatsen.

    Het print-blok verborg de TOC en zette al één kolom; alleen `display` bleef staan. Daarom
    toetst deze test die declaratie en niet de rendertijd: een tijdslimiet in een test is
    afhankelijk van de machine, en dit is de oorzaak zelf.
    """
    print_blok = md_to_html.CSS.split("@media print")[1]
    regel = print_blok.split(".page")[1].split("}")[0]
    assert "display: block" in regel, f"print-blok mist display:block op .page: {regel!r}"


def test_paginagrootte_staat_vast(tmp_path: Path) -> None:
    """A4 en niet Letter: het rapport gaat naar Nederlandse auditors en printers."""
    assert "@page" in md_to_html.CSS
    assert "A4" in md_to_html.CSS
