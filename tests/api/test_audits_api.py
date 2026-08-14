"""Tests voor de audit-gescopede API (taak 2 van change portal-dashboard).

De kern die hier bewaakt wordt: een beslissing landt in de audit die het verzoek
noemt, en in geen andere. In een append-only trail is een beslissing in de verkeerde
audit niet terug te draaien, dus dat is de test die moet blijven staan.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iso_audit.api import overzicht as ov
from iso_audit.api.app import create_app
from iso_audit.api.auth_gate import REQUIRE_AUTH_ENV
from iso_audit.api.registry import AuditRegistry

from .conftest import AUDITOR, EXAMPLES, NORMS

_FINDINGS = [
    {
        "id": "f1",
        "severity": "NC",
        "standard": "iso-9001-2015",
        "clause": "10.2",
        "title": "Correctieve maatregelen",
        "description": "Effectiviteit niet geëvalueerd.",
        "triage_status": "open",
    }
]


@pytest.fixture(autouse=True)
def _gate_uit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deze tests gaan over routing, niet over de gate; die is elders gedekt."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)


def _portaal(tmp_path: Path) -> tuple[TestClient, AuditRegistry]:
    registry = AuditRegistry(tmp_path / "audits")
    registry.root.mkdir(parents=True)
    app = create_app(registry, profile=str(EXAMPLES / "conduction.profile.yaml"), norms_dir=NORMS)
    return TestClient(app, headers={"X-Forwarded-Email": AUDITOR}), registry


def _vul(registry: AuditRegistry, aid: str, findings: list[dict[str, object]]) -> Path:
    d = registry.pad(aid)
    (d / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    (d / "memo-input.yaml").write_text(
        (EXAMPLES / "memo-input.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return d


# --- audits aanmaken en opsommen -----------------------------------------


def test_audit_aanmaken_is_een_auditorhandeling(tmp_path: Path) -> None:
    """Geen beheeractie: norm + periode volstaat, en de audit bestaat direct."""
    client, _ = _portaal(tmp_path)
    r = client.post("/audits", json={"norm": "9001", "periode": "2026-Q3"})
    assert r.status_code == 201
    assert r.json()["id"] == "9001-2026-Q3"
    assert r.json()["status"] == ov.STATUS_NIEUW

    lijst = client.get("/audits").json()
    assert [a["id"] for a in lijst] == ["9001-2026-Q3"]


def test_ongeldige_periode_geeft_400(tmp_path: Path) -> None:
    client, _ = _portaal(tmp_path)
    r = client.post("/audits", json={"norm": "9001", "periode": "najaar"})
    assert r.status_code == 400
    assert "periode" in r.json()["detail"]


def test_dubbele_audit_geeft_400(tmp_path: Path) -> None:
    client, _ = _portaal(tmp_path)
    client.post("/audits", json={"norm": "9001", "periode": "2026-Q3"})
    r = client.post("/audits", json={"norm": "9001", "periode": "2026-Q3"})
    assert r.status_code == 400
    assert "bestaat al" in r.json()["detail"]


def test_lege_audit_staat_in_het_overzicht(tmp_path: Path) -> None:
    """Een audit zonder run is een geldige toestand en moet zichtbaar zijn."""
    client, _ = _portaal(tmp_path)
    client.post("/audits", json={"norm": "27001", "periode": "2026-H2"})
    (regel,) = client.get("/audits").json()
    assert regel["status"] == ov.STATUS_NIEUW
    assert regel["runs"] == 0


# --- isolatie tussen audits ----------------------------------------------


def test_beslissing_landt_in_de_genoemde_audit(tmp_path: Path) -> None:
    """De belangrijkste test van deze change: geen kruisbesmetting."""
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"norm": "9001", "periode": "2026-Q3"})
    client.post("/audits", json={"norm": "27001", "periode": "2026-Q3"})
    a, b = "9001-2026-Q3", "27001-2026-Q3"
    _vul(registry, a, _FINDINGS)
    _vul(registry, b, _FINDINGS)

    r = client.post(
        f"/audits/{a}/findings/f1",
        json={"triage_status": "valide", "reason": "bewijs gezien"},
    )
    assert r.status_code == 200

    assert len(client.get(f"/audits/{a}/trail").json()) == 1
    assert client.get(f"/audits/{b}/trail").json() == [], "beslissing lekte naar de andere audit"
    assert client.get(f"/audits/{b}/findings").json()[0]["triage_status"] == "open"


def test_onbekende_audit_geeft_404_en_maakt_niets_aan(tmp_path: Path) -> None:
    client, registry = _portaal(tmp_path)
    r = client.get("/audits/9001-2026-Q9/findings")
    assert r.status_code == 404
    assert "bestaat niet" in r.json()["detail"]
    assert list(registry.root.iterdir()) == []


def test_padontsnapping_wordt_geweigerd(tmp_path: Path) -> None:
    client, _ = _portaal(tmp_path)
    assert client.get("/audits/..%2F..%2Fetc/findings").status_code in (400, 404)


# --- runs ----------------------------------------------------------------


def test_run_wordt_geregistreerd_met_identiteit(tmp_path: Path) -> None:
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"norm": "9001", "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)

    r = client.post(
        f"/audits/{aid}/run/start", json={"mode": "sim", "norm": "9001", "sources": ["drive"]}
    )
    assert r.status_code == 200

    (rec,) = client.get(f"/audits/{aid}/runs").json()
    assert rec["door"] == AUDITOR
    assert rec["bronnen"] == ["drive"]
    assert rec["status"] == "klaar"


def test_bronnen_uit_runs_landen_in_het_overzicht(tmp_path: Path) -> None:
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"norm": "9001", "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)
    client.post(f"/audits/{aid}/run/start", json={"mode": "sim", "sources": ["drive"]})

    (regel,) = client.get("/audits").json()
    assert regel["bronnen"] == ["drive"]
    assert regel["status"] == ov.STATUS_LOOPT


# --- audit-onafhankelijke routes -----------------------------------------


def test_healthz_en_config_zijn_niet_audit_gescoped(tmp_path: Path) -> None:
    """Deze twee horen buiten elke audit; anders zijn ze onbruikbaar als probe/overzicht."""
    client, _ = _portaal(tmp_path)
    assert client.get("/healthz").json() == {"status": "ok"}
    gezondheid = client.get("/config/health").json()
    assert set(gezondheid) >= {"drive", "jira", "planning"}
    assert "sources" in client.get("/config/options").json()


def test_detail_meldt_andere_actieve_auditor(tmp_path: Path) -> None:
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"norm": "9001", "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)
    registry.markeer_actief(aid, "iemand.anders@conduction.nl")

    detail = client.get(f"/audits/{aid}").json()
    assert detail["andere_actief"]["identiteit"] == "iemand.anders@conduction.nl"
    assert detail["audit"]["id"] == aid


def test_tweede_run_via_de_route_behoudt_triage(tmp_path: Path) -> None:
    """Regressie-vangnet voor het gat dat de containertest blootlegde.

    `_run_live_worker` deed `self._save(drafted)` en overschreef daarmee de hele
    werkset. De dedup-module bestond en was getest, maar niets riep hem aan vanuit de
    run — dus de spec-eis "een volgende run gooit geen triage weg" hield op
    moduleniveau en niet in de praktijk. Deze test loopt door de échte route.
    """
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"norm": "9001", "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    d = _vul(registry, aid, _FINDINGS)

    r = client.post(f"/audits/{aid}/findings/f1", json={"triage_status": "valide", "reason": "ok"})
    assert r.status_code == 200

    # Een run met dezelfde kandidaat erin mag hem niet opnieuw introduceren.
    from iso_audit.api import runs as runs_mod

    toegevoegd, overgeslagen = runs_mod.voeg_toe(d, _FINDINGS)
    assert (toegevoegd, overgeslagen) == (0, 1)

    na = client.get(f"/audits/{aid}/findings").json()
    assert len(na) == 1
    assert na[0]["triage_status"] == "valide", "triage is weggegooid door de tweede run"
