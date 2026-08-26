"""De indicator die laat zien dat de app op de server wacht.

Gemeten op 2026-08-26 in het draaiende portaal: alleen `/instellingen/health` is traag — 3,5
seconden, want die test live verbindingen naar Drive, Jira en Nextcloud. Alle andere endpoints
zitten onder een halve seconde. Een spinner per scherm zou dus overwegend versiering zijn; het
echte probleem is dat er tijdens die ene wacht niets zichtbaar gebeurt.

Daarom één indicator, aangestuurd vanuit `j()` zelf. Dat dekt élke aanroep zonder dat iemand
het per scherm moet onthouden — dezelfde reden als bij `_get()` in de forge-client.

Geteld en niet booleaan: bij `Promise.all` lopen er meerdere tegelijk, en dan zou de eerste die
terugkomt de indicator uitzetten terwijl de trage nog loopt.
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
_FINDINGS = [
    {
        "id": "nc1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.14",
        "title": "Continuiteit",
        "description": "Niet getest.",
        "triage_status": "open",
    }
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
        "MIRO_API_TOKEN",
        "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE",
        "AUDIT_SOURCE_FOLDER_ID",
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
        yield page
        assert not fouten, f"JavaScript-fouten in de pagina: {fouten}"
        browser.close()


def test_de_indicator_is_weg_als_er_niets_loopt(pagina: Page) -> None:
    """Een indicator die blijft staan is erger dan geen indicator."""
    assert pagina.is_hidden("#bezig")


def test_j_zet_de_indicator_aan_voordat_hij_wacht(pagina: Page) -> None:
    """Deterministisch in plaats van een race: `j()` roept `_bezigAan()` synchroon aan, vóór
    zijn eerste `await`. Beide in één expressie meten laat geen ruimte voor timing."""
    zichtbaar = pagina.evaluate(
        "(() => {"
        "  window._p = j('/audits').catch(() => {});"
        "  return !document.getElementById('bezig').hidden;"
        "})()"
    )
    assert zichtbaar, "de indicator ging niet aan bij een lopende aanroep"


def test_hij_verdwijnt_weer_als_alles_klaar_is(pagina: Page) -> None:
    pagina.evaluate("loadFindings('')")
    pagina.wait_for_function("document.getElementById('bezig').hidden === true", timeout=10000)


def test_gelijktijdige_aanroepen_zetten_hem_niet_te_vroeg_uit(pagina: Page) -> None:
    """Bij `Promise.all` zou de eerste die terugkomt de indicator uitzetten."""
    pagina.evaluate(
        "window._t = (async () => {"
        "  _bezigAan(); _bezigAan();"
        "  return document.getElementById('bezig').hidden;"
        "})()"
    )
    pagina.evaluate("_bezigAf()")
    assert pagina.is_hidden("#bezig") is False, "één afronding mag hem niet uitzetten"
    pagina.evaluate("_bezigAf()")
    assert pagina.is_hidden("#bezig")


def test_hij_verdwijnt_ook_als_de_aanroep_faalt(pagina: Page) -> None:
    """Een mislukte aanroep die de indicator laat staan, laat het portaal bevroren lijken."""
    pagina.evaluate("j('/bestaat-niet').catch(() => {})")
    pagina.wait_for_function("document.getElementById('bezig').hidden === true", timeout=10000)
