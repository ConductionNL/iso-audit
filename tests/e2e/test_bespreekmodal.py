"""End-to-end: de besprekingsmodal, in een echte browser.

Het memo naast zijn eigen actietabel, zodat eigenaren en data tijdens de bespreking worden
ingevuld. Dat hoort in het portaal en niet in een los .docx: anders bewerkt iemand buiten het
systeem en weet de audit-trail niet wie wat heeft toegezegd. Een managementmemo waarvan de
toezeggingen niet herleidbaar zijn, is precies waar een externe auditor een NC op schrijft.

Waarom in een browser: het patroon dat deze dag drie keer terugkwam is dat de route het al kon
en de bediening ontbrak. Dat ziet een contract-test niet en een gebruiker meteen.
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
        "id": "nc1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.14",
        "title": "Continuiteit niet getest",
        "description": "Niet getest.",
        "thema": "Back-up & continuiteit",
        "triage_status": "valide",
        "actions": [{"wat": "Continuiteitstest inplannen"}],
    },
    {
        "id": "ofi1",
        "severity": "OFI",
        "standard": "iso-27001-2022",
        "clause": "8.15",
        "title": "Logging zonder baseline",
        "description": "Geen baseline.",
        "thema": "Logging & monitoring",
        "actions": [{"wat": "Baseline beschrijven"}],
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
        page.wait_for_selector("#btn-bespreken", timeout=15000)
        yield page
        assert not fouten, f"JavaScript-fouten in de pagina: {fouten}"
        browser.close()


def test_de_modal_gaat_open_en_toont_de_actietabel(pagina: Page) -> None:
    pagina.click("#btn-bespreken")
    pagina.wait_for_selector("#bespreek-acties table", timeout=15000)
    tekst = pagina.locator("#bespreek-acties").inner_text()
    assert "Continuiteitstest inplannen" in tekst
    assert "Baseline beschrijven" in tekst


def test_de_acties_staan_op_thema_gegroepeerd(pagina: Page) -> None:
    """Zelfde indeling als de blokken in het memo, anders zoekt de lezer zich suf."""
    pagina.click("#btn-bespreken")
    pagina.wait_for_selector("#bespreek-acties table", timeout=15000)
    koppen = pagina.locator("#bespreek-acties tr.thema-kop").all_inner_texts()
    assert any("Back-up" in k for k in koppen), koppen
    assert any("Logging" in k for k in koppen), koppen


def test_de_modal_toont_het_memo(pagina: Page) -> None:
    pagina.click("#btn-bespreken")
    pagina.wait_for_selector("#bespreek-pdf", timeout=15000)
    bron = pagina.get_attribute("#bespreek-pdf", "src") or ""
    assert bron.endswith("/memo/pdf"), bron


def test_een_eigenaar_invullen_wordt_bewaard(pagina: Page) -> None:
    pagina.click("#btn-bespreken")
    pagina.wait_for_selector("#bespreek-acties table", timeout=15000)
    rij = pagina.locator('#bespreek-acties tr[data-rij="nc1|0"]')
    rij.locator(".a-wie").fill("CISO")
    rij.locator(".a-uiterlijk").fill("2026-10-01")
    rij.locator("button").click()
    pagina.wait_for_function(
        "document.querySelector('#bespreek-acties tr[data-rij=\"nc1|0\"] .ok').textContent === '✓'"
    )
    # Opnieuw laden: de waarde komt uit de werkset en niet uit het invoerveld.
    pagina.click("button:has-text('Sluiten')")
    pagina.click("#btn-bespreken")
    pagina.wait_for_selector("#bespreek-acties table", timeout=15000)
    assert pagina.input_value('#bespreek-acties tr[data-rij="nc1|0"] .a-wie') == "CISO"


def test_sluiten_laat_geen_memo_in_het_geheugen_achter(pagina: Page) -> None:
    pagina.click("#btn-bespreken")
    pagina.wait_for_selector("#bespreek-acties table", timeout=15000)
    pagina.click("button:has-text('Sluiten')")
    assert pagina.is_hidden("#bespreek-modal")
