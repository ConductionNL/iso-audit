"""NC's groeperen tot thema-blokken, zoals het handgemaakte memo.

Het Q2-memo had **twee** genummerde NC's, elk met drie onderliggende bevindingen op drie
clausules: "NC 1 — Bedrijfscontinuïteit & redundantie" met §8.14, §5.29 en §5.30. De run van
2026-08-25 leverde 91 losse NC's op. Eenennegentig blokken op drie A4 is geen memo.

Groeperen op **thema** en niet op clausule: het Q2-memo bundelt juist over clausules heen, want
dat is waar één gebrek zich in meerdere eisen laat zien. Het thema staat al op elke bevinding
(`bepaal_thema`), en de review levert per clausule de kernzin die het blok zijn synthese geeft.

Wat hier níet gebeurt: bevindingen weggooien of samenvoegen tot één tekst. Elke bevinding blijft
zichtbaar onder zijn blok, met zijn eigen bron — dat is wat de memo natrekbaar houdt.
"""

from __future__ import annotations

from iso_audit.memo.groepering import groepeer_ncs
from iso_audit.memo.models import Finding


def _nc(clausule: str, thema: str, kern: str = "", standard: str = "iso-27001-2022") -> Finding:
    return Finding(
        id=f"nc-{clausule}",
        severity="NC",
        standard=standard,
        clause=clausule,
        title=f"§{clausule}",
        description="x",
        thema=thema,
        kern=kern,
        triage_status="valide",
    )


def test_bevindingen_met_hetzelfde_thema_komen_in_een_blok() -> None:
    groepen = groepeer_ncs(
        [
            _nc("8.14", "Back-up & continuïteit"),
            _nc("5.29", "Back-up & continuïteit"),
            _nc("5.30", "Back-up & continuïteit"),
        ]
    )
    assert len(groepen) == 1
    assert sorted(f.clause for f in groepen[0].bevindingen) == ["5.29", "5.30", "8.14"]


def test_het_blok_noemt_alle_clausules() -> None:
    """De normregel onder een NC-blok somt de clausules op: §8.14 / §5.29 / §5.30."""
    groepen = groepeer_ncs([_nc("8.14", "Continuïteit"), _nc("5.29", "Continuïteit")])
    assert groepen[0].clausules == ["5.29", "8.14"]


def test_verschillende_themas_blijven_apart() -> None:
    groepen = groepeer_ncs([_nc("8.14", "Continuïteit"), _nc("5.12", "Informatieclassificatie")])
    assert len(groepen) == 2


def test_het_grootste_thema_staat_voorop() -> None:
    """Waar het meeste bewijs ligt, hoort de eerste NC te staan."""
    groepen = groepeer_ncs(
        [_nc("5.12", "Klein"), _nc("8.14", "Groot"), _nc("5.29", "Groot"), _nc("5.30", "Groot")]
    )
    assert groepen[0].thema == "Groot"


def test_de_kernzin_van_het_blok_komt_uit_de_bevindingen() -> None:
    """Eén synthese per blok; de eerste die er een heeft, wint."""
    groepen = groepeer_ncs(
        [_nc("8.14", "Continuïteit"), _nc("5.29", "Continuïteit", kern="Eén hoofdgebrek.")]
    )
    assert groepen[0].kern == "Eén hoofdgebrek."


def test_zonder_kernzin_blijft_het_blok_leeg_op_dat_punt() -> None:
    groepen = groepeer_ncs([_nc("8.14", "Continuïteit")])
    assert groepen[0].kern == ""


def test_overig_wordt_niet_een_verzamelblok() -> None:
    """ "Overig" is geen thema maar het ontbreken ervan.

    Op 2026-08-24 viel 25% van de bevindingen in "Overig". Die als één NC-blok presenteren zou
    suggereren dat ze één gebrek delen, en dat is precies wat ze níet doen.
    """
    groepen = groepeer_ncs([_nc("8.14", "Overig"), _nc("5.12", "Overig")])
    assert len(groepen) == 2
    assert all(len(g.bevindingen) == 1 for g in groepen)


def test_alleen_valide_bevindingen_tellen() -> None:
    """De memo bevat wat de auditor heeft bevestigd; de rest is nog in behandeling."""
    open_nc = _nc("5.12", "Continuïteit")
    open_nc.triage_status = "open"
    groepen = groepeer_ncs([_nc("8.14", "Continuïteit"), open_nc])
    assert [f.clause for f in groepen[0].bevindingen] == ["8.14"]
