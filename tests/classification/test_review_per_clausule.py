"""De review kijkt per clausule, niet per document.

Dat is het hele punt. De classificatie oordeelt per document: 42 documenten die clausule 8.16
raken geven 42 oordelen over dezelfde eis. Een auditor stelt één vraag — *wordt deze eis
gehaald, gegeven al het bewijs dat we hebben?* — en dat is een vraag die je maar één keer stelt.

Het verschil is niet alleen het aantal. Uit één tool-ontwerpdocument volgt niet dat de
organisatie geen classificatieschema heeft; dat volgt hooguit uit álle documenten samen die
erover zouden moeten gaan. Zolang het oordeel per document valt, is "organisatiebreed gebroken"
een conclusie die het bewijs niet draagt — en dat gaf op 2026-08-24 71 major NC's op 79.

De review groepeert daarom eerst en oordeelt dan. Wat hij oplevert is een **advies met een
reden**, nooit een status: de auditor beslist.
"""

from __future__ import annotations

from typing import Any

from iso_audit.classification.review import groepeer_per_clausule


def _bev(clausule: str, norm: str, classificatie: str, doc: str, **kw: Any) -> dict[str, Any]:
    basis = {
        "clausule_id": clausule,
        "norm": norm,
        "classificatie": classificatie,
        "doc_id": doc,
        "document_naam": f"{doc}.docx",
        "beschrijving": f"Bevinding over {clausule}",
        "onderbouwing": f"Norm {norm} §{clausule}",
        "onbruikbaar": 0,
    }
    basis.update(kw)
    return basis


def test_bevindingen_op_een_clausule_komen_samen() -> None:
    groepen = groepeer_per_clausule(
        [
            _bev("8.16", "27001", "NC", "d1"),
            _bev("8.16", "27001", "OFI", "d2"),
            _bev("8.16", "27001", "positief", "d3"),
        ]
    )
    assert len(groepen) == 1
    groep = groepen[0]
    assert groep.clausule == "8.16"
    assert len(groep.bevindingen) == 3
    assert groep.documenten == 3


def test_dezelfde_clausule_in_twee_normen_blijft_gescheiden() -> None:
    """§7.5 betekent in 9001 iets anders dan in 27001; die mogen niet op één hoop.

    Zonder dit onderscheid zou de review bewijs over "Gedocumenteerde informatie" gebruiken om
    iets te zeggen over "Bescherming tegen fysieke en omgevingsbedreigingen".
    """
    groepen = groepeer_per_clausule(
        [_bev("7.5", "9001", "NC", "d1"), _bev("7.5", "27001", "positief", "d2")]
    )
    assert len(groepen) == 2
    assert {(g.clausule, g.norm) for g in groepen} == {("7.5", "9001"), ("7.5", "27001")}


def test_onbruikbare_bevindingen_tellen_niet_mee() -> None:
    """Een oordeel zonder beschrijving én onderbouwing draagt niets bij aan de vraag."""
    groepen = groepeer_per_clausule(
        [
            _bev("8.16", "27001", "NC", "d1"),
            _bev("8.16", "27001", "OFI", "d2", onbruikbaar=1, beschrijving="", onderbouwing=""),
        ]
    )
    assert len(groepen[0].bevindingen) == 1


def test_een_clausule_zonder_bruikbare_bevindingen_komt_niet_terug() -> None:
    groepen = groepeer_per_clausule(
        [_bev("8.16", "27001", "OFI", "d1", onbruikbaar=1, beschrijving="", onderbouwing="")]
    )
    assert groepen == []


def test_de_groep_kent_de_zwaarste_classificatie() -> None:
    """Waar de review op sorteert: een clausule met een NC vraagt eerder aandacht.

    Niet om te beslissen — dat blijft de auditor — maar om de volgorde te bepalen waarin de
    review de dure aanroepen doet, zodat een afgebroken run de belangrijkste al heeft gehad.
    """
    groepen = groepeer_per_clausule(
        [_bev("8.16", "27001", "positief", "d1"), _bev("8.16", "27001", "NC", "d2")]
    )
    assert groepen[0].zwaarste == "NC"


def test_groepen_staan_op_volgorde_van_gewicht() -> None:
    groepen = groepeer_per_clausule(
        [
            _bev("5.1", "27001", "positief", "d1"),
            _bev("8.16", "27001", "NC", "d2"),
            _bev("6.3", "27001", "OFI", "d3"),
        ]
    )
    assert [g.zwaarste for g in groepen] == ["NC", "OFI", "positief"]
