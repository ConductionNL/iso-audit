"""Tests voor `iso_audit.data.normteksten` — lookup-coverage + schema-consistency."""

from __future__ import annotations

import pytest

from iso_audit.data.normteksten import (
    NORMTEKSTEN_9001,
    NORMTEKSTEN_27001,
    available,
    lookup,
)

REQUIRED_KEYS = {"normtekst", "interpretatie", "bewijslast"}

# Clausules die bij audit-rapport-onderbouwing essentieel zijn (smoketest).
EXPECTED_9001 = {"4.1", "5.1", "6.1", "9.1", "10.1", "10.2", "10.3"}
# 27001 §10.2 (Non-conformiteit en corrigerende maatregel) ontbreekt in de
# bron-dict — niet opgenomen in EXPECTED_27001. Aanvullen is een data-gap-fix,
# eigen change-proposal in een vervolg-PR.
EXPECTED_27001 = {"A.5.11", "A.5.18", "A.5.27", "A.6.5", "A.8.15", "A.8.16"}
"""Bijlage A-maatregelen dragen sinds 2026-08-28 de `A.`-prefix, zoals de norm zelf.

Zonder die prefix botsten ze met de managementclausules: §5.1 is "Leiderschap en betrokkenheid",
A.5.1 is "Beleid voor informatiebeveiliging". Tot die datum bevatte de norm-DB alleen Bijlage A,
waardoor hoofdstuk 4 t/m 10 nooit werd getoetst."""

EXPECTED_27001_MANAGEMENT = {"4.1", "4.3", "5.1", "6.1.3", "7.5", "9.2", "9.3", "10.2"}
"""Een greep uit de managementclausules; deze moeten er nu óók zijn."""


def test_normteksten_9001_non_empty() -> None:
    assert NORMTEKSTEN_9001, "9001-dict is leeg"
    assert len(NORMTEKSTEN_9001) >= 25, f"9001 heeft te weinig clausules: {len(NORMTEKSTEN_9001)}"


def test_normteksten_27001_non_empty() -> None:
    assert NORMTEKSTEN_27001, "27001-dict is leeg"
    # Annex A heeft 93 controls — totaal moet die orde benaderen.
    assert len(NORMTEKSTEN_27001) >= 80, (
        f"27001 heeft te weinig clausules: {len(NORMTEKSTEN_27001)}"
    )


@pytest.mark.parametrize("clausule", sorted(EXPECTED_9001))
def test_9001_required_clausules_present(clausule: str) -> None:
    entry = lookup("9001", clausule)
    assert entry is not None, f"clausule {clausule!r} ontbreekt in 9001"
    missing = REQUIRED_KEYS - set(entry)
    assert not missing, f"clausule {clausule}: ontbrekende keys {missing}"


@pytest.mark.parametrize("clausule", sorted(EXPECTED_27001))
def test_27001_required_clausules_present(clausule: str) -> None:
    entry = lookup("27001", clausule)
    assert entry is not None, f"clausule {clausule!r} ontbreekt in 27001"
    missing = REQUIRED_KEYS - set(entry)
    assert not missing, f"clausule {clausule}: ontbrekende keys {missing}"


def test_schema_consistency_9001() -> None:
    """Alle 9001-entries moeten verplichte keys hebben met niet-lege content."""
    issues: list[str] = []
    for cl, entry in NORMTEKSTEN_9001.items():
        for key in REQUIRED_KEYS:
            if key not in entry:
                issues.append(f"9001:{cl} mist {key}")
            elif not entry[key]:
                issues.append(f"9001:{cl}.{key} is leeg")
    assert not issues, "schema-inconsistenties:\n" + "\n".join(issues)


def test_schema_consistency_27001() -> None:
    """Alle 27001-entries moeten verplichte keys hebben met niet-lege content."""
    issues: list[str] = []
    for cl, entry in NORMTEKSTEN_27001.items():
        for key in REQUIRED_KEYS:
            if key not in entry:
                issues.append(f"27001:{cl} mist {key}")
            elif not entry[key]:
                issues.append(f"27001:{cl}.{key} is leeg")
    assert not issues, "schema-inconsistenties:\n" + "\n".join(issues)


def test_lookup_unknown_clausule() -> None:
    """Onbekende clausule → `None` (geen exception)."""
    assert lookup("9001", "999.99") is None
    assert lookup("27001", "abc") is None


def test_lookup_invalid_norm() -> None:
    """Onbekende norm → `ValueError` (programmeerfout)."""
    with pytest.raises(ValueError, match="onbekende norm"):
        lookup("ISO", "10.2")


def test_available_9001() -> None:
    keys = available("9001")
    assert keys == sorted(keys), "available moet gesorteerd zijn"
    assert "10.2" in keys


def test_available_27001() -> None:
    keys = available("27001")
    assert "A.6.5" in keys
    assert "A.8.16" in keys
    assert "9.2" in keys, "managementclausule 9.2 Interne audit ontbreekt"


def test_available_invalid_norm() -> None:
    with pytest.raises(ValueError, match="onbekende norm"):
        available("foo")


@pytest.mark.parametrize("clausule", sorted(EXPECTED_27001_MANAGEMENT))
def test_27001_managementclausules_present(clausule: str) -> None:
    """Hoofdstuk 4 t/m 10 is de helft van de certificeringseis en ontbrak volledig."""
    assert clausule in NORMTEKSTEN_27001, f"managementclausule {clausule!r} ontbreekt in 27001"
