"""De autonome review is aan of uit te zetten.

Elke modus in dit tool moet te schakelen zijn — een stap die altijd draait en tokens kost is
geen keuze maar een verrassing op de rekening. De review draait over honderden bevindingen op een
zwaarder model en is daarmee de duurste stap van de pipeline.

Hij staat **uit** tenzij iemand hem aanzet. Dat is de kant die past bij de rest van deze repo:
geen impliciete defaults, en zeker niet voor iets dat geld kost en een oordeel voorbereidt.

De schakelaar volgt hetzelfde patroon als `--source` en `--mode`: een expliciete vlag met een
env-var-fallback die luid meldt dát hij wordt gebruikt.
"""

from __future__ import annotations

import pytest

from iso_audit.classification.review import ReviewInstelling, review_aan


def test_standaard_staat_de_review_uit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ISO_AUDIT_REVIEW", raising=False)
    assert review_aan(None) is False


@pytest.mark.parametrize("waarde", ["1", "true", "TRUE", "ja", "aan", "on", "yes"])
def test_env_var_zet_hem_aan(waarde: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ISO_AUDIT_REVIEW", waarde)
    assert review_aan(None) is True


@pytest.mark.parametrize("waarde", ["0", "false", "nee", "uit", "off", "no", ""])
def test_env_var_zet_hem_uit(waarde: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ISO_AUDIT_REVIEW", waarde)
    assert review_aan(None) is False


def test_de_vlag_wint_van_de_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Een expliciete keuze op de opdrachtregel overstemt een omgeving die iets anders wil.

    Andersom zou betekenen dat een cron-instelling een handmatige run stil overrulet, en dan
    weet degene die de run start niet wat er draait.
    """
    monkeypatch.setenv("ISO_AUDIT_REVIEW", "aan")
    assert review_aan(False) is False
    monkeypatch.setenv("ISO_AUDIT_REVIEW", "uit")
    assert review_aan(True) is True


def test_de_instelling_meldt_waar_de_keuze_vandaan_komt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Herkomst hoort in de trail: vlag, omgeving of standaard.

    Zelfde reden als bij de bron-configuratie: "waarom draaide deze stap wel/niet" moet
    achteraf te beantwoorden zijn zonder de startopdracht terug te zoeken.
    """
    monkeypatch.setenv("ISO_AUDIT_REVIEW", "aan")
    assert ReviewInstelling.bepaal(None).herkomst == "omgeving"
    assert ReviewInstelling.bepaal(True).herkomst == "vlag"
    monkeypatch.delenv("ISO_AUDIT_REVIEW", raising=False)
    assert ReviewInstelling.bepaal(None).herkomst == "standaard"


def test_uit_betekent_geen_enkele_modelaanroep() -> None:
    """De schakelaar moet vóór de aanroep zitten, niet erna.

    Een review die draait en zijn uitkomst weggooit, kost hetzelfde als een review die telt.
    """
    instelling = ReviewInstelling(aan=False, herkomst="standaard")
    assert instelling.mag_model_aanroepen() is False
