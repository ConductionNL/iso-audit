"""Tests voor `ui.html` als contract met de API (taak 3 van change portal-dashboard).

Dit is geen browser-test. Wat hier bewaakt wordt, is het gat dat je in een
single-file UI zonder build-stap niet ziet: dat de UI een route aanroept die de API
niet meer heeft. De vorige UI ging uit van ongescopede paden (`/findings`); nu moet
elk audit-gescoped pad via de `A()`-helper lopen. Een vergeten `A()` levert in de
browser een 404 en hier een falende test.
"""

from __future__ import annotations

import re
from pathlib import Path

UI = Path("src/iso_audit/api/ui.html")

# Paden die bewust NIET onder een audit vallen.
ONGESCOPED = {
    "/audits",
    # Het documentenlandschap hoort bij de organisatie en niet bij één audit: één
    # voorraad die alle audits gebruiken. Daarom bewust zonder audit-prefix.
    "/landschap",
    "/config/health",
    "/config/options",
    "/config/bronnen",
    "/config/wijzigingen",
    "/config/herkomst",
    "/config/anthropic",
    "/me",
}


def _bron() -> str:
    return UI.read_text(encoding="utf-8")


def test_ui_is_een_bestand_zonder_buildstap() -> None:
    """Geen bundler, geen imports: de UI blijft te lezen en te patchen zonder toolchain."""
    bron = _bron()
    assert "<script>" in bron
    assert 'src="http' not in bron, (
        "externe scriptbron gevonden — dat is een buildstap in vermomming"
    )
    assert "import " not in bron.split("<script>")[1][:200]


def test_alle_auditcalls_lopen_via_de_prefix_helper() -> None:
    """Een vergeten `A()` is een 404 in de browser en verder onzichtbaar."""
    bron = _bron()
    losse = set()
    for m in re.finditer(r'(?:fetch|j)\(\s*(["`])(/[^"`]*)\1', bron):
        pad = m.group(2)
        basis = pad.split("?")[0]
        if not any(basis == o or basis.startswith(o + "/") for o in ONGESCOPED):
            losse.add(pad)
    assert not losse, f"deze paden missen de audit-prefix: {sorted(losse)}"


def test_prefix_helper_encodeert_het_audit_id() -> None:
    """Het id komt uit de URL-hash; zonder encoding breekt een id met vreemde tekens."""
    bron = _bron()
    assert "encodeURIComponent(AUDIT)" in bron


def test_drie_views_en_hash_routing() -> None:
    bron = _bron()
    for view in ("view-dashboard", "view-audit", "view-config"):
        assert f'id="{view}"' in bron
    assert 'window.addEventListener("hashchange"' in bron
    assert "#/audit/" in bron


def test_dashboard_toont_de_vier_gevraagde_kolommen() -> None:
    """Norm+periode met status, triage-voortgang, bronnen, en wie het laatst bewerkte."""
    bron = _bron()
    kop = bron.split("<th>Audit</th>")[1].split("</tr>")[0]
    for kolom in ("Status", "Triage", "Bronnen", "Laatst bewerkt"):
        assert f"<th>{kolom}</th>" in kop


def test_configscherm_kan_een_bron_koppelen() -> None:
    """Zapier-achtig: kies een bron, klik, configureer. Zonder cluster of beheerder."""
    bron = _bron()
    assert 'id="view-config"' in bron
    assert "toonBronForm" in bron and "bewaarBron" in bron
    assert "/config/bronnen/" in bron


def test_openen_van_een_audit_laadt_ook_de_bronselectie() -> None:
    """Zonder deze aanroep is #config-form leeg tot iemand op een knop klikt, en stuurt
    `selectedConfig()` `sources: []` mee — een run die niets leest terwijl de auditor
    bronnen dénkt te hebben gekozen."""
    bron = _bron()
    lichaam = bron.split("async function openAudit(")[1].split("\nasync function")[0]
    assert "loadConfig()" in lichaam


def test_elk_configuratieveld_is_gewoon_invulbaar() -> None:
    """Geen `readonly`, geen extra bevestigingsstap.

    Er hebben hier achtereenvolgens een badge, een slot en een bevestigingsknop gestaan.
    De badge was te zwak (typen had geen effect), het slot te hard (een geroteerde key
    was niet te vervangen) en de knop overbodig zodra invullen écht werkt. Wat blijft is
    de projectregel uit `bron_config.py`: registratie is de controle, niet het moeilijk
    maken van configureren.
    """
    bron = _bron()
    invoer = bron.split("function toonBronForm(")[1].split("// Meteen zeggen")[0]
    assert "readonly" not in invoer.lower()
    assert "Toch overschrijven" not in invoer
    assert "Terug naar de omgeving" in invoer, "een overschrijving moet terug te draaien zijn"


