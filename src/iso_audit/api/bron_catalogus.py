"""Welke velden een bron nodig heeft — declaratief, en te overrulen met YAML.

De **catalogus** zegt *wat* je per bron moet invullen (label, env-var, geheim of niet).
De **waarden** staan ergens anders (`bron_config.py`), want die zijn van de auditor en
niet van de beheerder.

Die scheiding is het punt: een beheerder richt bij initialisatie de catalogus in — of
laat `scripts/genereer-bron-catalogus.sh` hem schrijven — en daarna kan een auditor
bronnen koppelen zonder iets van env-vars, Secrets of een cluster te weten.

Volgorde van waarheid:

1. het YAML-bestand op ``ISO_AUDIT_BRON_CATALOGUS``, als dat gezet en leesbaar is;
2. anders de ingebouwde standaard hieronder.

De standaard staat in code zodat het portaal uit de doos werkt. Het YAML-bestand maakt
het aanpasbaar zonder codewijziging — nodig omdat dit tool aan derden geleverd wordt en
niet iedereen dezelfde bronnen of veldnamen heeft.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

CATALOGUS_ENV = "ISO_AUDIT_BRON_CATALOGUS"
"""Pad naar een YAML-catalogus die de ingebouwde standaard vervangt."""


@dataclass(frozen=True, slots=True)
class Veld:
    """Eén invulveld van een bron."""

    naam: str
    """Env-var die de adapter leest, bv. ``JIRA_API_TOKEN``."""

    label: str
    """Wat de auditor ziet. Geen env-var-namen in de UI."""

    geheim: bool = False
    """Geheime velden worden nooit teruggegeven; de UI toont 'ingesteld'."""

    verplicht: bool = True
    hint: str = ""
    """Korte uitleg, als tooltip. Niet de plek voor implementatiedetails."""


@dataclass(frozen=True, slots=True)
class BronDefinitie:
    """Wat er nodig is om één bron te koppelen."""

    naam: str
    label: str
    uitleg: str = ""
    velden: list[Veld] = field(default_factory=list)

    eigen_kaart: bool = False
    """Heeft een eigen scherm in de UI en hoort niet in de generieke bronnenlijst.
    Anders staat hetzelfde veld twee keer, met twee kanten die kunnen afwijken."""


# Ingebouwde standaard. De env-var-namen komen uit de adapters zelf
# (`sources/jira.py`, `miro/client.py`, `sources/drive.py`, `sources/planning.py`);
# staat er hier iets anders dan de adapter leest, dan koppelt de bron niet — daarom
# is dit één lijst en geen tweede administratie per bron.
STANDAARD: list[BronDefinitie] = [
    BronDefinitie(
        naam="drive",
        label="Google Drive",
        uitleg="Beleid, procedures en werkinstructies uit een auditmap.",
        velden=[
            Veld(
                naam="AUDIT_SOURCE_FOLDER_ID",
                label="Map-ID van de auditmap",
                hint="Het laatste deel van de Drive-URL van de map.",
            ),
            Veld(
                naam="GWS_IMPERSONATE_EMAIL",
                label="Namens wie lezen (optioneel)",
                verplicht=False,
                hint=(
                    "Leeg = alleen wat expliciet met het service-account gedeeld is. "
                    "Gevuld vraagt eenmalige autorisatie door een Workspace-beheerder."
                ),
            ),
        ],
    ),
    BronDefinitie(
        naam="planning",
        label="Auditplanning (Google Sheets)",
        uitleg="De planning per norm en jaar; bepaalt welke clausules wanneer aan bod komen.",
        velden=[
            Veld(
                naam="AUDIT_PLANNING_SHEETS_ID",
                label="Spreadsheet-ID van de planning",
                hint="Het lange deel van de Sheets-URL.",
            ),
        ],
    ),
    BronDefinitie(
        naam="jira",
        label="Jira",
        uitleg="Tickets als bewijs, bijvoorbeeld ISO-verbeteracties.",
        velden=[
            Veld(
                naam="JIRA_BASE_URL", label="Jira-adres", hint="https://organisatie.atlassian.net"
            ),
            Veld(
                naam="JIRA_USER_EMAIL",
                label="Service-account e-mail",
                hint=(
                    "Bij voorkeur een functioneel account, geen persoon: dan blijft de "
                    "koppeling werken als iemand de organisatie verlaat."
                ),
            ),
            Veld(naam="JIRA_API_TOKEN", label="API-token", geheim=True),
            Veld(
                naam="JIRA_PROJECTS",
                label="Projecten",
                verplicht=False,
                hint="Komma-gescheiden, bv. ISO. Leeg = alle projecten.",
            ),
        ],
    ),
    BronDefinitie(
        naam="miro",
        label="Miro",
        uitleg="Bevindingen van een auditbord, alleen lezen.",
        velden=[Veld(naam="MIRO_API_TOKEN", label="API-token", geheim=True)],
    ),
    # Geen bron maar wel configuratie, en het heeft een eigen kaart in de UI omdat de
    # keuze tussen abonnement en API-key uitleg vraagt die niet in een tooltip past.
    BronDefinitie(
        naam="anthropic",
        label="Claude (Anthropic)",
        uitleg="Classificatie en memo-tekst.",
        eigen_kaart=True,
        velden=[
            Veld(
                naam="ANTHROPIC_AUTH_MODE",
                label="Manier van inloggen",
                verplicht=False,
                hint="api_key werkt ook zonder browser; sso gebruikt een Claude-abonnement.",
            ),
            Veld(naam="ANTHROPIC_API_KEY", label="API-key", geheim=True, verplicht=False),
            Veld(
                naam="AUDIT_CLASSIFICATION_MODEL",
                label="Model",
                verplicht=False,
                hint="Haiku is het snelst en goedkoopst; grotere modellen kosten meer per run.",
            ),
        ],
    ),
]


def _uit_yaml(data: Any) -> list[BronDefinitie]:
    bronnen: list[BronDefinitie] = []
    for item in data.get("bronnen", []) or []:
        velden = [
            Veld(
                naam=str(v["naam"]),
                label=str(v.get("label", v["naam"])),
                geheim=bool(v.get("geheim", False)),
                verplicht=bool(v.get("verplicht", True)),
                hint=str(v.get("hint", "")),
            )
            for v in item.get("velden", []) or []
        ]
        bronnen.append(
            BronDefinitie(
                naam=str(item["naam"]),
                label=str(item.get("label", item["naam"])),
                uitleg=str(item.get("uitleg", "")),
                eigen_kaart=bool(item.get("eigen_kaart", False)),
                velden=velden,
            )
        )
    return bronnen


def catalogus() -> list[BronDefinitie]:
    """De actieve catalogus: YAML als die er is, anders de ingebouwde standaard.

    Een onleesbaar of ongeldig YAML-bestand valt terug op de standaard in plaats van het
    portaal te breken — configuratie kunnen zien is belangrijker dan een strikte lezing
    van een bestand dat een beheerder kan repareren.
    """
    pad = os.environ.get(CATALOGUS_ENV)
    if pad and Path(pad).is_file():
        try:
            data = yaml.safe_load(Path(pad).read_text(encoding="utf-8")) or {}
            bronnen = _uit_yaml(data)
            if bronnen:
                return bronnen
        except (yaml.YAMLError, KeyError, TypeError):
            pass
    return STANDAARD


def definitie(naam: str) -> BronDefinitie | None:
    return next((b for b in catalogus() if b.naam == naam), None)


def naar_yaml(bronnen: list[BronDefinitie] | None = None) -> str:
    """Serialiseer een catalogus naar YAML — de vorm die een beheerder aanpast."""
    lijst = bronnen if bronnen is not None else STANDAARD
    return yaml.safe_dump(
        {"bronnen": [asdict(b) for b in lijst]},
        allow_unicode=True,
        sort_keys=False,
    )
