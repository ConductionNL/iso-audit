"""Repo- en websitedocumenten dragen een wijzigingstijd, zodat een herhaalde run ze overslaat.

Gemeten op 2026-08-29: alle 2.207 repo-documenten en 175 websitedocumenten in de database hadden
een lege `modified_at`, tegen 0 van de 439 Drive-documenten. `mag_overslaan` vergelijkt die tijd
met wat er is opgeslagen — zonder tijd kan hij nooit overslaan, dus haalde élke run alles opnieuw
op. Dat is de reden dat de tweede run over dezelfde 385 repository's weer zestien minuten deed.

De gegevens zijn er wel:

- GitHub en Forgejo geven per repository `pushed_at`. Is er sinds de vorige run niet gepusht, dan
  zijn de bestanden niet gewijzigd — dat is precies de vraag die `mag_overslaan` stelt.
- Een sitemap geeft `<lastmod>` per pagina. conduction.nl vult dat.

Ontbreekt de tijd, dan blijft het veld leeg en wordt er gewoon opnieuw gelezen. Een verzonnen
tijdstempel zou een document als "ongewijzigd" laten gelden terwijl niemand dat weet — dezelfde
regel als bij de bronnen zonder wijzigingstijd in `incrementele-ingest`.
"""

from __future__ import annotations

from iso_audit.sources.website import urls_uit_sitemap_met_datum

_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.nl/privacy/</loc><lastmod>2026-08-11</lastmod></url>
  <url><loc>https://x.nl/terms/</loc></url>
</urlset>"""


def test_de_sitemap_levert_de_wijzigingsdatum() -> None:
    assert urls_uit_sitemap_met_datum(_SITEMAP) == [
        ("https://x.nl/privacy/", "2026-08-11"),
        ("https://x.nl/terms/", ""),
    ]


def test_een_pagina_zonder_lastmod_krijgt_geen_verzonnen_datum() -> None:
    """Liever elke run opnieuw lezen dan een document ten onrechte overslaan."""
    assert urls_uit_sitemap_met_datum(_SITEMAP)[1][1] == ""


def test_de_websitebron_zet_de_datum_op_het_document() -> None:
    from iso_audit.sources.website import WebsiteSource

    bron = WebsiteSource(["https://x.nl"])
    bron._urls = lambda site: [  # type: ignore[method-assign]
        ("https://x.nl/privacy/", "2026-08-11")
    ]
    bron._robots = lambda site: type("R", (), {"can_fetch": lambda *a: True})()  # type: ignore[method-assign]
    docs = list(bron.list_documents())
    assert docs[0].laatst_gewijzigd == "2026-08-11"


def test_de_repobron_gebruikt_pushed_at() -> None:
    """Is er sinds de vorige run niet gepusht, dan zijn de bestanden niet gewijzigd."""
    from iso_audit.clients.forge import Repositoriegegevens, Wijzigingen
    from iso_audit.sources.repo import RepoSource

    class _Client:
        forge = "github"

        def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
            return Repositoriegegevens(
                naam=f"{eigenaar}/{naam}",
                forge="github",
                url="",
                prive=False,
                gearchiveerd=False,
                hoofdbranch="main",
                gewijzigd="2026-08-20T10:00:00Z",
            )

        def repositories(self, eigenaar: str) -> tuple[list[str], str]:
            return ["y"], ""

        def paden(self, eigenaar: str, naam: str) -> tuple[list[str], str]:
            return ["README.md"], ""

        def bestand(self, eigenaar: str, naam: str, pad: str) -> object: ...

        def bestanden_in_map(self, e: str, n: str, m: str) -> tuple[list[str], str]:
            return [], ""

        def wijzigingen(self, e: str, n: str, a: int) -> Wijzigingen:
            return Wijzigingen()

    bron = RepoSource([{"forge": "github", "eigenaar": "x", "naam": "y"}])
    bron._clients["github"] = _Client()  # type: ignore[assignment]
    docs = list(bron.list_documents())
    assert docs, "geen documenten"
    assert all(d.laatst_gewijzigd == "2026-08-20T10:00:00Z" for d in docs), [
        (d.titel, d.laatst_gewijzigd) for d in docs
    ]
