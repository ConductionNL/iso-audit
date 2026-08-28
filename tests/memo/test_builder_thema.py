"""De memo bouwt één NC-blok per thema, niet per bevinding.

Gemeten op de echte werkset van 2026-08-26: 47 bevestigde NC's gaven 47 blokken en **35
pagina's**. Het handgemaakte Q2-memo had er twee. Groeperen op thema brengt die 47 terug naar 24
blokken — nog niet genoeg voor drie A4, maar het is het verschil tussen "de auditor moet
cureren" en "dit is onbruikbaar".

Wat er niet verandert: elke bevinding blijft zichtbaar onder zijn blok, met zijn eigen bron. Een
memo die niet terug te voeren is op documenten, is een mening.
"""

from __future__ import annotations

from pathlib import Path

from iso_audit.memo.models import ActionRow, BronRef, Finding


def _nc(clausule: str, thema: str, kern: str = "", bron: str = "B.docx") -> Finding:
    return Finding(
        id=f"nc-{clausule}",
        severity="NC",
        standard="iso-27001-2022",
        clause=clausule,
        title=f"§{clausule} — iets",
        description="beschrijving",
        deviation=f"afwijking op {clausule}",
        thema=thema,
        kern=kern,
        triage_status="valide",
        bronnen=[
            BronRef(herkomst="Drive", doc_id="d1", doc_naam=bron, beschrijving="wat erin staat")
        ],
        actions=[ActionRow(wat=f"actie voor {clausule}")],
    )


def _bouw(findings: list[Finding]) -> list:
    import yaml

    from iso_audit.memo.builder import build_memo
    from iso_audit.memo.models import MemoInput
    from iso_audit.memo.norm_lookup import laad_norm_db
    from iso_audit.memo.theme.profile import laad_profiel

    profiel = laad_profiel("examples/auditmemo/conduction.profile.yaml")
    norm_db = laad_norm_db("examples/norms")
    ruw = Path("examples/auditmemo/memo-input.yaml").read_text(encoding="utf-8")
    memo_input = MemoInput(**yaml.safe_load(ruw))
    memo = build_memo(
        findings=findings,
        historical_ncs=[],
        profile=profiel,
        norm_db=norm_db,
        memo_input=memo_input,
    )
    return memo.nc_blocks


def test_drie_ncs_op_een_thema_geven_een_blok() -> None:
    blokken = _bouw(
        [
            _nc("A.8.14", "Back-up & continuïteit", kern="Geen getest continuïteitsbeheer."),
            _nc("A.5.29", "Back-up & continuïteit"),
            _nc("A.5.30", "Back-up & continuïteit"),
        ]
    )
    assert len(blokken) == 1
    assert blokken[0].kern.startswith("Geen getest")


def test_het_blok_citeert_alle_clausules() -> None:
    """De normregel onder een NC-blok somt ze op: §A.8.14 / §A.5.29 / §5.30."""
    blokken = _bouw([_nc("A.8.14", "Continuïteit"), _nc("A.5.29", "Continuïteit")])
    assert sorted(c.clause for c in blokken[0].citations) == ["A.5.29", "A.8.14"]


def test_elke_bron_blijft_zichtbaar() -> None:
    """Bundelen mag geen bewijs verstoppen."""
    blokken = _bouw(
        [
            _nc("A.8.14", "Continuïteit", bron="Plan.docx"),
            _nc("A.5.29", "Continuïteit", bron="Test.md"),
        ]
    )
    namen = {b.doc_naam for b in blokken[0].bronnen}
    assert namen == {"Plan.docx", "Test.md"}


def test_de_acties_van_alle_bevindingen_komen_samen() -> None:
    blokken = _bouw([_nc("A.8.14", "Continuïteit"), _nc("A.5.29", "Continuïteit")])
    assert len(blokken[0].actions) == 2


def test_verschillende_themas_blijven_aparte_blokken() -> None:
    blokken = _bouw([_nc("A.8.14", "Continuïteit"), _nc("A.5.12", "Informatieclassificatie")])
    assert len(blokken) == 2


def test_met_kern_verhuist_het_detail_naar_de_bijlage() -> None:
    """Is er een synthese, dan is die de blok-tekst.

    Zonder deze regel groeit een thema-blok mee met zijn omvang: zeven bevindingen betekent
    zeven volledige afwijkingsteksten onder elkaar, en dan levert bundelen niets op. Het
    handgemaakte Q2-memo doet het andersom — één synthese in de memo, de onderbouwing per
    clausule in het detailrapport, waar ze toch al staat.
    """
    blokken = _bouw(
        [
            _nc("A.8.14", "Continuïteit", kern="Continuïteit is niet aantoonbaar getest."),
            _nc("A.5.29", "Continuïteit"),
        ]
    )
    assert blokken[0].kern == "Continuïteit is niet aantoonbaar getest."
    assert blokken[0].deviation == ""


def test_zonder_kern_blijft_de_afwijking_staan() -> None:
    """Geen synthese betekent niet: geen inhoud. Dan is de afwijking alles wat we hebben."""
    blokken = _bouw([_nc("A.8.14", "Continuïteit"), _nc("A.5.29", "Continuïteit")])
    assert "afwijking op A.8.14" in blokken[0].deviation
    assert "afwijking op A.5.29" in blokken[0].deviation


def test_het_bewijs_blijft_ook_met_kern_zichtbaar() -> None:
    """Het detail verhuist, de bronvermelding niet — anders is de memo niet na te trekken."""
    blokken = _bouw(
        [
            _nc("A.8.14", "Continuïteit", kern="Niet getest.", bron="Plan.docx"),
            _nc("A.5.29", "Continuïteit", bron="Test.md"),
        ]
    )
    assert {b.doc_naam for b in blokken[0].bronnen} == {"Plan.docx", "Test.md"}


def test_met_kern_houdt_het_blok_de_bronnaam_maar_niet_de_omschrijving() -> None:
    """De bron-omschrijvingen waren 45% van de memo-tekst (4.993 van 11.028 tekens, 2026-08-26).

    Wat blijft is wat de memo natrekbaar maakt: welk document. Wat verhuist is wat het
    detailrapport toch al per bevinding uitschrijft. Zonder kern blijft alles staan, want dan is
    er geen bijlage-synthese om naar te verwijzen.
    """
    met = _bouw([_nc("A.8.14", "Continuïteit", kern="Niet getest."), _nc("A.5.29", "Continuïteit")])
    assert [b.doc_naam for b in met[0].bronnen] == ["B.docx"]
    assert all(not b.beschrijving for b in met[0].bronnen)


def test_zonder_kern_blijft_de_bronomschrijving_staan() -> None:
    zonder = _bouw([_nc("A.8.14", "Continuïteit"), _nc("A.5.29", "Continuïteit")])
    assert any(b.beschrijving for b in zonder[0].bronnen)
