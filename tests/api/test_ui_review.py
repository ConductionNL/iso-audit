"""De review-schakelaar staat in het scherm en gaat mee met de run.

Een modus die alleen via een env-var of de opdrachtregel aan te zetten is, is voor de auditor
niet aan te zetten — en die is degene die beslist of het de tokens waard is.
"""

from __future__ import annotations

from pathlib import Path

UI = Path("src/iso_audit/api/ui.html")


def _html() -> str:
    return UI.read_text(encoding="utf-8")


def test_er_is_een_vinkje_voor_de_review() -> None:
    assert 'id="review-mode"' in _html()


def test_er_is_een_veld_voor_de_steekproef() -> None:
    """67 clausules op een zwaar model is een uitgave; de auditor moet klein kunnen beginnen."""
    assert 'id="review-steekproef"' in _html()


def test_de_run_stuurt_beide_mee() -> None:
    html = _html()
    assert "review:document.getElementById" in html
    assert "review_steekproef:parseInt" in html


def test_het_vinkje_legt_uit_dat_het_geld_kost() -> None:
    """Een schakelaar zonder prijskaartje wordt aangezet zonder afweging."""
    html = _html()
    kop = html[html.index('id="review-mode"') - 300 : html.index('id="review-mode"')]
    assert "token" in kop.lower()
