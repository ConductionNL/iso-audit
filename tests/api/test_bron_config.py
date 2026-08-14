"""Tests voor bron-configuratie via de UI (taak 3.6-3.9 van change portal-dashboard).

Het punt van deze laag: een auditor koppelt een bron zonder cluster, Secret of
beheerder. De controle is registratie — elke wijziging staat append-only met identiteit
— niet dat configureren moeilijk is.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from iso_audit.api import bron_catalogus as cat
from iso_audit.api.bron_config import BronConfig, ConfigError


@pytest.fixture(autouse=True)
def _schone_omgeving(monkeypatch: pytest.MonkeyPatch) -> None:
    for naam in (
        "JIRA_BASE_URL",
        "JIRA_USER_EMAIL",
        "JIRA_API_TOKEN",
        "JIRA_PROJECTS",
        "MIRO_API_TOKEN",
        "AUDIT_SOURCE_FOLDER_ID",
    ):
        monkeypatch.delenv(naam, raising=False)
    monkeypatch.delenv(cat.CATALOGUS_ENV, raising=False)


# --- catalogus ------------------------------------------------------------


def test_standaardcatalogus_dekt_de_bronnen() -> None:
    namen = {b.naam for b in cat.catalogus()}
    assert {"drive", "planning", "jira", "miro"} <= namen


def test_yaml_overrulet_de_standaard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Een beheerder past labels aan zonder codewijziging."""
    pad = tmp_path / "bronnen.yaml"
    pad.write_text(
        "bronnen:\n- naam: jira\n  label: Onze Jira\n  velden:\n"
        "  - naam: JIRA_BASE_URL\n    label: Adres\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(cat.CATALOGUS_ENV, str(pad))
    assert [b.naam for b in cat.catalogus()] == ["jira"]
    assert cat.definitie("jira").label == "Onze Jira"  # type: ignore[union-attr]


def test_kapotte_yaml_valt_terug_op_de_standaard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Configuratie kunnen zien weegt zwaarder dan een strikte lezing van een bestand."""
    pad = tmp_path / "stuk.yaml"
    pad.write_text("bronnen: [dit: is: geen: geldige: yaml", encoding="utf-8")
    monkeypatch.setenv(cat.CATALOGUS_ENV, str(pad))
    assert {b.naam for b in cat.catalogus()} >= {"jira", "miro"}


def test_gegenereerde_yaml_is_weer_inleesbaar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wat het script schrijft, moet het portaal kunnen lezen."""
    pad = tmp_path / "rond.yaml"
    pad.write_text(cat.naar_yaml(), encoding="utf-8")
    monkeypatch.setenv(cat.CATALOGUS_ENV, str(pad))
    assert [b.naam for b in cat.catalogus()] == [b.naam for b in cat.STANDAARD]


# --- waarden opslaan ------------------------------------------------------


def test_zetten_koppelt_de_bron_via_de_omgeving(tmp_path: Path) -> None:
    """De adapters lezen env-vars; daarom landen de waarden daar."""
    c = BronConfig(tmp_path)
    c.zet("miro", {"MIRO_API_TOKEN": "geheim123"}, door="a@conduction.nl")
    assert os.environ["MIRO_API_TOKEN"] == "geheim123"

    # Overleeft een herstart: nieuw object, zelfde directory.
    os.environ.pop("MIRO_API_TOKEN")
    BronConfig(tmp_path).naar_omgeving()
    assert os.environ["MIRO_API_TOKEN"] == "geheim123"


def test_geheim_veld_komt_er_nooit_uit(tmp_path: Path) -> None:
    c = BronConfig(tmp_path)
    c.zet("miro", {"MIRO_API_TOKEN": "geheim123"}, door="a@c.nl")
    (veld,) = c.status("miro")["velden"]  # type: ignore[index]
    assert veld["ingesteld"] is True
    assert veld["waarde"] == ""
    assert "geheim123" not in json.dumps(c.status("miro"))


def test_niet_geheim_veld_is_wel_leesbaar(tmp_path: Path) -> None:
    """Anders kan een auditor niet zien welke map hij had ingesteld."""
    c = BronConfig(tmp_path)
    c.zet("drive", {"AUDIT_SOURCE_FOLDER_ID": "map-abc"}, door="a@c.nl")
    velden = {v["naam"]: v for v in c.status("drive")["velden"]}  # type: ignore[index]
    assert velden["AUDIT_SOURCE_FOLDER_ID"]["waarde"] == "map-abc"


def test_leeg_zetten_wist_de_waarde(tmp_path: Path) -> None:
    """Een verkeerd gekoppelde bron moet je kunnen loskoppelen."""
    c = BronConfig(tmp_path)
    c.zet("drive", {"AUDIT_SOURCE_FOLDER_ID": "map-abc"}, door="a@c.nl")
    c.zet("drive", {"AUDIT_SOURCE_FOLDER_ID": ""}, door="a@c.nl")
    velden = {v["naam"]: v for v in c.status("drive")["velden"]}  # type: ignore[index]
    assert velden["AUDIT_SOURCE_FOLDER_ID"]["ingesteld"] is False
    assert "AUDIT_SOURCE_FOLDER_ID" not in os.environ


def test_omgeving_wint_van_opgeslagen_waarde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wat een beheerder expliciet zette, weegt zwaarder dan een oude UI-invoer."""
    c = BronConfig(tmp_path)
    c.zet("miro", {"MIRO_API_TOKEN": "uit-de-ui"}, door="a@c.nl")
    monkeypatch.setenv("MIRO_API_TOKEN", "uit-het-manifest")
    BronConfig(tmp_path).naar_omgeving()
    assert os.environ["MIRO_API_TOKEN"] == "uit-het-manifest"


def test_onbekende_bron_en_veld_worden_geweigerd(tmp_path: Path) -> None:
    c = BronConfig(tmp_path)
    with pytest.raises(ConfigError, match="Onbekende bron"):
        c.zet("sharepoint", {"X": "y"}, door="a@c.nl")
    with pytest.raises(ConfigError, match="Onbekende velden"):
        c.zet("miro", {"MIRO_TOKEN_TYPO": "y"}, door="a@c.nl")


def test_bestand_is_alleen_voor_de_eigenaar_leesbaar(tmp_path: Path) -> None:
    """Er kunnen tokens in staan; dit is geen secret-manager maar wel 0600."""
    c = BronConfig(tmp_path)
    c.zet("miro", {"MIRO_API_TOKEN": "geheim"}, door="a@c.nl")
    assert oct(c.pad.stat().st_mode)[-3:] == "600"


# --- registratie ----------------------------------------------------------


def test_wijziging_wordt_append_only_vastgelegd_zonder_waarden(tmp_path: Path) -> None:
    """Registratie is de controle. Veldnamen wel, waarden nooit."""
    c = BronConfig(tmp_path)
    c.zet("jira", {"JIRA_BASE_URL": "https://x.atlassian.net"}, door="eerste@c.nl")
    eerste = c.wijzigingen()
    c.zet("jira", {"JIRA_API_TOKEN": "topsecret"}, door="tweede@c.nl")
    alles = c.wijzigingen()

    assert len(alles) == 2
    assert alles[0] == eerste[0], "oudere regel is gemuteerd"
    assert alles[1]["door"] == "tweede@c.nl"
    assert alles[1]["geheim"] == ["JIRA_API_TOKEN"]
    assert "topsecret" not in json.dumps(alles)


def test_ongewijzigd_zetten_logt_niets(tmp_path: Path) -> None:
    c = BronConfig(tmp_path)
    c.zet("miro", {"MIRO_API_TOKEN": "zelfde"}, door="a@c.nl")
    c.zet("miro", {"MIRO_API_TOKEN": "zelfde"}, door="a@c.nl")
    assert len(c.wijzigingen()) == 1


# --- via de API -----------------------------------------------------------


def _portaal(tmp_path: Path):  # type: ignore[no-untyped-def]
    from fastapi.testclient import TestClient

    from iso_audit.api.app import create_app
    from iso_audit.api.registry import AuditRegistry

    from .conftest import AUDITOR, EXAMPLES, NORMS

    registry = AuditRegistry(tmp_path / "audits")
    registry.root.mkdir(parents=True)
    app = create_app(registry, profile=str(EXAMPLES / "conduction.profile.yaml"), norms_dir=NORMS)
    return TestClient(app, headers={"X-Forwarded-Email": AUDITOR}), registry


def test_api_koppelt_een_bron_zonder_cluster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De hele reden van deze laag: geen Secret, geen manifest, geen beheerder."""
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    client, _ = _portaal(tmp_path)

    bronnen = client.get("/config/bronnen").json()
    jira = next(b for b in bronnen if b["naam"] == "jira")
    assert jira["velden"][0]["label"] == "Jira-adres"

    r = client.post(
        "/config/bronnen/jira",
        json={"velden": {"JIRA_BASE_URL": "https://x.atlassian.net", "JIRA_API_TOKEN": "t0k3n"}},
    )
    assert r.status_code == 200
    velden = {v["naam"]: v for v in r.json()["velden"]}
    assert velden["JIRA_BASE_URL"]["waarde"] == "https://x.atlassian.net"
    assert velden["JIRA_API_TOKEN"]["ingesteld"] is True
    assert velden["JIRA_API_TOKEN"]["waarde"] == ""
    assert "t0k3n" not in r.text


def test_api_weigert_onbekend_veld(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    client, _ = _portaal(tmp_path)
    r = client.post("/config/bronnen/miro", json={"velden": {"MIRO_TYPO": "x"}})
    assert r.status_code == 400
    assert "Onbekende velden" in r.json()["detail"]


def test_api_toont_wijzigingsspoor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    client, _ = _portaal(tmp_path)
    client.post("/config/bronnen/miro", json={"velden": {"MIRO_API_TOKEN": "x"}})
    (regel,) = client.get("/config/wijzigingen").json()
    from .conftest import AUDITOR

    assert regel["door"] == AUDITOR
    assert regel["bron"] == "miro"


def test_geen_configwijziging_tijdens_een_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Een Source leest zijn config bij start; halverwege wisselen geeft twee scopes."""
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    d = registry.pad(aid)
    # De sim-run loopt één tik per bevinding; met een lege werkset is hij direct klaar
    # en zou de guard nooit getest worden.
    (d / "findings.json").write_text(
        json.dumps(
            [
                {
                    "id": f"f{i}",
                    "severity": "NC",
                    "standard": "iso-9001-2015",
                    "clause": "10.2",
                    "title": f"T{i}",
                    "description": "x",
                }
                for i in range(3)
            ]
        ),
        encoding="utf-8",
    )
    (d / "memo-input.yaml").write_text(
        (Path("examples/auditmemo/memo-input.yaml")).read_text(encoding="utf-8"), encoding="utf-8"
    )
    # Sim-run met een trage pace, zodat hij nog loopt tijdens de configpoging.
    client.post(f"/audits/{aid}/run/start", json={"mode": "sim", "pace": 5.0})

    r = client.post("/config/bronnen/miro", json={"velden": {"MIRO_API_TOKEN": "x"}})
    assert r.status_code == 409
    assert aid in r.json()["detail"]
