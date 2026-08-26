"""Tests voor `classifier` + `pattern_detection`."""

from __future__ import annotations

from iso_audit.memo.classifier import DefaultClassifier
from iso_audit.memo.models import Finding
from iso_audit.memo.pattern_detection import DefaultPatternDetector


def _f(fid: str, severity: str, clause: str = "10.2", promote: bool = False) -> Finding:
    return Finding(
        id=fid,
        severity=severity,  # type: ignore[arg-type]
        standard="iso-27001-2022",
        clause=clause,
        title=f"f{fid}",
        description="x",
        promote_to_improvement=promote,
    )


# --- classifier -------------------------------------------------------------


def test_ncs_alleen_nc_in_volgorde() -> None:
    fs = [_f("1", "OFI"), _f("2", "NC"), _f("3", "POSITIVE"), _f("4", "NC")]
    out = DefaultClassifier().ncs(fs)
    assert [f.id for f in out] == ["2", "4"]


# De OFI-selectie zat hier als clausule-clustering met drempel 10. Sinds 2026-08-26 bundelt
# `memo/groepering.py` op **thema**, want geen enkele clausule haalde die drempel terwijl de
# 53 OFI's zich over 16 thema's verdeelden. Eén regel, één plek: de tests staan nu in
# `tests/memo/test_verbeterpunten_thema.py`.


# --- pattern detection ------------------------------------------------------


def test_pattern_gemengde_clausule() -> None:
    fs = [_f("1", "POSITIVE", "10.2"), _f("2", "OFI", "10.2"), _f("3", "OFI", "10.2")]
    note = DefaultPatternDetector().pattern_note("10.2", fs)
    assert note is not None
    assert "1 positieve bevinding" in note
    assert "2 OFI's" in note


def test_pattern_alleen_positief_geen_note() -> None:
    fs = [_f("1", "POSITIVE", "10.2")]
    assert DefaultPatternDetector().pattern_note("10.2", fs) is None


def test_pattern_alleen_ofi_geen_note() -> None:
    fs = [_f("1", "OFI", "10.2")]
    assert DefaultPatternDetector().pattern_note("10.2", fs) is None
