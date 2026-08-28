"""Tests voor `iso_audit.classification.clause_mapping`."""

from __future__ import annotations

from typing import Any

import pytest

from iso_audit.classification.clause_mapping import (
    filter_clause_map,
    koppel_documenten,
    laad_clause_map,
    ontbrekende_dekking,
)


@pytest.fixture
def map_9001() -> dict[str, Any]:
    return laad_clause_map("9001")


@pytest.fixture
def map_27001() -> dict[str, Any]:
    return laad_clause_map("27001")


@pytest.fixture
def map_beide() -> dict[str, Any]:
    return laad_clause_map("beide")


def test_laad_9001(map_9001: dict[str, Any]) -> None:
    assert map_9001["norm"].startswith("ISO 9001")
    assert "4.1" in map_9001["clausules"]
    assert "10.2" in map_9001["clausules"]


def test_laad_27001(map_27001: dict[str, Any]) -> None:
    assert "27001" in map_27001["norm"]
    assert "6.5" in map_27001["clausules"]
    assert "8.16" in map_27001["clausules"]


def test_laad_beide(map_beide: dict[str, Any]) -> None:
    """`beide` voegt 9001+27001 samen."""
    assert "9001" in map_beide["norm"]
    assert "27001" in map_beide["norm"]
    # Beide chapters moeten aanwezig zijn.
    assert "4.1" in map_beide["clausules"]
    assert "6.5" in map_beide["clausules"]


def test_laad_onbekende_norm() -> None:
    with pytest.raises(ValueError, match="onbekende norm"):
        laad_clause_map("ISO 31000")


def test_filter_clause_map_hoofdstuk(map_9001: dict[str, Any]) -> None:
    gefilterd = filter_clause_map(map_9001, "4")
    keys = list(gefilterd["clausules"])
    assert all(k.startswith("4.") for k in keys), keys
    assert len(keys) >= 1


def test_filter_clause_map_geen_match(map_9001: dict[str, Any]) -> None:
    """`EigenFoutError` en geen `ValueError`: deze tekst hoort ongewijzigd bij de auditor aan
    te komen. Als gewone fout werd hij door `config.verbinding.normaliseer` vervangen door "De
    verbinding kon niet worden gelegd" — zie `tests/config/test_eigen_fout.py`."""
    from iso_audit.config.verbinding import EigenFoutError

    with pytest.raises(EigenFoutError, match="Geen clausules gevonden"):
        filter_clause_map(map_9001, "99")


def test_filter_clause_map_exact_match(map_9001: dict[str, Any]) -> None:
    """Hoofdstuk == clausule-key wordt ook geaccepteerd."""
    if "4" in map_9001["clausules"]:
        # If exact "4" key bestaat (zelden); skippable.
        gefilterd = filter_clause_map(map_9001, "4")
        assert "4" in gefilterd["clausules"] or any(
            k.startswith("4.") for k in gefilterd["clausules"]
        )


def test_koppel_documenten_match(map_beide: dict[str, Any]) -> None:
    """Een memo met procedurele zoektermen krijgt clausule-koppelingen."""
    docs = [
        {
            "naam": "Memo offboarding Sarai",
            "tekst": "procedure beëindiging dienstverband",
        }
    ]
    gekoppeld, niet = koppel_documenten(docs, map_beide)
    assert len(gekoppeld) == 1
    assert len(niet) == 0
    assert "5.11" in gekoppeld[0]["clausules"] or "6.5" in gekoppeld[0]["clausules"]


def test_koppel_documenten_geen_match(map_beide: dict[str, Any]) -> None:
    docs = [{"naam": "Vakantie-foto", "tekst": "strandvakantie 2024"}]
    gekoppeld, niet = koppel_documenten(docs, map_beide)
    assert len(gekoppeld) == 0
    assert len(niet) == 1
    assert niet[0]["clausules"] == []


def test_koppel_documenten_lege_input(map_beide: dict[str, Any]) -> None:
    gekoppeld, niet = koppel_documenten([], map_beide)
    assert gekoppeld == []
    assert niet == []


def test_ontbrekende_dekking_alle_gedekt(map_9001: dict[str, Any]) -> None:
    """Als alle clausules gedekt zijn, geen ontbrekende rijen."""
    gekoppeld = [
        {"clausules": list(map_9001["clausules"])},
    ]
    miro: list[dict[str, Any]] = []
    onb = ontbrekende_dekking(gekoppeld, miro, map_9001)
    assert onb == []


def test_ontbrekende_dekking_niets_gedekt(map_9001: dict[str, Any]) -> None:
    onb = ontbrekende_dekking([], [], map_9001)
    assert len(onb) == len(map_9001["clausules"])
    assert all("clausule" in row for row in onb)


def test_ontbrekende_dekking_miro_telt(map_9001: dict[str, Any]) -> None:
    """Miro-notities met `clausule` veld tellen mee voor dekking."""
    miro = [{"clausule": k} for k in list(map_9001["clausules"])[:3]]
    onb = ontbrekende_dekking([], miro, map_9001)
    gedekte_set = {row["clausule"] for row in onb}
    # De eerste 3 zijn nu wél gedekt door miro → niet in onb.
    for k in list(map_9001["clausules"])[:3]:
        assert k not in gedekte_set
