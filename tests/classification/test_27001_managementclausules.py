"""ISO 27001 wordt op de hele norm getoetst, niet alleen op Bijlage A.

Tot 2026-08-28 bevatte de norm-DB voor 27001 uitsluitend de 93 maatregelen uit Bijlage A,
genummerd `5.1` t/m `8.34`. De managementclausules 4 t/m 10 — context, leiderschap, planning,
ondersteuning, uitvoering, evaluatie, verbetering — ontbraken volledig. Dat is de helft van de
certificeringseis, en het kwam pas boven water toen de auditor hoofdstuk 4 koos en een
foutmelding kreeg.

Ze allebei opnemen vraagt een keuze, want de nummers botsen: §5.1 is "Leiderschap en
betrokkenheid" en A.5.1 is "Beleid voor informatiebeveiliging". De norm zelf lost dat op met de
`A.`-prefix voor Bijlage A, en dat doen wij nu ook.

**Herkomst van de tekst.** De managementclausules komen uit `Norm ISO 27001.pdf` in de Drive van
de organisatie. Dat is de 2013/2017-uitgave; de structuur van hoofdstuk 4-10 is in 2022
ongewijzigd op twee punten na, en die zijn hier expliciet toegepast:

- 2022 voegt **6.3 Planning van wijzigingen** toe.
- 2022 draait 10.1 en 10.2 om: 10.1 is Continue verbetering, 10.2 Afwijkingen en corrigerende
  maatregelen.

Dat staat hier omdat het een aanname is die niet uit het brondocument volgt. Wie hem wil
controleren, weet nu waar hij op moet letten.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_DB = Path("examples/norms/iso-27001-2022.yaml")


@pytest.fixture(scope="module")
def clausules() -> dict[str, dict[str, str]]:
    return yaml.safe_load(_DB.read_text(encoding="utf-8"))["clauses"]


def test_de_managementclausules_staan_erin(clausules: dict[str, dict[str, str]]) -> None:
    """Hoofdstuk 4 t/m 10; dit was de melding die de auditor kreeg."""
    hoofdstukken = {k.split(".")[0] for k in clausules if not k.startswith("A.")}
    assert hoofdstukken == {"4", "5", "6", "7", "8", "9", "10"}


def test_hoofdstuk_vier_is_compleet(clausules: dict[str, dict[str, str]]) -> None:
    for nummer in ("4.1", "4.2", "4.3", "4.4"):
        assert nummer in clausules, nummer


def test_de_titels_komen_uit_de_norm(clausules: dict[str, dict[str, str]]) -> None:
    assert "context" in clausules["4.1"]["title_nl"].lower()
    assert "leiderschap" in clausules["5.1"]["title_nl"].lower()
    assert "interne audit" in clausules["9.2"]["title_nl"].lower()


def test_bijlage_a_heeft_de_a_prefix(clausules: dict[str, dict[str, str]]) -> None:
    """Zoals de norm zelf: A.5.1 is Beleid, 5.1 is Leiderschap."""
    assert "A.5.1" in clausules
    assert "beleid" in clausules["A.5.1"]["title_nl"].lower()
    assert "leiderschap" in clausules["5.1"]["title_nl"].lower()


def test_alle_drieennegentig_maatregelen_zijn_er_nog(
    clausules: dict[str, dict[str, str]],
) -> None:
    """De hernoeming mag er geen kwijtraken."""
    annex = [k for k in clausules if k.startswith("A.")]
    assert len(annex) == 93


def test_geen_enkele_maatregel_staat_er_nog_zonder_prefix(
    clausules: dict[str, dict[str, str]],
) -> None:
    """`8.14` is nu Bijlage A noch managementclausule — 27001 heeft geen 8.14 in hoofdstuk 8."""
    assert "8.14" not in clausules
    assert "A.8.14" in clausules


def test_de_2022_verschillen_zijn_toegepast(clausules: dict[str, dict[str, str]]) -> None:
    """Het brondocument is de 2013-uitgave; deze twee punten wijken in 2022 af."""
    assert "6.3" in clausules, "2022 voegt 6.3 Planning van wijzigingen toe"
    assert "verbetering" in clausules["10.1"]["title_nl"].lower()
    assert "afwijking" in clausules["10.2"]["title_nl"].lower()


def test_elke_clausule_heeft_een_titel_en_tekst(clausules: dict[str, dict[str, str]]) -> None:
    """Een clausule zonder tekst levert een memo-citaat dat leeg is."""
    for nummer, gegevens in clausules.items():
        assert gegevens.get("title_nl"), nummer
        assert gegevens.get("text_nl"), nummer


def test_de_zoektermen_dekken_dezelfde_clausules() -> None:
    """Loopt de clause-map uit de pas, dan wordt een clausule nooit gekoppeld."""
    from iso_audit.classification.clause_mapping import laad_clause_map

    kaart = set(laad_clause_map("27001")["clausules"])
    db = set(yaml.safe_load(_DB.read_text(encoding="utf-8"))["clauses"])
    ontbreekt = db - kaart
    assert not ontbreekt, f"geen zoektermen voor: {sorted(ontbreekt)[:10]}"


# --- scope kiezen -----------------------------------------------------------


def test_elke_scope_levert_wat_de_norm_belooft() -> None:
    """De aantallen komen uit ISO 27001:2022 zelf: 4 clausules in hoofdstuk 4, 37 in A.5, 34 in A.8.

    Dit is de toets die na de A-prefix telt: kan een auditor kiezen wát hij toetst, en krijgt hij
    dan precies dat? Vóór 2026-08-28 bestond alleen Bijlage A en gaf hoofdstuk 4 een foutmelding.
    """
    from iso_audit.classification.clause_mapping import filter_clause_map, laad_clause_map

    kaart = laad_clause_map("27001")
    verwacht = {
        "4": 4,  # context van de organisatie
        "5": 3,  # leiderschap
        "9": 3,  # evaluatie van de prestaties
        "A": 93,  # de hele Bijlage A
        "A.5": 37,  # organisatorische maatregelen
        "A.6": 8,  # mensgerichte maatregelen
        "A.7": 14,  # fysieke maatregelen
        "A.8": 34,  # technologische maatregelen
        "A.8.24": 1,  # één maatregel
    }
    gemeten = {h: len(filter_clause_map(kaart, h)["clausules"]) for h in verwacht}
    assert gemeten == verwacht


def test_hoofdstuk_acht_bevat_geen_maatregelen() -> None:
    """§8 is "Uitvoering", A.8 zijn de technologische maatregelen. Zonder dat onderscheid zou een
    run op hoofdstuk 8 er 34 meenemen die er niet bij horen."""
    from iso_audit.classification.clause_mapping import filter_clause_map, laad_clause_map

    kaart = laad_clause_map("27001")
    acht = set(filter_clause_map(kaart, "8")["clausules"])
    annex_acht = set(filter_clause_map(kaart, "A.8")["clausules"])
    assert not acht & annex_acht
    assert all(not c.startswith("A.") for c in acht)


def test_de_vier_themas_van_bijlage_a_zijn_compleet() -> None:
    """37 + 8 + 14 + 34 = 93. Een thema dat clausules kwijtraakt, valt niet op zonder deze som."""
    from iso_audit.classification.clause_mapping import filter_clause_map, laad_clause_map

    kaart = laad_clause_map("27001")
    per_thema = [len(filter_clause_map(kaart, f"A.{n}")["clausules"]) for n in (5, 6, 7, 8)]
    assert sum(per_thema) == 93, per_thema
