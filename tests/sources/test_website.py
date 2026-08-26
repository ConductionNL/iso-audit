"""De website-bron: wat de organisatie publiek belooft, zonder crawler.

Een publieke toezegging is een verplichting. Privacyverklaring, securitypagina, een claim over
certificering — dat zijn externe beloften die tegen de interne praktijk horen (§5.31, §5.34, en
9001 §8.2). Het gat daartussen is een klassieke NC die dit tool structureel miste, niet omdat hij
moeilijk te zien is maar omdat de bron er niet was.

Gemeten op 2026-08-26: conduction.nl heeft een sitemap met 146 URL's, waaronder `/privacy/`,
`/terms/` en `/quality/`. `robots.txt` staat alles toe.

Wat hier bewaakt wordt is dat dit een *lezer* blijft en geen crawler: geen links volgen, robots
respecteren, en niets stil overslaan.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from iso_audit.sources.website import WebsiteSource, urls_uit_sitemap, zichtbare_tekst

_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.conduction.nl/privacy/</loc></url>
  <url><loc>https://www.conduction.nl/terms/</loc></url>
</urlset>"""


def test_de_sitemap_levert_de_paginas() -> None:
    assert urls_uit_sitemap(_SITEMAP) == [
        "https://www.conduction.nl/privacy/",
        "https://www.conduction.nl/terms/",
    ]


def test_een_sitemap_met_doctype_wordt_geweigerd() -> None:
    """ElementTree blokkeert entity-expansie niet; zelfde regel als bij ODF."""
    with pytest.raises(ValueError, match="DOCTYPE"):
        urls_uit_sitemap('<!DOCTYPE foo [<!ENTITY a "b">]><urlset/>')


def test_kapotte_xml_is_een_nette_fout() -> None:
    with pytest.raises(ValueError, match="geldige XML"):
        urls_uit_sitemap("<urlset><url>")


def test_de_tekst_wordt_zonder_markup_opgeslagen() -> None:
    """Opgeslagen markup maakt elke latere zoekopdracht onbetrouwbaar."""
    tekst = zichtbare_tekst("<html><body><h1>Privacy</h1><p>Wij verwerken.</p></body></html>")
    assert tekst == "Privacy Wij verwerken."


def test_script_en_style_tellen_niet_mee_als_tekst() -> None:
    ruw = "<style>.a{color:red}</style><script>var x=1</script><p>Beleid</p>"
    assert zichtbare_tekst(ruw) == "Beleid"


def test_de_bron_volgt_geen_links() -> None:
    """Een crawler is niet te begrenzen, niet te herhalen en niet uit te leggen."""
    bron = Path("src/iso_audit/sources/website.py").read_text(encoding="utf-8")
    for verdacht in ("findall(r'<a", 'href=', "urljoin(url"):
        assert verdacht not in bron.replace("Links volgen", ""), verdacht


def test_zonder_websites_is_de_bron_niet_gekoppeld() -> None:
    assert WebsiteSource([]).healthcheck()["status"] == "niet_gekoppeld"


def test_geconfigureerde_sites_staan_in_de_health() -> None:
    gezondheid = WebsiteSource(["https://conduction.nl"]).healthcheck()
    assert gezondheid["status"] == "ok"
    assert gezondheid["locaties"] == [{"naam": "https://conduction.nl"}]


def test_een_komma_gescheiden_lijst_werkt_ook() -> None:
    """De env-var is het opslagformaat; in de UI staan het losse rijen, zoals bij Drive."""
    bron = WebsiteSource("https://a.example, https://b.example")
    assert len(bron.healthcheck()["locaties"]) == 2  # type: ignore[arg-type]


def test_de_bron_levert_geen_kant_en_klare_bevindingen() -> None:
    assert list(WebsiteSource([]).list_findings("s1")) == []
