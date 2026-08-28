"""Een adres zoals een mens het opschrijft, werkt.

De auditor vulde `www.conduction.nl` in en de bron leverde nul pagina's: `urljoin` maakt van een
adres zonder schema `/sitemap.xml`, en dat is geen URL. De melding klopte wél — *"sitemap niet op
te halen: No scheme supplied"* — maar een tool dat een normale schrijfwijze afwijst en dan
netjes uitlegt waarom, heeft nog steeds nul pagina's gelezen.

`https://` is de juiste aanname en niet `http://`: een auditbron over een publieke website moet
niet stilletjes onversleuteld ophalen. Staat er wél een schema, dan blijft dat staan — ook
`http://`, want dat kan een bewuste keuze zijn voor een interne omgeving, en dat overrulen zou
een stille wijziging van de scope zijn.
"""

from __future__ import annotations

import pytest

from iso_audit.sources.website import normaliseer_adres


@pytest.mark.parametrize(
    ("ingevuld", "verwacht"),
    [
        ("www.conduction.nl", "https://www.conduction.nl"),
        ("conduction.nl", "https://conduction.nl"),
        ("https://www.conduction.nl", "https://www.conduction.nl"),
        ("https://www.conduction.nl/", "https://www.conduction.nl"),
        ("  www.conduction.nl  ", "https://www.conduction.nl"),
    ],
)
def test_een_adres_krijgt_een_schema(ingevuld: str, verwacht: str) -> None:
    assert normaliseer_adres(ingevuld) == verwacht


def test_een_expliciet_http_adres_blijft_http() -> None:
    """Overrulen zou een stille wijziging van de auditscope zijn."""
    assert normaliseer_adres("http://intern.example") == "http://intern.example"


def test_de_bron_leest_een_adres_zonder_schema() -> None:
    """De hele reden dat deze functie bestaat."""
    from iso_audit.sources.website import WebsiteSource

    bron = WebsiteSource(["www.conduction.nl"])
    gezondheid = bron.healthcheck()
    assert gezondheid["locaties"] == [{"naam": "https://www.conduction.nl"}]
