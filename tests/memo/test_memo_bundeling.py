"""De memo bundelt NC's tot thema-blokken in plaats van één blok per bevinding.

De run van 2026-08-25 leverde 91 bevestigde NC's op. Eén blok per bevinding maakt daar 91
blokken van; het handgemaakte Q2-memo had er twee. Het verschil is niet dat er bewijs wegvalt
maar dat het gebundeld wordt: één gebrek dat zich in drie clausules laat zien, is één besluit
voor het management.
"""

from __future__ import annotations

from iso_audit.memo.models import Finding


def _nc(clausule: str, thema: str, kern: str = "") -> Finding:
    return Finding(
        id=f"nc-{clausule}",
        severity="NC",
        standard="iso-27001-2022",
        clause=clausule,
        title=f"§{clausule} — iets",
        description="beschrijving",
        deviation="afwijking",
        thema=thema,
        kern=kern,
        triage_status="valide",
    )


def test_drie_bevindingen_op_een_thema_geven_een_blok() -> None:
    from iso_audit.memo.groepering import groepeer_ncs

    ncs = [
        _nc("8.14", "Back-up & continuïteit", kern="Geen getest continuïteitsbeheer."),
        _nc("5.29", "Back-up & continuïteit"),
        _nc("5.30", "Back-up & continuïteit"),
    ]
    groepen = groepeer_ncs(ncs)
    assert len(groepen) == 1
    assert groepen[0].clausules == ["5.29", "5.30", "8.14"]
    assert groepen[0].kern.startswith("Geen getest")


def test_het_blok_houdt_elke_bron_zichtbaar() -> None:
    """Bundelen mag geen bewijs verstoppen; dat is wat de memo natrekbaar houdt."""
    from iso_audit.memo.groepering import groepeer_ncs

    groepen = groepeer_ncs([_nc("8.14", "Continuïteit"), _nc("5.29", "Continuïteit")])
    assert len(groepen[0].bevindingen) == 2
