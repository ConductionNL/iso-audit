"""End-to-end: het landschapsscherm in een echte browser.

De keten die de opdrachtgever verwacht en die hier wordt afgelopen:

1. landschap inlezen
2. **in de UI zien of het klopt** — welke documenten, welke bron, welke clausules
3. erin kunnen zoeken
4. daarna pas normen of hoofdstukken kiezen en auditen

Stap 2 en 3 ontbraken volledig: er werd wel ingelezen, maar er was geen enkel scherm waarop
je kon controleren wát er was ingelezen. Een run was daarmee een black box.
"""

from __future__ import annotations

import socket
import sqlite3
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


def _vrije_poort() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        poort: int = s.getsockname()[1]
        return poort


def _vul_db(pad: Path) -> None:
    """Een landschap zoals een echte ingest het achterlaat."""
    from iso_audit.store import initialiseer, upsert_clause_match, upsert_document

    conn = sqlite3.connect(pad)
    try:
        initialiseer(conn)
        upsert_document(
            conn,
            {
                "id": "d1",
                "naam": "Kwaliteitshandboek.docx",
                "tekst": "beleid over directiebeoordeling en context",
                "herkomst": "Drive",
                "mime_type": "docx",
                "modified_at": "2026-05-01T10:00:00Z",
            },
        )
        upsert_document(
            conn,
            {
                "id": "d2",
                "naam": "Notulen MT 2026-03.docx",
                "tekst": "besluitvorming over leveranciers",
                "herkomst": "Drive",
                "mime_type": "docx",
                "modified_at": "2026-03-11T10:00:00Z",
            },
        )
        upsert_clause_match(conn, "d1", "Drive", "5.2", "9001")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def portaal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    db = tmp_path / "audit.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(db))
    for naam in ("JIRA_BASE_URL", "JIRA_API_TOKEN", "MIRO_API_TOKEN", "AUDIT_SOURCE_FOLDER_ID"):
        monkeypatch.delenv(naam, raising=False)
    _vul_db(db)

    registry = AuditRegistry(tmp_path / "audits")
    registry.root.mkdir(parents=True)
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
        page.goto(f"{portaal}/#/landschap", wait_until="networkidle")
        yield page
        assert not fouten, f"JavaScript-fouten in de pagina: {fouten}"
        browser.close()


def test_landschap_toont_wat_er_is_ingelezen(pagina: Page) -> None:
    """De vraag die dit scherm moet beantwoorden: klopt dit, is dit wat we hebben gezien?"""
    pagina.wait_for_selector("#ls-staat", timeout=15000)
    staat = pagina.locator("#ls-staat").inner_text()
    assert "2" in staat, f"aantal documenten ontbreekt: {staat!r}"
    assert "Drive" in staat

    tabel = pagina.locator("#ls-docs").inner_text()
    assert "Kwaliteitshandboek.docx" in tabel
    assert "Notulen MT 2026-03.docx" in tabel


def test_landschap_toont_de_clausule_koppeling(pagina: Page) -> None:
    """Zonder koppeling wordt een document in een run niet aan een norm getoetst; dat moet
    zichtbaar zijn vóór de run, niet achteraf uit de uitkomst blijken."""
    pagina.wait_for_selector("#ls-docs table", timeout=15000)
    rij = pagina.locator("#ls-docs tr", has_text="Kwaliteitshandboek").inner_text()
    assert "5.2" in rij
    zonder = pagina.locator("#ls-docs tr", has_text="Notulen MT").inner_text()
    assert "geen koppeling" in zonder


def test_zoeken_in_het_landschap(pagina: Page) -> None:
    """Zoeken over naam én inhoud, via de FTS-index die al bestond maar nergens werd
    gebruikt."""
    pagina.wait_for_selector("#ls-docs table", timeout=15000)
    pagina.locator("#ls-zoek").fill("directiebeoordeling")
    pagina.click("#ls-docs >> xpath=..//button[contains(text(),'Zoeken')]")
    pagina.wait_for_function(
        "document.querySelectorAll('#ls-docs tbody tr').length === 1", timeout=15000
    )
    assert "Kwaliteitshandboek" in pagina.locator("#ls-docs").inner_text()


def test_landschap_is_bereikbaar_zonder_audit(pagina: Page) -> None:
    """Het landschap hoort bij de organisatie, niet bij één audit — dus zonder een audit
    te openen te bereiken."""
    assert pagina.locator("#view-landschap").is_visible()
    assert pagina.locator("#nav-landschap").get_attribute("aria-current") == "page"
