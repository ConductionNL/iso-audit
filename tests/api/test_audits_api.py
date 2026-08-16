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
    r = client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    assert r.status_code == 201
    assert r.json()["id"] == "9001-2026-Q3"
    assert r.json()["status"] == ov.STATUS_NIEUW

    lijst = client.get("/audits").json()
    assert [a["id"] for a in lijst] == ["9001-2026-Q3"]


def test_ongeldige_periode_geeft_400(tmp_path: Path) -> None:
    client, _ = _portaal(tmp_path)
    r = client.post("/audits", json={"normen": ["9001"], "periode": "najaar"})
    assert r.status_code == 400
    assert "periode" in r.json()["detail"]


def test_dubbele_audit_geeft_400(tmp_path: Path) -> None:
    client, _ = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    r = client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    assert r.status_code == 400
    assert "bestaat al" in r.json()["detail"]


def test_lege_audit_staat_in_het_overzicht(tmp_path: Path) -> None:
    """Een audit zonder run is een geldige toestand en moet zichtbaar zijn."""
    client, _ = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["27001"], "periode": "2026-H2"})
    (regel,) = client.get("/audits").json()
    assert regel["status"] == ov.STATUS_NIEUW
    assert regel["runs"] == 0


# --- isolatie tussen audits ----------------------------------------------


def test_beslissing_landt_in_de_genoemde_audit(tmp_path: Path) -> None:
    """De belangrijkste test van deze change: geen kruisbesmetting."""
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    client.post("/audits", json={"normen": ["27001"], "periode": "2026-Q3"})
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
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)

    r = client.post(
        f"/audits/{aid}/run/start",
        json={"mode": "sim", "norm": "9001", "sources": ["drive"], "pace": 0},
    )
    assert r.status_code == 200

    (rec,) = client.get(f"/audits/{aid}/runs").json()
    assert rec["door"] == AUDITOR
    assert rec["bronnen"] == ["drive"]
    assert rec["status"] == "klaar"


def test_run_zonder_bron_wordt_geweigerd(tmp_path: Path) -> None:
    """Dit gaf `200 {"status": "running"}` terwijl vier gestapelde `or ["drive"]`-
    terugvallen er stil een drive-run van maakten. De auditor zag een run die niets deed
    en geen uitleg."""
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)

    r = client.post(f"/audits/{aid}/run/start", json={"mode": "sim", "sources": []})

    assert r.status_code == 400
    assert "minstens één bron" in r.json()["detail"]

    # De poging staat wél in de historie: "iemand probeerde te draaien zonder bron" is
    # precies de diagnose die je later mist.
    (rec,) = client.get(f"/audits/{aid}/runs").json()
    assert rec["status"] == "fout"
    assert "minstens één bron" in rec["fout"]


def test_onbekende_bron_wordt_geweigerd_met_de_beschikbare_lijst(tmp_path: Path) -> None:
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)

    r = client.post(f"/audits/{aid}/run/start", json={"mode": "sim", "sources": ["sharepoint"]})

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "sharepoint" in detail
    assert "drive" in detail, "noem wat er wél kan"


