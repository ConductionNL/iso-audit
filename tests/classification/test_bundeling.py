"""Eén bevinding per afwijking, niet per raakvlak.

Op de run van 2026-08-31 leverde "Memo NC-2025 Onvolledige evaluatie Q3/Q4" tien NC's op: één
afwijking die tien clausules raakte. Een externe auditor telde er nul. Deze tests leggen vast
wat er wel en niet mag samensmelten — bundelen dat te ver gaat, verbergt afwijkingen, en dat is
erger dan te veel tellen.
"""

from __future__ import annotations

from iso_audit.classification.bundeling import bundel
from iso_audit.memo.models import BronRef, Finding


def _f(
    fid: str,
    clause: str,
    *,
    doc: str = "d1",
    doc_naam: str = "Memo NC-2025",
    thema: str | None = "Rollen & verantwoordelijkheden",
    severity: str = "NC",
    standard: str = "iso-27001-2022",
    beschrijving: str = "",
) -> Finding:
    return Finding(
        id=fid,
        severity=severity,  # type: ignore[arg-type]
        standard=standard,
        clause=clause,
        title=f"§{clause}",
        description=beschrijving or f"iets over {clause}",
        thema=thema,
        bronnen=[BronRef(herkomst="Drive", doc_id=doc, doc_naam=doc_naam)],
    )


def test_een_afwijking_over_tien_clausules_wordt_een_bevinding() -> None:
    findings = [_f(str(i), c) for i, c in enumerate(["5.3", "7.4", "7.5", "9.2", "A.5.35"])]
    uit = bundel(findings)
    assert len(uit) == 1
    assert uit[0].clause == "5.3"
    assert uit[0].extra_clauses == ["7.4", "7.5", "9.2", "A.5.35"]


def test_de_raakvlakken_verdwijnen_niet() -> None:
    """`extra_clauses` gaat mee in de citaten van de memo; wegbundelen zou bewijs kwijtmaken."""
    uit = bundel([_f("1", "5.3"), _f("2", "9.2")])
    assert set([uit[0].clause, *uit[0].extra_clauses]) == {"5.3", "9.2"}
    assert uit[0].gebundeld_uit == ["1", "2"]


def test_twee_themas_in_een_document_blijven_twee_afwijkingen() -> None:
    """Een document met twee ongerelateerde problemen is niet één afwijking."""
    uit = bundel(
        [
            _f("1", "5.3", thema="Rollen & verantwoordelijkheden"),
            _f("2", "A.8.13", thema="Back-up & continuïteit"),
        ]
    )
    assert len(uit) == 2


def test_verschillende_documenten_bundelen_niet() -> None:
    """Bundelen over documenten heen zou de bron van een afwijking onzichtbaar maken."""
    uit = bundel([_f("1", "5.3", doc="d1"), _f("2", "5.3", doc="d2")])
    assert len(uit) == 2


def test_nc_en_ofi_bundelen_niet() -> None:
    """Een NC en een OFI samentrekken zou de klasse van een afwijking laten verdampen."""
    uit = bundel([_f("1", "5.3", severity="NC"), _f("2", "7.4", severity="OFI")])
    assert len(uit) == 2
    assert {f.severity for f in uit} == {"NC", "OFI"}


def test_zonder_thema_blijft_alles_los() -> None:
    """Twee labelloze bevindingen samentrekken suggereert een verband dat er niet is."""
    uit = bundel([_f("1", "5.3", thema=None), _f("2", "7.4", thema="Overig")])
    assert len(uit) == 2


def test_dezelfde_clausule_onder_twee_normen_telt_een_keer() -> None:
    """23 Annex SL-nummers bestaan in beide normen; dat is één oordeel, in twee rijen gekopieerd."""
    uit = bundel(
        [
            _f("1", "7.5", standard="iso-27001-2022"),
            _f("2", "7.5", standard="iso-9001-2015"),
        ]
    )
    assert len(uit) == 1
    assert uit[0].clause == "7.5"
    assert uit[0].extra_clauses == []
    assert uit[0].normen == ["iso-27001-2022", "iso-9001-2015"], "beide normen moeten zichtbaar"
    assert uit[0].gebundeld_uit == ["1", "2"]


def test_clausules_staan_op_normvolgorde_en_bijlage_a_achteraan() -> None:
    uit = bundel([_f("1", "10.2"), _f("2", "A.5.1"), _f("3", "4.1"), _f("4", "9.2")])
    assert [uit[0].clause, *uit[0].extra_clauses] == ["4.1", "9.2", "10.2", "A.5.1"]


def test_een_losse_bevinding_blijft_ongemoeid() -> None:
    """Geen bundel betekent: exact wat er binnenkwam, ook het id en de titel."""
    origineel = _f("1", "5.3")
    uit = bundel([origineel])
    assert uit == [origineel]


def test_de_beschrijvingen_blijven_allemaal_staan() -> None:
    """Eén representant overhouden maakt van een afwijking met tien kanten een anekdote."""
    uit = bundel(
        [
            _f("1", "5.3", beschrijving="Rollen niet vastgelegd."),
            _f("2", "9.2", beschrijving="Evaluatie niet uitgevoerd."),
        ]
    )
    assert "Rollen niet vastgelegd." in uit[0].description
    assert "Evaluatie niet uitgevoerd." in uit[0].description


def test_identieke_beschrijvingen_worden_ontdubbeld() -> None:
    """Dezelfde zin twee keer onder elkaar leest als drang."""
    uit = bundel([_f("1", "5.3", beschrijving="Zelfde."), _f("2", "9.2", beschrijving="Zelfde.")])
    assert uit[0].description == "Zelfde."


def test_de_titel_noemt_de_raakvlakken() -> None:
    uit = bundel([_f("1", "5.3"), _f("2", "7.4"), _f("3", "9.2")])
    assert uit[0].title.startswith("§5.3, §7.4, §9.2 — Rollen & verantwoordelijkheden")
    assert "Memo NC-2025" in uit[0].title


def test_een_lange_titel_blijft_leesbaar_zonder_iets_te_verliezen() -> None:
    """De titel kort af bij meer dan vier; de volledige lijst staat in `extra_clauses`."""
    clausules = ["4.1", "5.3", "7.4", "7.5", "9.2", "10.2"]
    uit = bundel([_f(str(i), c) for i, c in enumerate(clausules)])
    assert "+2" in uit[0].title
    assert len([uit[0].clause, *uit[0].extra_clauses]) == len(clausules)


def test_de_bronnen_worden_ontdubbeld() -> None:
    uit = bundel([_f("1", "5.3"), _f("2", "7.4")])
    assert len(uit[0].bronnen) == 1


def test_een_lege_lijst_geeft_een_lege_lijst() -> None:
    assert bundel([]) == []
