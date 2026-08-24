"""Elk veld in de bron-catalogus moet een `Veld` in `settings.VELDEN` hebben.

Zonder die koppeling is een bron wél in te vullen in het portaal maar **overleeft de
configuratie geen herstart**. `load_config()` haalt de opgeslagen waarden op via
`ui_waarden()` en `Settings.naar_omgeving()` schrijft ze in `os.environ` — maar alleen voor
velden die in `VELDEN` staan. Wat daar niet in staat, komt bij het opstarten nooit in de
omgeving, en de adapter leest bij `__init__` uit de omgeving.

Gemeten op 2026-08-24: Nextcloud stond in de catalogus en niet in `VELDEN`. De koppeling
werkte tot de pod herstartte voor een nieuwe versie, en daarna las de bron als "niet
gekoppeld" terwijl `bron_config.json` op de PVC alle drie de velden bevatte. Het werkte tot
dat moment omdat `BronConfig.zet()` de waarde bij het opslaan direct in `os.environ` schrijft:
hetzelfde proces, dus dezelfde omgeving.

Dit is de reden dat de test op de **catalogus** zit en niet op één bron: de volgende adapter
die iemand toevoegt loopt in precies dezelfde val, en die valt pas op na een herstart —
wanneer niemand meer aan de nieuwe bron denkt.
"""

from __future__ import annotations

from iso_audit.api import bron_catalogus
from iso_audit.config import settings


def _catalogus_velden() -> list[tuple[str, bool]]:
    """Per catalogusveld de env-naam en of het geheim is."""
    return [(veld.naam, veld.geheim) for bron in bron_catalogus.STANDAARD for veld in bron.velden]


def _settings_velden() -> list[tuple[str, bool]]:
    return [(veld.env, veld.geheim) for veld in settings.VELDEN]


def test_elk_catalogusveld_heeft_een_settings_veld() -> None:
    ontbreekt = sorted({n for n, _ in _catalogus_velden()} - {n for n, _ in _settings_velden()})
    assert not ontbreekt, (
        "deze env-vars zijn in het portaal in te vullen maar overleven geen herstart, "
        f"omdat ze niet in settings.VELDEN staan: {ontbreekt}"
    )


def test_geheime_velden_zijn_aan_beide_kanten_geheim() -> None:
    """Een wachtwoord dat in de catalogus geheim is en in de settings niet, lekt.

    De catalogus bepaalt of het invoerveld gemaskeerd is; `Settings` bepaalt of de waarde in
    de herkomst-uitvoer en op de `/config`-route zichtbaar is. Lopen die twee uiteen, dan is
    het veld in de UI gemaskeerd en elders leesbaar.
    """
    geheim_catalogus = {n for n, geheim in _catalogus_velden() if geheim}
    geheim_settings = {n for n, geheim in _settings_velden() if geheim}
    afwijkend = sorted(geheim_catalogus - geheim_settings)
    assert not afwijkend, f"geheim in de catalogus maar niet in settings.VELDEN: {afwijkend}"
