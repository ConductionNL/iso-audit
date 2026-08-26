"""Een bron die nog niet is ingevuld, zegt dát — niet dat de verbinding faalde.

Op 2026-08-26 toonde het configuratiescherm voor `website` en `repo`: *"De verbinding kon niet
worden gelegd. Zie het serverlog voor details."* Er was niets mis met een verbinding; er stond
alleen nog geen adres in. Bij `website` is dat extra verwarrend, want die heeft geen token nodig
— dan zoekt een auditor naar een credential die niet bestaat.

De oorzaak was niet de tekst maar het ontbreken van `soort`. `_check_source` haalt elke
adapter-reden zonder `soort` door de normalisatie, en dat mechanisme is er met goede reden: tot
2026-08-14 landde een Jira-401 mét tenant-URL en responsbody rechtstreeks in de browser. Wie zijn
eigen `soort` meestuurt, verklaart daarmee dat de tekst van hem is en geen credentials draagt.
"""

from __future__ import annotations

from iso_audit.sources.repo import RepoSource
from iso_audit.sources.website import WebsiteSource


def test_de_reden_van_de_website_overleeft_de_normalisatie() -> None:
    from iso_audit.api.session import _check_source

    gezondheid = _check_source("website")
    assert gezondheid["soort"] == "niet_geconfigureerd"
    assert "geen token nodig" in str(gezondheid["reden"])
    assert "serverlog" not in str(gezondheid["reden"])


def test_de_reden_van_de_repobron_overleeft_de_normalisatie() -> None:
    from iso_audit.api.session import _check_source

    gezondheid = _check_source("repo")
    assert gezondheid["soort"] == "niet_geconfigureerd"
    assert "forge:eigenaar/naam" in str(gezondheid["reden"])


def test_de_adapters_zetten_zelf_een_soort() -> None:
    """Zonder `soort` wordt de tekst vervangen; dat is de val waar dit in liep."""
    for bron in (WebsiteSource([]), RepoSource([])):
        gezondheid = bron.healthcheck()
        assert gezondheid.get("soort"), bron.naam


def test_de_website_noemt_geen_token() -> None:
    """Een website is publiek; naar een credential laten zoeken is het verkeerde spoor."""
    reden = str(WebsiteSource([]).healthcheck()["reden"])
    assert "geen token nodig" in reden
