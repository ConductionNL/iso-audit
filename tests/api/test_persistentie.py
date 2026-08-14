"""Tests voor de persistentie-garantie van de audit-trail (capability portal-deployment).

De append-only trail is auditbewijs, geen cache. In het portaal draait de app in een
pod die verdwijnt; als de trail dat niet overleeft, is de append-only-belofte uit
`CLAUDE.md` leeg. Een pod-restart is hier gemodelleerd als "nieuw proces, nieuwe
`AuditSession`, zelfde directory" — precies wat een herstart met een PVC doet.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iso_audit.api.app import create_app
from iso_audit.api.auth_gate import EMAIL_HEADER, REQUIRE_AUTH_ENV
from iso_audit.api.registry import AuditRegistry
from iso_audit.api.session import AuditSession
from iso_audit.store import DEFAULT_DB_PATH, db_pad

from .conftest import PortaalClient

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
    },
    {
        "id": "f2",
        "severity": "NC",
        "standard": "iso-9001-2015",
        "clause": "10.2",
        "title": "Correctieve maatregelen",
        "description": "Effectiviteit niet geëvalueerd.",
        "triage_status": "open",
    },
]


def _nieuw_proces(audits_root: Path, audit_id: str) -> PortaalClient:
    """Simuleer een pod-restart: nieuwe app en nieuwe registry op dezelfde PVC.

    Bewust een verse `create_app` én een verse `AuditRegistry`: de sessie-cache in
    `Audits` leeft in het proces, dus dit is precies wat een herstart doet — alle
    in-memory state weg, alleen de bestanden over.
    """
    registry = AuditRegistry(audits_root)
    app = create_app(
        registry,
        profile=str(_EX / "conduction.profile.yaml"),
        norms_dir="examples/norms",
    )
    return PortaalClient(
        TestClient(app, headers={EMAIL_HEADER: _AUDITOR}),
        audit_id,
        registry.pad(audit_id),
    )


def _opzet(tmp_path: Path) -> tuple[Path, str]:
    """Maak een audits-root met één audit en de findings erin."""
    root = tmp_path / "audits"
    registry = AuditRegistry(root)
    aid = registry.maak(normen=["9001"], periode="2026-Q3", door=_AUDITOR)
    d = registry.pad(aid)
    (d / "findings.json").write_text(json.dumps(_FINDINGS), encoding="utf-8")
    (d / "memo-input.yaml").write_text(
        (_EX / "memo-input.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return root, aid


def test_trail_overleeft_herstart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Triage-beslissingen zijn na een herstart identiek terug te lezen."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    root, aid = _opzet(tmp_path)

    voor = _nieuw_proces(root, aid)
    voor.post("/findings/f1", json={"triage_status": "valide", "reason": "bewijs gezien"})
    voor.post("/findings/f2", json={"triage_status": "niet_valide", "reason": "buiten scope"})
    trail_voor = voor.get("/trail").json()
    assert len(trail_voor) == 2

    na = _nieuw_proces(root, aid)
    assert na.get("/trail").json() == trail_voor


def test_trail_is_append_only_over_herstarts_heen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Een tweede proces voegt toe aan de trail en overschrijft niets."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    root, aid = _opzet(tmp_path)

    eerste = _nieuw_proces(root, aid)
    eerste.post("/findings/f1", json={"triage_status": "valide", "reason": "ronde 1"})
    eerste_trail = eerste.get("/trail").json()

    tweede = _nieuw_proces(root, aid)
    tweede.post("/findings/f2", json={"triage_status": "follow_up", "reason": "ronde 2"})
    tweede_trail = tweede.get("/trail").json()

    assert len(tweede_trail) == len(eerste_trail) + 1
    assert tweede_trail[: len(eerste_trail)] == eerste_trail, "oudere regels zijn gemuteerd"


def test_sessie_zonder_findings_faalt_hard(tmp_path: Path) -> None:
    """Geen stille lege sessie: een ontbrekende findings.json is een leesbare fout.

    Dit gedrag bestond al in `AuditSession.__init__`; de test legt het vast zodat het
    niet per ongeluk in een fallback verandert.
    """
    from iso_audit.api.session import SessionError

    with pytest.raises(SessionError, match=r"Geen findings\.json"):
        AuditSession(
            tmp_path,
            profile=str(_EX / "conduction.profile.yaml"),
            norms_dir="examples/norms",
            memo_input_path=str(_EX / "memo-input.yaml"),
        )


def test_db_pad_expliciet_wint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Met AUDIT_DB_PATH gezet wordt de repo-interne fallback niet gebruikt."""
    doel = tmp_path / "data" / "audit.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(doel))
    assert db_pad() == str(doel)


def test_db_pad_fallback_wordt_gemeld(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Zonder AUDIT_DB_PATH is er een fallback, maar geen stille fallback."""
    monkeypatch.delenv("AUDIT_DB_PATH", raising=False)
    monkeypatch.setattr("iso_audit.store._fallback_gemeld", False)

    with caplog.at_level("WARNING", logger="iso_audit.store"):
        assert db_pad() == DEFAULT_DB_PATH

    assert any("AUDIT_DB_PATH niet gezet" in r.message for r in caplog.records)
