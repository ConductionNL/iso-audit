"""Tests voor de memo-renderer (HTML + PDF)."""

from __future__ import annotations

from pathlib import Path

import pytest

from iso_audit.memo.models import (
    ActionRow,
    AuditMemo,
    ClauseCitation,
    ImprovementBlock,
    MemoContext,
    NCBlock,
)
from iso_audit.memo.renderer.html import MemoRendererImpl
from iso_audit.memo.theme.profile import Profile

_LOGO = '<svg viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>'


def _profiel() -> Profile:
    return Profile(
        schema_version=1,
        slug="conduction",
        organization={"name": "Conduction B.V."},
        auditor={"name": "Mark", "role": "ISO-auditor"},
        brand={"logo_svg": _LOGO, "colors": {"primary": "#4376fc"}},
    )


def _memo() -> AuditMemo:
    cit = ClauseCitation(
        standard="ISO 27001:2022",
        clause="6.5",
        title="Verantwoordelijkheden",
        text="Verplichtingen...",
    )
    nc = NCBlock(
        title="NC 1 — Opvolging",
        citations=[cit],
        deviation="<p>Afwijking <strong>hier</strong>.</p>",
        pattern_note="De praktijk werkt deels.",
        corrective_measure="Bundel de memo's.",
        actions=[ActionRow(wat="Register opzetten", uiterlijk="2026-Q3")],
    )
    imp = ImprovementBlock(
        code="OFI 1",
        title="Logging-baseline",
        citations=[cit],
        deviation="Geen baseline.",
        classification_rationale="Operationeel werkt het; vastlegging ontbreekt.",
        suggestion="Eén pagina per platform.",
    )
    ctx = MemoContext(
        audit_cycle="Q2 2026",
        scope={"ISO 9001:2015": "§4-10"},
        sources=["Google Drive", "Miro"],
        dataset_counts={"NC": 2, "OFI": 297, "positief": 122},
        scope_caveat="Tool zag alleen Drive/Miro.",
    )
    return AuditMemo(
        title="Auditmemo — Test",
        subtitle="Mark | ISO-auditor · Q2 2026",
        date="06-05-2026",
        version="v2",
        lead_summary="<strong>2 NC</strong> en 1 verbeterpunt.",
        context=ctx,
        nc_blocks=[nc],
        improvements=[imp],
        historical_ncs=[],
        detail_report_ref="detail.pdf",
    )


def test_render_html_bevat_kernsecties() -> None:
    html = MemoRendererImpl().render_html(_memo(), _profiel())
    for needle in [
        "NC 1 — Opvolging",
        "OFI 1 — Logging-baseline",
        "Waarom verbeterpunt en geen NC?",
        "Verantwoordelijkheden",
        "De praktijk werkt deels.",
        "#4376fc",  # palette uit profiel
        "eigenaar in te vullen",  # placeholder
        "<svg",  # inline logo
        "297 OFI",  # dataset-telling in context
    ]:
        assert needle in html, f"ontbreekt: {needle}"


def test_render_html_escaped_geen_placeholder_voor_ingevulde_cel() -> None:
    html = MemoRendererImpl().render_html(_memo(), _profiel())
    assert "2026-Q3" in html  # ingevulde uiterlijk-cel, geen placeholder


def _memo_met_nc(triage: str, reasoning: list[str]) -> AuditMemo:
    m = _memo()
    m.nc_blocks[0].triage_status = triage  # type: ignore[assignment]
    m.nc_blocks[0].reasoning = reasoning
    return m


def test_triage_checklist_voor_open_kandidaat() -> None:
    html = MemoRendererImpl().render_html(
        _memo_met_nc("open", ["ruwe bevinding A", "ruwe bevinding B"]), _profiel()
    )
    assert 'class="triage"' in html
    assert "Nog te beoordelen" in html
    assert "valide" in html and "niet valide" in html
    # De ruwe redenatielijst staat sinds 2026-08-26 niet meer in de memo maar in het
    # detailrapport: de memo is een bespreekstuk van 1-3 A4 en de triage doet de auditor in het
    # portaal, niet in een PDF. Wat blijft is de verwijzing — inkorten mag geen weglaten worden.
    assert "Onderbouwing" in html and "detail.pdf" in html
    # De ruwe redenatie zelf staat in het detailrapport; in de memo staat de verwijzing.
    # Zie de toelichting hierboven.


def test_geen_triage_voor_valide_nc() -> None:
    html = MemoRendererImpl().render_html(_memo_met_nc("valide", []), _profiel())
    assert 'class="triage"' not in html


def test_font_stack_niet_html_escaped_in_css() -> None:
    """Regressie: autoescape mag de quotes in de font-stack niet kapotmaken (CSS-context)."""
    html = MemoRendererImpl().render_html(_memo(), _profiel())
    assert '"Segoe UI"' in html
    assert "&#34;Segoe UI" not in html


def test_render_pdf_schrijft_bestand(tmp_path: Path) -> None:
    renderer = MemoRendererImpl()
    html = renderer.render_html(_memo(), _profiel())
    uit = tmp_path / "memo.pdf"
    renderer.render_pdf(html, uit)
    assert uit.is_file()
    assert uit.stat().st_size > 1000  # niet-leeg PDF


@pytest.mark.parametrize("ontbreekt", ["wie", "waar", "uiterlijk"])
def test_lege_actie_velden_tonen_placeholder(ontbreekt: str) -> None:
    html = MemoRendererImpl().render_html(_memo(), _profiel())
    assert 'class="placeholder"' in html
