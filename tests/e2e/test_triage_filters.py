"""End-to-end: filteren in de triage-tabel, in een echte browser.

De auditor meldde op 2026-08-26 dat hij niet op triage-status kon filteren, en ook niet op bron
of clausule. Met 271 bevindingen in één audit is dat geen comfort-kwestie — "wat staat er nog
open?" is de eerste vraag van elke triage-sessie.

Waarom in een browser en niet alleen tegen de API: de API kón het na tien regels, maar de knop
zat er niet. Precies dat gat — werkende route, geen bediening — is wat een contract-test niet
ziet en een gebruiker meteen.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api", reason="playwright niet geïnstalleerd")
from playwright.sync_api import Page, sync_playwright

from iso_audit.api.app import create_app
from iso_audit.api.registry import AuditRegistry

_EX = Path("examples/auditmemo")
_NORMS = Path("examples/norms")

_AUDIT_ID: list[str] = []
"""Het id dat de fixture aanmaakt; de pagina-fixture opent daarmee de juiste audit-route."""

_FINDINGS = [
    {
        "id": "f1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.14",
        "title": "Continuiteit niet getest",
        "description": "Niet getest.",
        "triage_status": "open",
        "source": "Drive/Continuiteitsplan.docx",
    },
    {
        "id": "f2",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.5",
        "title": "MFA niet gedefinieerd",
        "description": "Niet gedefinieerd.",
        "triage_status": "valide",
        "source": "Drive/Toegangsbeleid.docx",
    },
    {
        "id": "f3",
        "severity": "OFI",
        "standard": "iso-9001-2015",
        "clause": "10.2",
        "title": "Evaluatie niet vastgelegd",
        "description": "Niet vastgelegd.",
        "triage_status": "open",
        "source": "Jira/ISO-42",
    },
]


def _vrije_poort() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        poort: int = s.getsockname()[1]
        return poort


@pytest.fixture
def portaal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    for naam in (
        "JIRA_BASE_URL",
        "JIRA_API_TOKEN",
        "JIRA_PROJECTS",
        "MIRO_API_TOKEN",
        "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE",
        "GWS_IMPERSONATE_EMAIL",
        "AUDIT_SOURCE_FOLDER_ID",
        "AUDIT_DRIVE_FOLDER_ID",
        "AUDIT_PLANNING_SHEETS_ID",
    ):
        monkeypatch.delenv(naam, raising=False)

    registry = AuditRegistry(tmp_path / "audits")
    registry.root.mkdir(parents=True)
    aid = registry.maak(normen=["27001"], periode="2026-Q3", door="auditor@conduction.nl")
    (registry.root / aid / "findings.json").write_text(json.dumps(_FINDINGS), encoding="utf-8")
    _AUDIT_ID.append(aid)

    app = create_app(registry, profile=str(_EX / "conduction.profile.yaml"), norms_dir=_NORMS)
    poort = _vrije_poort()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=poort, log_level="warning"))
    draad = threading.Thread(target=server.run, daemon=True)
    draad.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{poort}"
    server.should_exit = True
    draad.join(timeout=5)


@pytest.fixture
def pagina(portaal: str) -> Iterator[Page]:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium niet beschikbaar ({exc})")
        page = browser.new_page()
        fouten: list[str] = []
        page.on("pageerror", lambda e: fouten.append(str(e)))
        page.goto(f"{portaal}/#/audit/{_AUDIT_ID[-1]}", wait_until="networkidle")
        page.wait_for_selector("#triage-wrap table", timeout=15000)
        yield page
        assert not fouten, f"JavaScript-fouten in de pagina: {fouten}"
        browser.close()


def _titels(pagina: Page) -> set[str]:
    return {
        t.strip("▸ ").strip() for t in pagina.locator("#triage-wrap td.f-title").all_inner_texts()
    }


def test_zonder_filter_staat_alles_in_de_tabel(pagina: Page) -> None:
    assert len(_titels(pagina)) == 3


def test_filteren_op_open_triage(pagina: Page) -> None:
    pagina.select_option("#flt-triage", "open")
    pagina.wait_for_function(
        "document.querySelectorAll('#triage-wrap tbody tr.sevrow-NC').length === 1"
    )
    assert _titels(pagina) == {"Continuiteit niet getest", "Evaluatie niet vastgelegd"}


def test_filteren_op_bron_met_een_deel_van_de_naam(pagina: Page) -> None:
    pagina.fill("#flt-bron", "jira")
    pagina.click("#triage-filter2 button:has-text('Toepassen')")
    pagina.wait_for_function(
        "document.querySelectorAll('#triage-wrap tbody tr[data-id]').length === 1"
    )
    assert _titels(pagina) == {"Evaluatie niet vastgelegd"}


def test_filteren_op_hoofdstuk(pagina: Page) -> None:
    """`8` moet §8.5 en §8.14 geven — niet elke subclausule los hoeven weten."""
    pagina.fill("#flt-clausule", "8")
    pagina.click("#triage-filter2 button:has-text('Toepassen')")
    pagina.wait_for_function(
        "document.querySelectorAll('#triage-wrap tbody tr[data-id]').length === 2"
    )
    assert _titels(pagina) == {"Continuiteit niet getest", "MFA niet gedefinieerd"}


def test_filters_stapelen_met_de_classificatieknop(pagina: Page) -> None:
    """De nieuwe filters mogen de bestaande NC/OFI-knop niet resetten."""
    pagina.click("#triage-filter button:has-text('NC')")
    pagina.select_option("#flt-triage", "open")
    pagina.wait_for_function(
        "document.querySelectorAll('#triage-wrap tbody tr[data-id]').length === 1"
    )
    assert _titels(pagina) == {"Continuiteit niet getest"}


def test_wissen_brengt_alles_terug(pagina: Page) -> None:
    pagina.select_option("#flt-triage", "valide")
    pagina.wait_for_function(
        "document.querySelectorAll('#triage-wrap tbody tr[data-id]').length === 1"
    )
    pagina.click("#triage-filter2 button:has-text('Wissen')")
    pagina.wait_for_function(
        "document.querySelectorAll('#triage-wrap tbody tr[data-id]').length === 3"
    )
    assert len(_titels(pagina)) == 3
