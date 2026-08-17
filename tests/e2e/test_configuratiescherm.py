"""End-to-end: het configuratiescherm in een echte browser.

## Waarom dit bestaat

De rest van de suite test de API en de HTML-broncode. Dat is niet genoeg gebleken: op
2026-08-15 was de server aantoonbaar correct — de juiste velden in `/instellingen/bronnen`, de
juiste JS in `ui.html` — terwijl een auditor in de browser **niets kon invullen**. Een
contract-test op de brontekst ziet dat niet, want die voert de JS nooit uit.

Deze tests draaien het portaal en bedienen het met een echte browser: typen, klikken,
kijken wat er op het scherm staat. Dat is de enige laag die de vraag beantwoordt die de
gebruiker stelt, namelijk "kan ik dit invullen".

Draaien: `uv run pytest tests/e2e -q`. Vereist de Chromium van Playwright
(`uv run playwright install chromium`); zonder die browser slaan de tests zichzelf over
in plaats van de suite rood te maken.
"""

from __future__ import annotations

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


def _vrije_poort() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        poort: int = s.getsockname()[1]
        return poort


@pytest.fixture
def portaal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Start het portaal in een thread en geef het basis-URL terug.

    `JIRA_BASE_URL` staat bewust in de omgeving: dat is het geval waarop het misging —
    een veld met een beheerderswaarde erachter moet gewoon in te vullen zijn.

    Het `.invalid`-domein is gereserveerd en resolvet nooit. De verbindingstest faalt
    daardoor snel en zónder netwerk: een testsuite die van het internet afhangt is
    onbetrouwbaar, en de bedoeling hier is de UI te testen, niet Jira.
    """
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    monkeypatch.setenv("JIRA_BASE_URL", "https://van-de-beheerder.invalid")
    # Álle bronconfiguratie leeg, ook de Google-variabelen. Zonder die laatste doet het
    # configuratiescherm bij elk herladen een echte Drive-call met de credentials van de
    # ontwikkelaar: traag, afhankelijk van het netwerk, en het leest productiedata. Dat
    # maakte deze test wisselvallig in de volledige suite — wat op een timeout leek maar
    # een ontbrekende isolatie was.
    for naam in (
        "JIRA_USER_EMAIL",
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
        except Exception as exc:  # geen browser geïnstalleerd
            pytest.skip(
                f"Chromium niet beschikbaar ({exc}); draai `uv run playwright install chromium`"
            )
        page = browser.new_page()
        fouten: list[str] = []
        page.on("pageerror", lambda e: fouten.append(str(e)))
        page.goto(portaal, wait_until="networkidle")
        yield page
        # Een JS-fout sloopt het hele scherm zonder dat de server iets merkt; dat is
        # precies hoe "ik kan niets invullen" kan ontstaan bij een correcte backend.
        assert not fouten, f"JavaScript-fouten in de pagina: {fouten}"
        browser.close()


def _open_config(pagina: Page, bron: str) -> None:
    pagina.click("#nav-config")
    pagina.wait_for_selector(f"#kaart-{bron}", timeout=30000)
    pagina.click(f"#kaart-{bron} button:has-text('Configureer')")
    pagina.wait_for_selector(f"#bf-{bron} input", timeout=15000)


def test_een_veld_met_een_beheerderswaarde_is_typbaar(pagina: Page) -> None:
    """De klacht van 2026-08-15, als test. Dit veld had een readonly-attribuut."""
    _open_config(pagina, "jira")
    veld = pagina.locator("#v-jira-JIRA_BASE_URL")

    assert veld.is_editable(), "veld met een omgevingswaarde moet gewoon in te vullen zijn"
    veld.fill("https://door-de-auditor.example")
    assert veld.input_value() == "https://door-de-auditor.example"


def test_alle_velden_van_een_bron_zijn_typbaar(pagina: Page) -> None:
    """Niet één veld, maar het hele formulier — de klacht was "ik kan níets invullen"."""
    _open_config(pagina, "jira")
    velden = pagina.locator("#bf-jira input")
    aantal = velden.count()
    assert aantal >= 4, f"verwacht minstens 4 Jira-velden, kreeg {aantal}"
    for i in range(aantal):
        assert velden.nth(i).is_editable(), f"veld {i} is niet invulbaar"


def test_er_is_geen_extra_bevestigingsknop(pagina: Page) -> None:
    """Die heeft er even gestaan en was niet gevraagd; invullen moet in één handeling."""
    _open_config(pagina, "jira")
    assert pagina.locator("#bf-jira").get_by_text("Toch overschrijven").count() == 0


def test_opslaan_geeft_zichtbare_terugkoppeling(pagina: Page) -> None:
    """Zonder testuitslag weet je na het opslaan nog steeds niet of de koppeling werkt."""
    _open_config(pagina, "jira")
    pagina.locator("#v-jira-JIRA_USER_EMAIL").fill("iso-tool@serviceaccount.atlassian.com")
    pagina.locator("#v-jira-JIRA_API_TOKEN").fill("niet-geldig-token")
    pagina.click("#bf-jira button:has-text('Opslaan en testen')")

    pagina.wait_for_selector("#bs-jira:has-text('opgeslagen')", timeout=30000)
    # Wachten op de uitkomst, niet op "niet meer leeg": dat laatste is al waar zodra er
    # "bezig met testen…" staat, en dan leest de test de tussenstand. Precies de fout die
    # deze suite elders opspoort — een controle die op een tussentoestand afgaat.
    pagina.wait_for_selector("#bt-jira:has-text('gekoppeld')", timeout=60000)
    uitslag = pagina.locator("#bt-jira").inner_text()
    assert "gekoppeld" in uitslag, f"geen leesbare testuitslag: {uitslag!r}"


def test_de_testknop_werkt_los_van_opslaan(pagina: Page) -> None:
    _open_config(pagina, "miro")
    pagina.click("#bf-miro button:has-text('Testen')")
    # Ook hier op de uitkomst wachten en niet op "niet meer leeg".
    pagina.wait_for_selector("#bt-miro:has-text('niet gekoppeld')", timeout=30000)
    assert "niet gekoppeld" in pagina.locator("#bt-miro").inner_text()


def test_een_ingevulde_waarde_vervangt_de_omgeving_en_is_terug_te_draaien(
    pagina: Page,
) -> None:
    """Het rotatiegeval, helemaal door de browser heen."""
    _open_config(pagina, "jira")
    pagina.locator("#v-jira-JIRA_BASE_URL").fill("https://door-de-auditor.example")
    pagina.click("#bf-jira button:has-text('Opslaan en testen')")
    pagina.wait_for_selector(
        "#bf-jira:has-text('Vervangt de waarde uit de omgeving')", timeout=15000
    )

    pagina.click("#bf-jira button:has-text('Terug naar de omgeving')")
    # Wachten tot het scherm daadwerkelijk is herladen, anders leest de test het oude
    # formulier — een race die als een bug leest.
    pagina.wait_for_selector(
        "#bf-jira:has-text('Vervangt de waarde uit de omgeving')", state="detached", timeout=15000
    )
    pagina.click("#kaart-jira button:has-text('Configureer')")
    pagina.wait_for_selector("#v-jira-JIRA_BASE_URL", timeout=15000)
    assert pagina.locator("#v-jira-JIRA_BASE_URL").input_value() == (
        "https://van-de-beheerder.invalid"
    )
