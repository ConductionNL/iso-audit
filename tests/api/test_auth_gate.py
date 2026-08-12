"""Tests voor de fail-closed identity-gate (`iso_audit.api.auth_gate`).

Dit is de lokale tegenhanger van de smoke-test uit `docs/how-to/verify-portal-auth.md`: fail-closed is
zonder cluster en zonder proxy aan te tonen, en dat is precies het auditbewijs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iso_audit.api.app import create_app
from iso_audit.api.auth_gate import (
    DEV_IDENTITEIT,
    EMAIL_HEADER,
    REQUIRE_AUTH_ENV,
    USER_HEADER,
    auth_vereist,
)
from iso_audit.api.session import AuditSession

_EX = Path("examples/auditmemo")
_AUDITOR = "auditor@conduction.nl"
_FINDINGS = [
    {
        "id": "f1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "6.5",
        "title": "Offboarding",
        "description": "Offboarding niet aantoonbaar afgesloten.",
        "triage_status": "open",
    }
]


def _client(tmp_path: Path, **kwargs: object) -> TestClient:
    (tmp_path / "findings.json").write_text(json.dumps(_FINDINGS), encoding="utf-8")
    session = AuditSession(
        tmp_path,
        profile=str(_EX / "conduction.profile.yaml"),
        norms_dir="examples/norms",
        memo_input_path=str(_EX / "memo-input.yaml"),
    )
    return TestClient(create_app(session), **kwargs)  # type: ignore[arg-type]


# --- auth_vereist() ---------------------------------------------------------


def test_auth_vereist_default_aan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zonder REQUIRE_AUTH staat de gate aan — fail closed is de default."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    assert auth_vereist() is True


@pytest.mark.parametrize("waarde", ["false", "FALSE", "0", "no", "off", ""])
def test_auth_vereist_uit_waarden(monkeypatch: pytest.MonkeyPatch, waarde: str) -> None:
    """Alleen expliciete uit-waarden zetten de gate uit."""
    monkeypatch.setenv(REQUIRE_AUTH_ENV, waarde)
    assert auth_vereist() is False


@pytest.mark.parametrize("waarde", ["true", "maybe", "ja", "1", "aan"])
def test_auth_vereist_onbekende_waarde_blijft_aan(
    monkeypatch: pytest.MonkeyPatch, waarde: str
) -> None:
    """Een typfout mag het portaal niet openzetten."""
    monkeypatch.setenv(REQUIRE_AUTH_ENV, waarde)
    assert auth_vereist() is True


# --- de gate op de app -----------------------------------------------------


def test_zonder_header_403(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Request zonder identity-header wordt geweigerd terwijl de gate aan staat."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    r = _client(tmp_path).get("/findings")
    assert r.status_code == 403
    assert EMAIL_HEADER in r.json()["detail"]


def test_met_email_header_200(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Met een geldige identity-header verwerkt de app het request normaal."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    r = _client(tmp_path, headers={EMAIL_HEADER: _AUDITOR}).get("/findings")
    assert r.status_code == 200


def test_user_header_als_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sommige proxy-configuraties zetten alleen X-Forwarded-User."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    r = _client(tmp_path, headers={USER_HEADER: _AUDITOR}).get("/findings")
    assert r.status_code == 200


def test_lege_header_telt_niet_als_identiteit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Een aanwezige maar lege header is geen identiteit."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    r = _client(tmp_path, headers={EMAIL_HEADER: "   "}).get("/findings")
    assert r.status_code == 403


def test_healthz_altijd_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """De probe moet werken zonder sessie, ook met de gate aan."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    r = _client(tmp_path).get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_require_auth_false_laat_door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dev-modus: zonder header toch door, expliciet aangezet."""
    monkeypatch.setenv(REQUIRE_AUTH_ENV, "false")
    r = _client(tmp_path).get("/findings")
    assert r.status_code == 200


def test_index_is_ook_bewaakt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Alleen /healthz staat open — de UI-route niet."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    assert _client(tmp_path).get("/").status_code == 403


# --- sec-bevinding 1: de actor in de append-only trail ----------------------


def _triage(client: TestClient) -> None:
    r = client.post(
        "/findings/f1",
        json={"triage_status": "valide", "reason": "bewijs gezien"},
    )
    assert r.status_code == 200


def test_trail_legt_geverifieerde_identiteit_vast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De trail-regel is toewijsbaar aan de ingelogde auditor."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    client = _client(tmp_path, headers={EMAIL_HEADER: _AUDITOR})
    _triage(client)

    regels = client.get("/trail").json()
    assert regels, "trail is leeg — triage is niet vastgelegd"
    assert all(r["actor"] == _AUDITOR for r in regels)
    assert not any(r["actor"] == "auditor" for r in regels), (
        "placeholder-default staat nog in de trail"
    )


def test_trail_actor_is_nooit_leeg_in_dev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Met de gate uit staat er een onmiskenbare dev-markering, geen leeg veld."""
    monkeypatch.setenv(REQUIRE_AUTH_ENV, "false")
    client = _client(tmp_path)
    _triage(client)

    regels = client.get("/trail").json()
    assert all(r["actor"] == DEV_IDENTITEIT for r in regels)


def test_geen_beslissing_zonder_identiteit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Een geweigerd triage-request legt niets vast."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    client = _client(tmp_path)
    assert client.post("/findings/f1", json={"reason": "x"}).status_code == 403
    assert not (tmp_path / "triage_log.jsonl").exists()