def test_run_record_beweert_niet_klaar_voordat_de_run_klaar_is(tmp_path: Path) -> None:
    """Het record werd geschreven met `laatste_merge` = (0, 0) direct na het starten van de
    thread, met `status: "klaar"`. Append-only betekent dat je dat niet kunt rechtzetten."""
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)

    # pace > 0 → de sim-run draait in een thread en is bij het lezen nog niet klaar.
    client.post(f"/audits/{aid}/run/start", json={"mode": "sim", "sources": ["drive"], "pace": 5.0})

    (rec,) = client.get(f"/audits/{aid}/runs").json()
    assert rec["status"] == "loopt"
    assert "toegevoegd" not in rec or rec["toegevoegd"] == 0

    # Het ruwe spoor heeft één record; er is niets overschreven.
    regels = (registry.pad(aid) / "runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(regels) == 1


def test_bronnen_uit_runs_landen_in_het_overzicht(tmp_path: Path) -> None:
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
    aid = "9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)
    client.post(f"/audits/{aid}/run/start", json={"mode": "sim", "sources": ["drive"], "pace": 0})

    (regel,) = client.get("/audits").json()
    assert regel["bronnen"] == ["drive"]
    assert regel["status"] == ov.STATUS_LOOPT


# --- audit-onafhankelijke routes -----------------------------------------


def test_healthz_en_config_zijn_niet_audit_gescoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deze twee horen buiten elke audit; anders zijn ze onbruikbaar als probe/overzicht.

    De koppelstatus wordt gestubd. Deze test gaat over routing, niet over connectiviteit —
    en zonder stub doen Drive en Planning echte Google-calls met de credentials die uit een
    lokaal omgevingsbestand komen. Dat duurde 75 seconden en las de live auditmap uit; een
    testsuite hoort geen productiedata aan te raken.
    """
    monkeypatch.setattr(
        "iso_audit.api.session._check_source",
        lambda naam: {"connected": False, "status": "fail", "naam": naam, "soort": "netwerk"},
    )
    client, _ = _portaal(tmp_path)
    assert client.get("/healthz").json() == {"status": "ok"}
    gezondheid = client.get("/config/health").json()
    assert set(gezondheid) >= {"drive", "jira", "planning"}
    assert "sources" in client.get("/config/options").json()


def test_detail_meldt_andere_actieve_auditor(tmp_path: Path) -> None:
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
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
    client.post("/audits", json={"normen": ["9001"], "periode": "2026-Q3"})
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


def test_audit_over_beide_normen_via_de_api(tmp_path: Path) -> None:
    client, _ = _portaal(tmp_path)
    r = client.post("/audits", json={"normen": ["9001", "27001"], "periode": "2026-Q3"})
    assert r.status_code == 201
    assert r.json()["id"] == "27001_9001-2026-Q3"
    assert r.json()["normen"] == ["27001", "9001"]


def test_norm_buiten_de_pipeline_geeft_400(tmp_path: Path) -> None:
    client, registry = _portaal(tmp_path)
    r = client.post("/audits", json={"normen": ["iso-14001-2015"], "periode": "2026-Q3"})
    assert r.status_code == 400
    assert "nog niet draaien" in r.json()["detail"]
    assert list(registry.root.iterdir()) == []


def test_run_neemt_de_norm_uit_de_audit(tmp_path: Path) -> None:
    """De run mag geen andere norm kunnen kiezen dan de audit — anders liegt de memo."""
    client, registry = _portaal(tmp_path)
    client.post("/audits", json={"normen": ["9001", "27001"], "periode": "2026-Q3"})
    aid = "27001_9001-2026-Q3"
    _vul(registry, aid, _FINDINGS)

    assert (
        client.post(
            f"/audits/{aid}/run/start", json={"mode": "sim", "sources": ["drive"]}
        ).status_code
        == 200
    )
    (rec,) = client.get(f"/audits/{aid}/runs").json()
    assert rec["norm"] == "beide"


def test_me_geeft_identiteit_en_logout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zonder /me heeft de UI geen "ingelogd als" en geen uitlogknop."""
    monkeypatch.setenv("ISO_AUDIT_LOGOUT_URL", "https://iam.example/logout")
    client, _ = _portaal(tmp_path)
    d = client.get("/me").json()
    assert d["identiteit"] == AUDITOR
    assert d["logout_url"] == "https://iam.example/logout"


def test_me_zonder_logout_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Niet gezet → null, en de UI wist dan alleen de proxy-sessie."""
    monkeypatch.delenv("ISO_AUDIT_LOGOUT_URL", raising=False)
    client, _ = _portaal(tmp_path)
    assert client.get("/me").json()["logout_url"] is None
