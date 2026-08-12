"""Tests voor het toegangs-audit-log (`iso_audit.api.audit_log`, sec-bevinding 4 + 6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from iso_audit.api.audit_log import log_event
from iso_audit.api.auth_gate import DEV_IDENTITEIT, EMAIL_HEADER, REQUIRE_AUTH_ENV

from .conftest import PortaalClient, maak_portaal

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


def _client(tmp_path: Path, **kwargs: object) -> PortaalClient:
    return maak_portaal(tmp_path, findings=_FINDINGS, headers=kwargs.get("headers", {}))  # type: ignore[arg-type]


def _regels(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [json.loads(r.message) for r in caplog.records if r.name == "iso_audit.audit"]


# --- log_event zelf --------------------------------------------------------


def test_log_event_is_jsonl_met_vaste_velden(caplog: pytest.LogCaptureFixture) -> None:
    """Elke regel is losse JSON met ts, soort en identiteit."""
    with caplog.at_level("INFO", logger="iso_audit.audit"):
        log_event("test", _AUDITOR, pad="/x")

    (regel,) = _regels(caplog)
    assert regel["soort"] == "test"
    assert regel["identiteit"] == _AUDITOR
    assert regel["pad"] == "/x"
    assert str(regel["ts"]).endswith("Z")


def test_log_event_kapt_niet_scalars_af(caplog: pytest.LogCaptureFixture) -> None:
    """Een per ongeluk doorgegeven object stort geen volledige structuur uit."""
    with caplog.at_level("INFO", logger="iso_audit.audit"):
        log_event("test", _AUDITOR, brok={"geheim": "x" * 500})

    (regel,) = _regels(caplog)
    assert len(str(regel["brok"])) <= 200


# --- via de app -----------------------------------------------------------


def test_geweigerde_auth_wordt_gelogd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Een 403 laat een spoor achter; anders is een aanvalspoging onzichtbaar."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    client = _client(tmp_path)
    with caplog.at_level("INFO", logger="iso_audit.audit"):
        client.get("/findings")

    soorten = [r["soort"] for r in _regels(caplog)]
    assert "auth_geweigerd" in soorten


def test_mutatie_wordt_gelogd_met_identiteit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Een wijziging van auditdata is herleidbaar naar een mens."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    client = _client(tmp_path, headers={EMAIL_HEADER: _AUDITOR})
    with caplog.at_level("INFO", logger="iso_audit.audit"):
        client.post("/findings/f1", json={"triage_status": "valide", "reason": "ok"})

    mutaties = [r for r in _regels(caplog) if r["soort"] == "mutatie"]
    assert mutaties
    assert all(r["identiteit"] == _AUDITOR for r in mutaties)
    # Het pad bevat nu het audit-id — dat is de winst van de audit-scoping: uit het
    # log alleen is te zien in wélke audit iemand muteerde.
    assert any(r["pad"] == f"/audits/{client.audit_id}/findings/f1" for r in mutaties)


def test_leesverzoek_wordt_niet_gelogd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Alleen muterende verzoeken; anders verzuipt het log in GET-ruis."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    client = _client(tmp_path, headers={EMAIL_HEADER: _AUDITOR})
    with caplog.at_level("INFO", logger="iso_audit.audit"):
        client.get("/findings")

    assert _regels(caplog) == []


def test_run_start_logt_kosten_attributie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Wie een kosten-dragende run start, staat in het log (sec-bevinding 6)."""
    monkeypatch.delenv(REQUIRE_AUTH_ENV, raising=False)
    client = _client(tmp_path, headers={EMAIL_HEADER: _AUDITOR})
    with caplog.at_level("INFO", logger="iso_audit.audit"):
        client.post("/run/start", json={"mode": "sim", "norm": "9001", "sources": ["drive"]})

    runs = [r for r in _regels(caplog) if r["soort"] == "run_gestart"]
    assert runs, "run-start is niet gelogd"
    assert runs[0]["identiteit"] == _AUDITOR
    assert runs[0]["bronnen"] == "drive"


def test_geen_headers_of_cookies_in_het_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Een meegestuurd token mag nergens in een logregel opduiken.

    Structureel gegarandeerd: `log_event` krijgt het request-object nooit te zien.
    Deze test legt dat vast zodat een latere refactor het niet stilletjes omdraait.
    """
    monkeypatch.setenv(REQUIRE_AUTH_ENV, "false")
    geheim = "sk-ant-nooit-loggen-abc123"  # testwaarde, geen echte key
    client = _client(tmp_path, headers={"Authorization": f"Bearer {geheim}"})
    with caplog.at_level("INFO", logger="iso_audit.audit"):
        client.post("/findings/f1", json={"triage_status": "valide", "reason": "ok"})

    tekst = json.dumps(_regels(caplog))
    assert geheim not in tekst
    assert "Bearer" not in tekst
    assert DEV_IDENTITEIT in tekst
