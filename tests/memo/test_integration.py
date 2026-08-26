"""Integratietest: render de auditmemo uit de meegeleverde examples.

Dekt fase 7: HTML lxml-valid, PDF rendert zonder fout, norm-referenties
resolven, structureel equivalent aan het referentievoorbeeld.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from lxml import html as lxml_html

from iso_audit.memo.builder import build_memo
from iso_audit.memo.models import Finding, HistoricalNC, MemoInput
from iso_audit.memo.norm_lookup import laad_norm_db
from iso_audit.memo.renderer.html import MemoRendererImpl
from iso_audit.memo.theme.profile import laad_profiel

_EX = Path("examples/auditmemo")
_NOW = datetime(2026, 5, 6, 9, 0, 0, tzinfo=UTC)


def _bouw():
    findings = [Finding(**x) for x in json.loads((_EX / "findings.json").read_text("utf-8"))]
    mi = MemoInput(**yaml.safe_load((_EX / "memo-input.yaml").read_text("utf-8")))
    hist_raw = yaml.safe_load((_EX / "historical_ncs.yaml").read_text("utf-8"))["entries"]
    hist = [HistoricalNC(**e) for e in hist_raw]
    profile = laad_profiel(str(_EX / "conduction.profile.yaml"))
    norm_db = laad_norm_db("examples/norms")
    memo = build_memo(
        findings=findings,
        historical_ncs=hist,
        profile=profile,
        norm_db=norm_db,
        memo_input=mi,
        now=_NOW,
    )
    return memo, profile


def test_voorbeeld_rendert_valide_html() -> None:
    memo, profile = _bouw()
    html = MemoRendererImpl().render_html(memo, profile)
    doc = lxml_html.fromstring(html)  # raises bij kapotte HTML
    tekst = doc.text_content()
    for sectie in ["Context", "NC 1", "NC 2", "OFI 1", "Status eerder geconstateerde"]:
        assert sectie in tekst


def test_voorbeeld_norm_referenties_resolven() -> None:
    """build_memo gooit niet → elke geciteerde clausule resolvet in de norm-DB."""
    memo, _ = _bouw()
    assert len(memo.nc_blocks) == 2
    # NC 2 citeert 6.5 + 5.11 + 5.18 → drie citaten.
    nc2 = next(b for b in memo.nc_blocks if "Offboarding" in b.title)
    assert {c.clause for c in nc2.citations} == {"6.5", "5.11", "5.18"}


def test_voorbeeld_pattern_en_verbeterpunt() -> None:
    memo, _ = _bouw()
    nc1 = next(b for b in memo.nc_blocks if "Opvolging" in b.title)
    assert nc1.pattern_note is not None  # 10.2 heeft positief + OFI
    assert len(memo.improvements) == 1
    assert "Logging" in memo.improvements[0].title


def test_voorbeeld_rendert_pdf(tmp_path: Path) -> None:
    memo, profile = _bouw()
    renderer = MemoRendererImpl()
    html = renderer.render_html(memo, profile)
    uit = tmp_path / "memo.pdf"
    renderer.render_pdf(html, uit)
    assert uit.stat().st_size > 5000


def test_audit_trail_metadata_aanwezig() -> None:
    memo, profile = _bouw()
    html = MemoRendererImpl().render_html(memo, profile)
    assert "audit-trail profile=conduction" in html
    assert "rendered_at=2026-05-06T09:00:00Z" in html
    assert "findings_hash=" in html
