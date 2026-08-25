"""De review-prompt adviseert en beslist niet.

Dit is de enige prompt in dit tool die naar bestaande oordelen kijkt in plaats van naar een
document. Zijn grens is daarom een andere: hij mag geen status zetten en niets afsluiten. Zelfde
regel als bij `assistent/clausule.py`, waar `VERBODEN_VELDEN` dat met een test afdwingt — een
agent die een status zet maakt van beoordelen bevestigen, en de auditor-spiegel is de capability
die dit tool draagt.
"""

from __future__ import annotations

from pathlib import Path

PROMPT = Path("src/iso_audit/classification/prompts/v2-review.md")


def _tekst() -> str:
    return " ".join(PROMPT.read_text(encoding="utf-8").lower().split())


def test_de_prompt_bestaat() -> None:
    assert PROMPT.is_file()


def test_hij_oordeelt_over_de_clausule_en_niet_over_een_document() -> None:
    """Dat is het hele punt: 42 documenten op 8.16 zijn één vraag, geen 42."""
    tekst = _tekst()
    assert "één clausule" in tekst or "een clausule" in tekst
    assert "als geheel" in tekst


def test_hij_stelt_de_vier_vragen() -> None:
    tekst = _tekst()
    for kern in ("inhoud", "passen", "verdedigbaar", "hetzelfde gebrek"):
        assert kern in tekst, f"deelvraag ontbreekt: {kern}"


def test_hij_zet_geen_status() -> None:
    """Advies, geen besluit — en dat moet in de prompt staan, niet alleen in de code."""
    tekst = _tekst()
    assert "de auditor beslist" in tekst
    assert "voorstel" in tekst
    assert "geen besluit" in tekst


def test_een_advies_moet_naar_documenten_verwijzen() -> None:
    """Zonder verwijzing is het advies niet na te trekken en dus waardeloos.

    Zelfde regel als bij de Bronbevrager: een bewering zonder bron telt niet als bewijs.
    """
    tekst = _tekst()
    assert "documentnamen" in tekst
    assert "zonder verwijzing" in tekst


def test_de_vier_adviezen_staan_erin() -> None:
    tekst = _tekst()
    for advies in ("bevestigen", "verlagen", "samenvoegen", "onvoldoende_bewijs"):
        assert advies in tekst, f"advies ontbreekt: {advies}"


def test_er_is_een_kernzin_voor_de_memo() -> None:
    """De memo heeft per NC één synthese-alinea nodig; die begint hier."""
    tekst = _tekst()
    assert "kern" in tekst
    assert "managementmemo" in tekst


def test_de_prompt_vraagt_om_acties() -> None:
    """Zonder actietabel is de memo een constatering zonder opdracht."""
    tekst = _tekst()
    assert "acties" in tekst
    for veld in ("wat", "wie", "waar", "uiterlijk"):
        assert veld in tekst, f"actieveld ontbreekt: {veld}"


def test_wie_moet_een_rol_zijn() -> None:
    """Een agent die een persoon aanwijst, neemt een besluit van de organisatie."""
    tekst = _tekst()
    assert "een **rol**" in tekst or "een rol" in tekst
    assert "nooit een persoon" in tekst


def test_een_leeg_veld_is_beter_dan_een_verzonnen_eigenaar() -> None:
    tekst = _tekst()
    assert "verzonnen eigenaar" in tekst
