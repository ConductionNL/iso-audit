"""Tests voor `iso_audit.eigen_output` — het tool mag zijn eigen rapporten niet als bewijs lezen.

Gemeten op 2026-08-22: 462 van de 1241 bevindingen (37%) kwamen uit twaalf documenten die dit
tool zelf schreef. Een bevinding die als bewijs een eerder eigen auditrapport aanwijst, is geen
onafhankelijke observatie maar een echo — en dat raakt de onafhankelijkheid van de interne
auditfunctie.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from iso_audit import eigen_output


def test_merkteken_in_de_tekst_wordt_herkend() -> None:
    tekst = f"# Auditrapport ISO 27001\n\n_{eigen_output.MERKTEKEN}._\n\nInhoud."
    assert eigen_output.is_eigen_output(tekst=tekst)


def test_merkteken_verderop_in_een_lang_document_telt_niet() -> None:
    """Het merkteken hoort in de kop. Anders telt een citaat ervan als merkteken.

    Een auditrapport dat de zin ergens in een bijlage aanhaalt, is daarmee niet ineens eigen
    output.
    """
    tekst = "x" * 5000 + eigen_output.MERKTEKEN
    assert not eigen_output.is_eigen_output(tekst=tekst)


def test_extern_auditrapport_telt_gewoon_mee() -> None:
    """`Auditrapport 2022.docx` is van de certificerende instantie en is juist bewijs.

    Dit is de reden dat er niet op naampatroon wordt gefilterd: "alles wat met Auditrapport
    begint" zou precies het externe oordeel over ons wegfilteren.
    """
    assert not eigen_output.is_eigen_output(
        naam="Auditrapport 2022.docx", tekst="Bevindingen van de certificerende instantie."
    )
    assert not eigen_output.is_eigen_output(naam="Bevindingen refactor OR", tekst="notulen")


def test_eenmalige_lijst_dekt_de_bestanden_die_er_al_stonden() -> None:
    """Tien bestanden van vóór het merkteken, één voor één nagekeken op naamvorm."""
    for naam in (
        "Auditrapport_beide_v3.3_2026-05-05.pdf",
        "Bevindingen_beide_v3.3_2026-05-05.csv",
        "Auditmemo_management_2026-06-23.pdf",
    ):
        assert eigen_output.is_eigen_output(naam=naam), naam
    assert len(eigen_output.BESTAANDE_EIGEN_OUTPUT) == 10


def test_splits_houdt_beide_lijsten() -> None:
    """Uitsluiten is niet weggooien: de eigen output blijft opvraagbaar."""
    docs: list[dict[str, Any]] = [
        {"naam": "Beleid.docx", "tekst": "wij versleutelen"},
        {"naam": "Auditrapport_beide_v3.3_2026-05-05.md", "tekst": "oude bevindingen"},
        {"naam": "Nieuw rapport.md", "tekst": f"_{eigen_output.MERKTEKEN}._ inhoud"},
    ]

    extern, eigen = eigen_output.splits(docs)

    assert [d["naam"] for d in extern] == ["Beleid.docx"]
    assert len(eigen) == 2, "op naam én op merkteken"


def test_rapport_van_dit_tool_wordt_door_zijn_eigen_merkteken_herkend(tmp_path: Path) -> None:
    """De kringloop dicht: schrijf een rapport en lees het terug.

    Zonder deze test kan het merkteken uit de rapportkop verdwijnen zonder dat iets faalt, en
    dan is de 37% na één refactor terug.
    """
    from iso_audit.reporting.local_report import schrijf_rapport

    pad = schrijf_rapport(
        bevindingen=[],
        ontbrekende_clausules=[],
        handmatige_review=[],
        management_summary="samenvatting",
        norm="27001",
        output_dir=str(tmp_path),
    )
    tekst = Path(pad).read_text(encoding="utf-8")

    assert eigen_output.is_eigen_output(naam=Path(pad).name, tekst=tekst)


def test_pipeline_classificeert_eigen_output_niet(tmp_path: Path) -> None:
    """De splitsing zit vóór de clausule-koppeling, dus vóór de classificatie."""
    docs: list[dict[str, Any]] = [
        {"naam": "Beleid.docx", "tekst": "toegangsbeheer", "id": "1", "herkomst": "Drive"},
        {
            "naam": "Auditrapport_beide_2026-03-24_s05.md",
            "tekst": "eerdere bevindingen over toegangsbeheer",
            "id": "2",
            "herkomst": "Drive",
        },
    ]
    extern, eigen = eigen_output.splits(docs)
    assert len(extern) == 1 and len(eigen) == 1
