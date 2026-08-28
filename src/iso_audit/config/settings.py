"""Eén loader, drie bronnen, vastgelegde precedence.

## De volgorde

``environment > config.yaml > UI-store > default``

De eerste bron met een niet-lege waarde wint. Environment staat bovenaan zodat een
deployment nooit stil een via-de-UI ingevulde waarde gebruikt: wat een beheerder expliciet
zette, weegt zwaarder dan wat er ooit is ingetypt.

## Waarom herkomst in de waarde zit

Een `Waarde` draagt zijn eigen `bron`. De alternatieve opzet — een dict met waarden plus
een tweede dict met herkomsten — is één administratie te veel: bij elke transformatie kan
de herkomst wegvallen zonder dat een test dat merkt. Zo kan een veld niet gebruikt worden
zonder dat zijn herkomst meekomt.

## Waarom geheimen hier niet uit te lezen zijn

`Waarde.__repr__` toont de waarde nooit als het veld geheim is. Een geheim dat in een
f-string, een assert-melding of een stacktrace belandt, staat daarna in een logbestand dat
niemand meer opruimt. Dit is dus geen discipline maar een structurele grens — hetzelfde
idee als `api.audit_log.log_event`, die bewust alleen scalars aanneemt.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import yaml

from iso_audit import modellen

_log = logging.getLogger("iso_audit.audit")

Bron = Literal["ui-override", "env", "yaml", "ui", "default", "leeg"]
"""`ui-override` staat bewust náást `ui` en vervangt hem niet: het verschil tussen "hier
ingevuld" en "hier ingevuld terwijl een beheerder iets anders had gezet" is precies wat
een auditor achteraf moet kunnen zien."""
"""Waar een waarde vandaan komt. `leeg` = nergens gezet en geen default."""

CONFIG_YAML_ENV = "ISO_AUDIT_CONFIG"
"""Pad naar `config.yaml`. Niet gezet = `config.yaml` naast de audits-root."""

SCHEMA_VERSIE = 1
"""Versie die deze code kent. Een hoger nummer in een bestand wordt gemeld."""

GEHEIM_VERVANGING = "<geheim>"


@dataclass(frozen=True, slots=True)
class Waarde:
    """Eén opgeloste configuratiewaarde plus waar hij vandaan komt."""

    waarde: str
    bron: Bron
    geheim: bool = False

    @property
    def ingesteld(self) -> bool:
        return bool(self.waarde)

    def __repr__(self) -> str:
        """Toon een geheime waarde nooit — ook niet in een stacktrace."""
        zichtbaar = GEHEIM_VERVANGING if self.geheim else repr(self.waarde)
        return f"Waarde(waarde={zichtbaar}, bron={self.bron!r})"

    __str__ = __repr__


def _leeg(*, geheim: bool = False) -> Waarde:
    return Waarde(waarde="", bron="leeg", geheim=geheim)


@dataclass(frozen=True, slots=True)
class Veld:
    """Definitie van één configuratieveld: waar het staat en of het geheim is."""

    sleutel: str
    """Puntpad in `config.yaml` en in de herkomst-log, bv. `jira.api_token`."""

    env: str
    """Env-var die de adapters lezen. Deze naam is het contract; niet hernoemen."""

    geheim: bool = False
    default: str = ""


# De env-namen zijn wat de adapters daadwerkelijk lezen — `sources/jira.py`,
# `auth.py`, `classification/findings.py`. Staat hier iets anders, dan koppelt de
# bron niet. Daarom is dit één lijst en geen tweede administratie.
#
# Wat hier ontbreekt maar wél in `api/bron_catalogus.py` staat, is in het portaal in te
# vullen en verdwijnt bij de eerste herstart: `load_config()` schrijft alleen deze velden
# naar `os.environ`, en `BronConfig.zet()` doet dat verder alleen in het lopende proces.
# Zo verloor Nextcloud op 2026-08-24 zijn koppeling bij een versie-uitrol terwijl
# `bron_config.json` op de PVC nog compleet was. `JIRA_PROJECTS` en `NEXTCLOUD_PATHS`
# hadden hetzelfde gat. `tests/config/test_catalogus_settings_koppeling.py` bindt de twee
# lijsten aan elkaar, zodat de volgende adapter niet dezelfde weg gaat.
VELDEN: tuple[Veld, ...] = (
    Veld("gws.impersonate_email", "GWS_IMPERSONATE_EMAIL"),
    Veld("jira.base_url", "JIRA_BASE_URL"),
    Veld("jira.account_email", "JIRA_USER_EMAIL"),
    Veld("jira.api_token", "JIRA_API_TOKEN", geheim=True),
    Veld("jira.projects", "JIRA_PROJECTS"),
    Veld("nextcloud.base_url", "NEXTCLOUD_BASE_URL"),
    Veld("nextcloud.user", "NEXTCLOUD_USER"),
    Veld("nextcloud.app_password", "NEXTCLOUD_APP_PASSWORD", geheim=True),
    Veld("nextcloud.paths", "NEXTCLOUD_PATHS"),
    Veld("miro.api_token", "MIRO_API_TOKEN", geheim=True),
    Veld("repo.repositories", "REPO_LOCATIES"),
    Veld("repo.github_token", "REPO_GITHUB_TOKEN", geheim=True),
    Veld("repo.github_app_id", "REPO_GITHUB_APP_ID"),
    Veld("repo.github_app_installation_id", "REPO_GITHUB_APP_INSTALLATION_ID"),
    Veld("repo.github_app_private_key", "REPO_GITHUB_APP_PRIVATE_KEY", geheim=True),
    Veld("repo.codeberg_token", "REPO_CODEBERG_TOKEN", geheim=True),
    Veld("repo.max_pr", "REPO_MAX_PR"),
    Veld("website.urls", "WEBSITE_URLS"),
    Veld("website.max_paginas", "WEBSITE_MAX_PAGINAS"),
    Veld("drive.folder_id", "AUDIT_SOURCE_FOLDER_ID"),
    Veld("planning.sheets_id", "AUDIT_PLANNING_SHEETS_ID"),
    Veld("anthropic.auth_mode", "ANTHROPIC_AUTH_MODE", default="api_key"),
    Veld("anthropic.api_key", "ANTHROPIC_API_KEY", geheim=True),
    Veld("anthropic.model", "AUDIT_CLASSIFICATION_MODEL", default=modellen.STANDAARD),
)

API_KEY_ENV = "ANTHROPIC_API_KEY"
AUTH_MODE_SLEUTEL = "anthropic.auth_mode"


@dataclass(frozen=True, slots=True)
class Settings:
    """Alle opgeloste configuratie, per veld met herkomst."""

    velden: dict[str, Waarde] = field(default_factory=dict)
    config_version: int = SCHEMA_VERSIE

    def __getitem__(self, sleutel: str) -> Waarde:
        return self.velden.get(sleutel, _leeg())

    @property
    def auth_mode(self) -> str:
        return self[AUTH_MODE_SLEUTEL].waarde or "api_key"

    def naar_omgeving(self) -> None:
        """Zet de opgeloste waarden in ``os.environ`` voor de adapters.

        De Source-adapters lezen env-vars bij `__init__`. Door hier te schrijven blijven
        ze ongewijzigd werken — geen adapter hoeft te weten dat er een portaal bestaat.

        Bij auth-modus ``sso`` wordt de API-key-variabele **verwijderd**, niet alleen
        overgeslagen. De SDK laat een gezette key voorgaan op het CLI-profiel, óók een
        lege string; zonder verwijderen loopt een run stil op een credential die de
        auditor niet gekozen heeft.
        """
        for veld in VELDEN:
            waarde = self[veld.sleutel]
            if waarde.ingesteld:
                os.environ[veld.env] = waarde.waarde

        if self.auth_mode == "sso":
            os.environ.pop(API_KEY_ENV, None)


def _uit_env(veld: Veld, omgeving: Mapping[str, str]) -> Waarde | None:
    ruw = omgeving.get(veld.env)
    if ruw is None or not ruw.strip():
        return None
    return Waarde(waarde=ruw.strip(), bron="env", geheim=veld.geheim)


def _pak(data: Any, sleutel: str) -> str:
    """Lees een puntpad uit geneste yaml-data; ontbreekt het, geef een lege string."""
    huidig: Any = data
    for deel in sleutel.split("."):
        if not isinstance(huidig, dict) or deel not in huidig:
            return ""
        huidig = huidig[deel]
    return "" if huidig is None else str(huidig).strip()


def _laad_yaml(pad: Path) -> tuple[dict[str, Any], int]:
    """Lees `config.yaml`. Onleesbaar of ongeldig = leeg, niet fataal.

    Een kapot bestand mag het portaal niet tegenhouden: configuratie kunnen zien is
    belangrijker dan een strikte lezing van iets dat een beheerder kan repareren.
    """
    if not pad.is_file():
        return {}, SCHEMA_VERSIE
    try:
        data = yaml.safe_load(pad.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        _log.warning('{"event": "config_yaml_onleesbaar", "pad": "%s"}', pad)
        return {}, SCHEMA_VERSIE
    if not isinstance(data, dict):
        return {}, SCHEMA_VERSIE

    versie = data.get("config_version", SCHEMA_VERSIE)
    try:
        versie = int(versie)
    except (TypeError, ValueError):
        versie = SCHEMA_VERSIE
    if versie > SCHEMA_VERSIE:
        # Doorstarten, niet weigeren: een auditor die zijn configuratie niet kan zien
        # kan hem ook niet repareren.
        _log.warning(
            '{"event": "config_schema_nieuwer", "bestand": %d, "code": %d}',
            versie,
            SCHEMA_VERSIE,
        )
    return data, versie


def _yaml_pad(root: Path) -> Path:
    expliciet = os.environ.get(CONFIG_YAML_ENV)
    return Path(expliciet) if expliciet else root / "config.yaml"


def load_config(
    *,
    root: Path | str,
    ui_waarden: dict[str, str] | None = None,
    omgeving: Mapping[str, str] | None = None,
    overschrijvingen: set[str] | None = None,
) -> Settings:
    """Los alle configuratie op volgens ui-override > env > yaml > ui > default.

    `overschrijvingen` bevat env-namen die een auditor **expliciet** boven de omgeving
    heeft gezet. Zonder die mogelijkheid kan een geroteerde of ingetrokken credential niet
    vervangen worden zonder clusterbeheerder, en dan hangt de auditcapability weer aan een
    persoon. Het blijft niet stil: overschrijven is een aparte handeling, hij staat in het
    wijzigingsspoor, en de herkomst heet `ui-override` en niet `ui`.

    `ui_waarden` is per **env-naam** gesleuteld, want dat is wat de UI-store bewaart
    (`bron_config.json`). Zo hoeft die store niet te weten dat er puntpaden bestaan.

    `omgeving` is de omgeving die als *env-laag* geldt. Standaard is dat de live
    `os.environ`, wat klopt voor de CLI. Een langlopend proces moet hier de omgeving
    **van vóór de eerste `naar_omgeving()`** doorgeven: die methode schrijft opgeloste
    waarden terug in `os.environ`, dus zonder momentopname leest een tweede
    `load_config()` een UI-waarde terug als `bron="env"`. Dan meldt
    `/instellingen/herkomst` "door een beheerder gezet" over iets dat een auditor zelf
    intypte — precies de vraag die dat endpoint moet beantwoorden — en zou een
    blokkade op env-velden een UI-veld na één save onbewerkbaar maken.
    """
    root = Path(root)
    data, versie = _laad_yaml(_yaml_pad(root))
    ui = ui_waarden or {}
    env_laag: Mapping[str, str] = os.environ if omgeving is None else omgeving

    vervangen = overschrijvingen or set()

    opgelost: dict[str, Waarde] = {}
    for veld in VELDEN:
        expliciet = (ui.get(veld.env) or "").strip()
        if veld.env in vervangen and expliciet:
            opgelost[veld.sleutel] = Waarde(expliciet, "ui-override", geheim=veld.geheim)
            continue

        uit_env = _uit_env(veld, env_laag)
        if uit_env is not None:
            opgelost[veld.sleutel] = uit_env
            continue

        uit_yaml = _pak(data, veld.sleutel)
        if uit_yaml:
            if veld.geheim:
                # Werkt wel, maar een geheim in een repo-bestand is niet de bedoeling.
                _log.warning('{"event": "config_yaml_secret", "veld": "%s"}', veld.sleutel)
            opgelost[veld.sleutel] = Waarde(uit_yaml, "yaml", geheim=veld.geheim)
            continue

        uit_ui = (ui.get(veld.env) or "").strip()
        if uit_ui:
            opgelost[veld.sleutel] = Waarde(uit_ui, "ui", geheim=veld.geheim)
            continue

        if veld.default:
            opgelost[veld.sleutel] = Waarde(veld.default, "default", geheim=veld.geheim)
            continue

        opgelost[veld.sleutel] = _leeg(geheim=veld.geheim)

    return Settings(velden=opgelost, config_version=versie)


def met_waarde(settings: Settings, sleutel: str, waarde: Waarde) -> Settings:
    """Geef een kopie met één veld vervangen. Voor tests; Settings is immutable."""
    nieuw = dict(settings.velden)
    nieuw[sleutel] = waarde
    return replace(settings, velden=nieuw)
