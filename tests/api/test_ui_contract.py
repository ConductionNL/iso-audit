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
ONGESCOPED = {"/audits", "/config/health", "/config/options"}


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
        if basis not in ONGESCOPED:
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


def test_configscherm_heeft_geen_schrijfroute() -> None:
    """Alleen-lezen is de eis; een POST naar /config zou die stilzwijgend breken."""
    bron = _bron()
    assert not re.search(r'fetch\(\s*["`]/config[^"`]*["`]\s*,\s*\{[^}]*POST', bron)
    assert 'id="view-config"' in bron


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
