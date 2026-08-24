"""Elke adapter in het pakket moet ook echt in de registry komen.

De `@register`-decorator draait pas als de module geïmporteerd is, en dat gebeurt via een
hardgecodeerde lijst. Staat een adapter daar niet in, dan bestaat hij niet voor
`sources.get(naam)` — zonder foutmelding bij het opstarten, alleen een `KeyError` op het moment
dat iemand hem gebruikt.

Dat is twee keer misgegaan op 2026-08-24: `scripts/preflight.py` meldde Jira als niet
beschikbaar, en een los meetproces kreeg `Source-adapter 'nextcloud' niet geregistreerd.
Beschikbaar: drive`. In beide gevallen was de adapter er gewoon; hij was alleen niet
geïmporteerd.

Deze test vergelijkt de lijst met wat er in het pakket staat, zodat de volgende adapter niet
stil buiten de boot valt.
"""

from __future__ import annotations

import pkgutil

import iso_audit.sources
from iso_audit.sources import laad_adapters

# Modules in `iso_audit.sources` die géén Source-adapter zijn.
_GEEN_ADAPTER = {
    "base",  # het protocol zelf
    "protocol_ingest",  # de brug naar de pipeline
    "tekst",  # gedeelde lezers, geen bron
    "opvolgpunten",  # pseudo-source, eigen ingang
}


def _adaptermodules() -> set[str]:
    return {
        naam
        for _, naam, _ in pkgutil.iter_modules(iso_audit.sources.__path__)
        if naam not in _GEEN_ADAPTER and not naam.startswith("_")
    }


def test_elke_adaptermodule_staat_geregistreerd_na_bootstrap() -> None:
    laad_adapters()
    geregistreerd = set(iso_audit.sources.available())
    ontbreekt = sorted(_adaptermodules() - geregistreerd)
    assert not ontbreekt, (
        f"deze adapters bestaan als module maar niet in de registry: {ontbreekt} — "
        "vul `_ADAPTERMODULES` in `iso_audit/sources/__init__.py` aan"
    )


def test_bootstrap_is_idempotent() -> None:
    laad_adapters()
    eerste = sorted(iso_audit.sources.available())
    laad_adapters()
    assert sorted(iso_audit.sources.available()) == eerste