def test_er_is_een_testknop_met_zichtbaar_resultaat() -> None:
    """Zonder terugkoppeling vul je een token in, krijg je "opgeslagen", en weet je nog
    steeds niet of de koppeling werkt."""
    bron = _bron()
    assert "async function testBron(" in bron
    assert "/config/health/" in bron, "test één bron, niet alle bronnen"
    assert ">Testen</button>" in bron
    bewaar = bron.split("async function bewaarBron(")[1].split("\nasync function")[0]
    assert "testBron(naam)" in bewaar, "na opslaan meteen testen"


def test_de_ui_wordt_niet_gecachet(tmp_path: Path) -> None:
    """Eén HTML-bestand zonder buildstap heeft geen versie in de URL. Zonder `no-store`
    zit een auditor na een uitrol op een oud scherm zonder het te merken — dat kostte hier
    een sessie aan verwarring over knoppen die er wél waren."""
    from fastapi.testclient import TestClient

    from iso_audit.api.app import create_app
    from iso_audit.api.registry import AuditRegistry

    from .conftest import AUDITOR, EXAMPLES, NORMS

    registry = AuditRegistry(tmp_path / "audits")
    registry.root.mkdir(parents=True)
    app = create_app(registry, profile=str(EXAMPLES / "conduction.profile.yaml"), norms_dir=NORMS)
    r = TestClient(app, headers={"X-Forwarded-Email": AUDITOR}).get("/")

    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "")


def test_de_ui_kent_alle_herkomsten_die_de_server_kan_geven() -> None:
    """Een single-file UI heeft geen buildstap; dit is de enige manier om te merken dat de
    backend een herkomst toevoegt die het scherm niet kan tonen."""
    from iso_audit.config.settings import Bron

    bron = _bron()
    labels = bron.split("const BRON_LABEL")[1].split("};")[0]
    for waarde in Bron.__args__:  # type: ignore[attr-defined]
        assert waarde in labels, f"herkomst {waarde!r} heeft geen label in de UI"


def test_geheime_velden_worden_als_wachtwoord_getoond() -> None:
    bron = _bron()
    assert 'type="${v.geheim ? "password" : "text"}"' in bron


def test_configscherm_noemt_geen_env_vars_of_secrets() -> None:
    """De auditor hoeft niets te weten van env-vars, Secrets of een cluster."""
    bron = _bron()
    blok = bron.split('id="view-config"')[1].split("</section>")[0]
    for jargon in ("env-var", "Secret", "cluster", "manifest", "JIRA_", "MIRO_"):
        assert jargon not in blok, f"implementatiejargon in het configscherm: {jargon}"


def test_audit_wissel_maakt_de_vorige_audit_leeg() -> None:
    """Anders zie je data van audit A terwijl de kop audit B zegt."""
    bron = _bron()
    blok = bron.split("async function openAudit()")[1].split("async function loadRuns()")[0]
    assert "triage-wrap" in blok and 'innerHTML = ""' in blok


def test_gelijktijdigheidswaarschuwing_wordt_getoond() -> None:
    """De registry levert `andere_actief`; de UI moet er iets mee doen."""
    bron = _bron()
    assert "andere_actief" in bron
    assert "audit-warn" in bron


def test_uitlogknop_bestaat() -> None:
    """Een portaal zonder uitlogknop kun je alleen verlaten door je browser te sluiten."""
    bron = _bron()
    assert 'id="uitloggen"' in bron
    assert "/oauth2/sign_out" in bron
    assert 'j("/me")' in bron


def test_normkeuze_is_een_enum_zonder_jargon() -> None:
    """De auditor kiest een norm of beide; slugs, id-formaat en YAML horen niet in de UI."""
    bron = _bron()
    formulier = bron.split('id="nieuw-audit"')[1].split("</div>")[0]
    assert "select" in formulier and "na-norm" in formulier
    assert "checkbox" not in formulier, "vinkjes: je kiest een auditscope, geen verzameling"
    for jargon in ("YAML", "yaml", "norm-DB", "9001_27001", "JJJJ-Qn"):
        assert jargon not in formulier, f"implementatiejargon in het formulier: {jargon}"


def test_normlabel_verbergt_de_slug() -> None:
    bron = _bron()
    assert "function normLabel" in bron
    assert "ISO ${m[1]}" in bron


def test_configscherm_toont_de_herkomst_per_veld() -> None:
    """Zonder herkomst-badge typt een auditor iets in dat stil geen effect heeft."""
    bron = _bron()
    assert 'j("/config/herkomst")' in bron
    assert "bronBadge" in bron
    assert "BRON_LABEL" in bron


def test_door_beheerder_gezette_velden_zijn_zichtbaar_vast() -> None:
    """env en yaml kunnen in de UI niet overschreven worden; dat moet je kunnen zien."""
    bron = _bron()
    assert 'h.bron === "env" || h.bron === "yaml"' in bron
    assert "bronbadge.vast" in bron
