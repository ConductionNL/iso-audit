"""Beide normen is de standaard; bij één norm is dat 27001.

Expliciete keuze van de auditor (2026-08-24): "je moet testen op 9001 & 27001 — als je voor 1
kiest, dan altijd 27001". De reden is dat ISO 27001 de informatiebeveiligingsaudit draagt en 93
clausules kent tegen 28 voor 9001. Een audit die maar één norm doet en 9001 kiest, laat het
grootste deel van de beheersmaatregelen liggen.

Deze test legt de voorkeur vast in code in plaats van in een gewoonte. Wat hij **niet** doet, is
een normkeuze afdwingen: een auditor die bewust alleen 9001 wil toetsen kan dat, en de run meldt
dan expliciet dat 27001 niet is getoetst.
"""

from __future__ import annotations

import pytest

from iso_audit.api.registry import STANDAARD_NORMEN, VOORKEURSNORM, run_code


def test_beide_normen_is_de_standaard() -> None:
    assert sorted(STANDAARD_NORMEN) == ["27001", "9001"]
    assert run_code(list(STANDAARD_NORMEN)) == "beide"


def test_bij_een_norm_is_de_voorkeur_27001() -> None:
    assert VOORKEURSNORM == "27001"


def test_een_expliciete_enkele_norm_blijft_mogelijk() -> None:
    """De voorkeur is een standaard, geen verbod — de auditor bepaalt de scope."""
    assert run_code(["9001"]) == "9001"
    assert run_code(["27001"]) == "27001"


@pytest.mark.parametrize("normen", [["9001", "27001"], ["27001", "9001"]])
def test_volgorde_maakt_niet_uit(normen: list[str]) -> None:
    assert run_code(normen) == "beide"
