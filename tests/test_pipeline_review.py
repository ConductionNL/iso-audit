"""De review draait alleen als de modus aan staat, en breekt de run nooit."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from iso_audit.pipeline import _autonome_review


def _bevindingen() -> list[dict[str, Any]]:
    return [
        {
            "clausule_id": "8.16",
            "norm": "27001",
            "classificatie": "NC",
            "doc_id": "d1",
            "document_naam": "Beleid.docx",
            "beschrijving": "Iets",
            "onderbouwing": "§8.16",
            "onbruikbaar": 0,
        }
    ]


def test_uit_roept_niets_aan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ISO_AUDIT_REVIEW", raising=False)
    with patch("iso_audit.classification.review.beoordeel") as beoordeel:
        _autonome_review(_bevindingen(), review=None, review_steekproef=0)
    beoordeel.assert_not_called()


def test_de_vlag_zet_hem_aan_ondanks_de_omgeving(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ISO_AUDIT_REVIEW", "uit")
    with patch("iso_audit.classification.review.beoordeel", return_value=[]) as beoordeel:
        _autonome_review(_bevindingen(), review=True, review_steekproef=3)
    beoordeel.assert_called_once()
    assert beoordeel.call_args.kwargs["steekproef"] == 3


def test_een_mislukte_review_breekt_de_run_niet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Best-effort, zoals de andere niet-essentiële stappen.

    Een run die 709 documenten heeft gelezen en geclassificeerd, mag niet ongeldig worden
    doordat een tweede zeef struikelt.
    """
    monkeypatch.setenv("ISO_AUDIT_REVIEW", "aan")
    with patch("iso_audit.classification.review.beoordeel", side_effect=RuntimeError("stuk")):
        _autonome_review(_bevindingen(), review=None, review_steekproef=0)  # mag niet werpen
