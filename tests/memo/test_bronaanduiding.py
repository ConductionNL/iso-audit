"""Elke geraadpleegde bron krijgt de aanduiding waarmee je hem terugvindt.

"Geraadpleegde bronnen: Google Drive, Jira, Planning, Nextcloud" is decoratie. Een externe
auditor die de scope van deze audit wil natrekken, vraagt wélke Drive-map en wélk Jira-project —
en dat staat gewoon in de configuratie waarmee de run draaide.

De aanduiding wordt afgeleid uit de instellingen op het moment van de run, en niet later
opnieuw. Anders zegt de memo wat er *nu* is gekoppeld in plaats van waar de audit op rustte.
"""

from __future__ import annotations

from iso_audit.memo.bronaanduiding import aanduiding_voor


def test_drive_krijgt_een_klikbare_mapverwijzing() -> None:
    a = aanduiding_voor("drive", {"drive.folder_id": "1AbCdEf"})
    assert a.naam == "Google Drive"
    assert a.identificatie == "1AbCdEf"
    assert a.url == "https://drive.google.com/drive/folders/1AbCdEf"


def test_planning_wijst_naar_het_werkblad() -> None:
    a = aanduiding_voor("planning", {"planning.sheets_id": "9Xyz"})
    assert a.url == "https://docs.google.com/spreadsheets/d/9Xyz"


def test_jira_noemt_de_projecten_bij_de_instantie() -> None:
    a = aanduiding_voor(
        "jira", {"jira.base_url": "https://conduction.atlassian.net", "jira.projects": "ISO,SEC"}
    )
    assert a.url == "https://conduction.atlassian.net"
    assert "ISO" in a.identificatie and "SEC" in a.identificatie


def test_nextcloud_noemt_de_paden() -> None:
    a = aanduiding_voor(
        "nextcloud", {"nextcloud.base_url": "https://cloud.example", "nextcloud.paths": "/ISO"}
    )
    assert a.url == "https://cloud.example"
    assert "/ISO" in a.identificatie


def test_een_bron_zonder_configuratie_krijgt_geen_verzonnen_url() -> None:
    """Liever geen aanduiding dan een die nergens heen wijst."""
    a = aanduiding_voor("drive", {})
    assert a.naam == "Google Drive"
    assert a.identificatie == ""
    assert a.url is None


def test_een_onbekende_bron_houdt_zijn_eigen_naam() -> None:
    a = aanduiding_voor("mcp:asana", {})
    assert a.naam == "mcp:asana"
    assert a.url is None


def test_miro_heeft_geen_identificatie_en_verzint_er_geen() -> None:
    """Miro is gekoppeld op een token, niet op een bord-id; dan valt er niets te noemen."""
    a = aanduiding_voor("miro", {"miro.api_token": "geheim"})
    assert a.naam == "Miro"
    assert a.identificatie == ""
    assert a.url is None


def test_een_geheim_lekt_nooit_in_de_aanduiding() -> None:
    """De memo wordt gedeeld; een token dat erin belandt is een incident."""
    for bron, config in (
        ("jira", {"jira.base_url": "https://x", "jira.api_token": "GEHEIM"}),
        ("nextcloud", {"nextcloud.base_url": "https://y", "nextcloud.app_password": "GEHEIM"}),
        ("miro", {"miro.api_token": "GEHEIM"}),
    ):
        a = aanduiding_voor(bron, config)
        assert "GEHEIM" not in f"{a.naam}{a.identificatie}{a.url}"
