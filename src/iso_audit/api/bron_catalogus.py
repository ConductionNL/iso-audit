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

    lijst: bool = False
    """Meerdere waarden, in de UI als rijen met een toevoeg- en verwijderactie.

    De opslag blijft één komma-gescheiden string — dat is wat de adapters al lezen
    (`sources/drive.py:_split_ids`). De komma is daarmee een implementatiedetail dat de UI
    opbouwt en uit elkaar haalt; de auditor typt er nooit een.

    Bewust géén generiek herhaalbaar-veld-mechaniek: alleen Drive heeft dit nodig, en drie
    bronnen die het niet gebruiken mogen niet meebetalen aan die abstractie. Wil Jira het
    later ook, dán generaliseren.
    """


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
                label="Gekoppelde Drive-locaties",
                hint=(
                    "Een Shared Drive of een map. Plak de URL uit de adresbalk, of het ID. "
                    "Je kunt er meerdere koppelen; dubbele bestanden worden overgeslagen."
                ),
                lijst=True,
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
        naam="nextcloud",
        label="Nextcloud",
        uitleg="Documenten uit een Nextcloud- of andere WebDAV-server.",
        velden=[
            Veld(
                naam="NEXTCLOUD_BASE_URL",
                label="Serveradres",
                hint="https://cloud.organisatie.nl — zonder /remote.php erachter.",
            ),
            Veld(
                naam="NEXTCLOUD_USER",
                label="Gebruikersnaam",
                hint=(
                    "Bij voorkeur een functioneel account: dan blijft de koppeling werken "
                    "als iemand de organisatie verlaat."
                ),
            ),
            Veld(
                naam="NEXTCLOUD_APP_PASSWORD",
                label="App-wachtwoord",
                geheim=True,
                hint=(
                    "Een app-specifiek wachtwoord uit Instellingen → Beveiliging, geen "
                    "gebruikerswachtwoord: apart intrekbaar en zonder toegang tot de "
                    "webinterface."
                ),
            ),
            Veld(
                naam="NEXTCLOUD_PATHS",
                label="Mappen",
                verplicht=False,
                hint="Leeg = de hele gebruikersmap. Meerdere mappen staan als losse rijen.",
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
        # "Classificatie en memo-tekst" stond hier tot 2026-08-20 en was niet waar: de
        # modelkeuze raakt alleen de classificatie. Memo-tekst, thema-bepaling en
        # rapportgeneratie draaien altijd op `modellen.STANDAARD`.
        uitleg="Classificatie van bevindingen.",
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
                hint=(
                    "Geldt voor de classificatie van bevindingen. Memo-tekst en "
                    "rapportgeneratie draaien altijd op Haiku. Haiku is het snelst en "
                    "goedkoopst; grotere modellen kosten meer per run."
                ),
            ),
        ],
    ),
    BronDefinitie(
        naam="repo",
        label="Code-repositories",
        uitleg=(
            "Repositories op GitHub of Codeberg. Voor ISO 27001 is dit de plek waar §8.4, "
            "§8.9, §8.25, §8.28, §8.31 en §8.32 aantoonbaar zijn: vier-ogen is geen belofte "
            "in een handboek maar een instelling op een branch."
        ),
        velden=[
            Veld(
                naam="AUDIT_REPOS",
                label="Repositories",
                lijst=True,
                hint=(
                    "Eén per regel, als forge:eigenaar/naam — bijvoorbeeld "
                    "github:ConductionNL/iso-audit of codeberg:conduction/conduction-website. "
                    "De forge staat er bewust bij: die wordt nooit uit de naam geraden."
                ),
            ),
            Veld(
                naam="GITHUB_TOKEN",
                label="GitHub-token",
                geheim=True,
                verplicht=False,
                hint=(
                    "Alleen leesrechten. Een fijnmazig token met Contents: read, Metadata: "
                    "read, Pull requests: read en Administration: read — dat laatste alleen "
                    "om te kunnen zien of een branch beschermd is."
                ),
            ),
            Veld(
                naam="GITHUB_APP_ID",
                label="GitHub-App id",
                verplicht=False,
                hint=(
                    "Vul dit in plaats van een persoonlijk token, als de organisatie een App "
                    "heeft. Een App is eigendom van de organisatie en blijft werken als iemand "
                    "vertrekt; een persoonlijk token niet."
                ),
            ),
            Veld(
                naam="GITHUB_APP_INSTALLATION_ID",
                label="GitHub-App installatie-id",
                verplicht=False,
                hint="Het id van de installatie op de organisatie, niet dat van de App zelf.",
            ),
            Veld(
                naam="GITHUB_APP_PRIVATE_KEY",
                label="GitHub-App private key",
                geheim=True,
                verplicht=False,
                hint=(
                    "Het PEM-blok dat GitHub eenmalig laat downloaden. Heeft voorrang op het "
                    "persoonlijke token."
                ),
            ),
            Veld(
                naam="CODEBERG_TOKEN",
                label="Codeberg-token",
                geheim=True,
                verplicht=False,
                hint=(
                    "Alleen leesrechten. Zonder token blijft de branch-bescherming op "
                    "'niet vast te stellen' staan — dat is iets anders dan 'niet ingesteld'."
                ),
            ),
            Veld(
                naam="REPO_MAX_PR",
                label="Aantal wijzigingen om te bekijken",
                verplicht=False,
                hint=(
                    "Over hoeveel recent samengevoegde wijzigingen het aandeel zonder review "
                    "wordt geteld. Standaard 20; elke wijziging kost een extra aanroep."
                ),
            ),
        ],
    ),
    BronDefinitie(
        naam="website",
        label="Website",
        uitleg=(
            "Gepubliceerde pagina's. Wat een organisatie publiek belooft — een "
            "privacyverklaring, een claim over certificering — is een verplichting die "
            "tegen de interne praktijk hoort (§5.31, §5.34, en 9001 §8.2)."
        ),
        velden=[
            Veld(
                naam="WEBSITE_URLS",
                label="Websites",
                lijst=True,
                hint=(
                    "Eén adres per regel, bijvoorbeeld https://www.conduction.nl. De "
                    "sitemap van de site bepaalt welke pagina's gelezen worden; er worden "
                    "nooit links gevolgd."
                ),
            ),
            Veld(
                naam="WEBSITE_MAX_PAGINAS",
                label="Maximum aantal pagina's",
                verplicht=False,
                hint=(
                    "Standaard 200. Wat er boven valt wordt niet gelezen en staat als "
                    "overgeslagen in de dekking — nooit stil afgekapt."
                ),
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
