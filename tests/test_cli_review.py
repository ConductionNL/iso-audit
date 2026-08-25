"""De review-schakelaar op de opdrachtregel heeft drie standen."""

from __future__ import annotations

import pytest

from iso_audit.cli import _build_parser


def _parse(*args: str) -> object:
    return _build_parser().parse_args(
        ["pipeline", "--source", "drive", "--mode", "autonoom", *args]
    )


def test_zonder_vlag_beslist_de_omgeving() -> None:
    """`None` betekent: niets gezegd. Een `store_true` kan dat niet uitdrukken.

    Zonder dit onderscheid zou een ontbrekende vlag hetzelfde zijn als `--geen-review`, en dan
    kan `ISO_AUDIT_REVIEW` nooit iets aanzetten.
    """
    assert _parse().review is None


def test_review_zet_hem_aan() -> None:
    assert _parse("--review").review is True


def test_geen_review_zet_hem_uit() -> None:
    assert _parse("--geen-review").review is False


def test_de_twee_vlaggen_sluiten_elkaar_uit() -> None:
    with pytest.raises(SystemExit):
        _parse("--review", "--geen-review")


def test_de_steekproef_is_standaard_uit() -> None:
    assert _parse().review_steekproef == 0
    assert _parse("--review-steekproef", "10").review_steekproef == 10
