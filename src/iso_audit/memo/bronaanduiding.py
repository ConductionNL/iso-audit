"""Per bron: de aanduiding waarmee je hem terugvindt.

Hoort bij `memo` en niet bij `sources`: dit is geen bron-adapter maar de vertaling van
bronconfiguratie naar iets dat in een memo leesbaar is.

"Geraadpleegde bronnen: Google Drive, Jira, Planning, Nextcloud" is decoratie. Een externe
auditor die de scope van een audit natrekt, vraagt wélke Drive-map en wélk Jira-project. Die
gegevens staan in de instellingen waarmee de run draaide; deze module maakt er een leesbare,
klikbare aanduiding van.

Twee regels die niet onderhandelbaar zijn:

- **Nooit een verzonnen verwijzing.** Ontbreekt de configuratie, dan is er geen identificatie en
  geen URL. Een link die nergens heen wijst is erger dan geen link: hij suggereert dat er
  nagekeken is.
- **Nooit een geheim.** De memo wordt gedeeld. Tokens en wachtwoorden komen hier niet voorbij,
  ook niet gemaskeerd — er is geen reden ze aan te raken.
"""

from __future__ import annotations

from collections.abc import Mapping

from iso_audit.memo.models import Bronaanduiding

BRONNAAM = {
    "drive": "Google Drive",
    "jira": "Jira",
    "miro": "Miro",
    "planning": "Planning",
    "nextcloud": "Nextcloud",
}
"""Mens-leesbare naam per adapter. Onbekende bron houdt zijn eigen naam."""


def aanduiding_voor(bron: str, config: Mapping[str, str]) -> Bronaanduiding:
    """Bouw de aanduiding voor één bron uit de opgeloste instellingen.

    `config` is een platte afbeelding van instelling-sleutel naar waarde, zoals
    `Settings` die oplevert. Bewust geen `Settings` als parameter: dan is dit een pure functie
    die je kunt testen zonder omgeving.
    """
    naam = BRONNAAM.get(bron, bron)

    if bron == "drive":
        folder = config.get("drive.folder_id", "")
        if folder:
            return Bronaanduiding(
                naam=naam,
                identificatie=folder,
                url=f"https://drive.google.com/drive/folders/{folder}",
            )
    elif bron == "planning":
        sheet = config.get("planning.sheets_id", "")
        if sheet:
            return Bronaanduiding(
                naam=naam,
                identificatie=sheet,
                url=f"https://docs.google.com/spreadsheets/d/{sheet}",
            )
    elif bron == "jira":
        basis = config.get("jira.base_url", "")
        projecten = config.get("jira.projects", "")
        if basis:
            return Bronaanduiding(
                naam=naam,
                identificatie=f"projecten {projecten}" if projecten else basis,
                url=basis,
            )
    elif bron == "nextcloud":
        basis = config.get("nextcloud.base_url", "")
        paden = config.get("nextcloud.paths", "")
        if basis:
            return Bronaanduiding(
                naam=naam,
                identificatie=paden or basis,
                url=basis,
            )

    # Miro valt hier ook onder: die is gekoppeld op een token en niet op een bord-id, dus er
    # valt niets te noemen. Een naam zonder aanduiding is een eerlijk antwoord.
    return Bronaanduiding(naam=naam)
