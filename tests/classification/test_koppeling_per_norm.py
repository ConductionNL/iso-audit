"""Een koppeling draagt de norm waaruit hij komt.

`laad_clause_map("beide")` voegde de twee maps samen met `{**map_9001, **map_27001}`. Achttien
clausulenummers bestaan in beide normen, en bij een botsing won 27001 — dus in een gecombineerde
audit werden 18 van de 28 ISO 9001-clausules nooit getoetst (§5.1 Leiderschap, §6.1 Risico's en
kansen, §7.5 Gedocumenteerde informatie, §8.4 Externe processen en zo verder). De samengevoegde
map had 103 ingangen waar er 148 horen (28 + 120).

Daaruit volgde ook dat een bevinding zijn norm niet wist: `bevindingen.norm` stond op `beide` voor
alle 800 rijen van de meting op 2026-08-24, en `run_job._resolve_standard()` moest achteraf raden
— met een half gevulde norm-DB raadde die er 448 verkeerd.

De koppeling draait nu per norm. Elke match draagt zijn eigen norm, en de zoektermen van de ene
norm kunnen die van de andere niet meer overschrijven.
"""

from __future__ import annotations

from typing import Any

from iso_audit.classification.clause_mapping import koppel_documenten, laad_clause_map

_MAP_9001: dict[str, Any] = {
    "clausules": {
        "7.5": {"titel": "Gedocumenteerde informatie", "zoektermen": ["documentbeheer"]},
        "10.2": {"titel": "Non-conformiteit", "zoektermen": ["corrigerende maatregel"]},
    }
}
_MAP_27001: dict[str, Any] = {
    "clausules": {
        "7.5": {"titel": "Beveiligd ontwikkelen", "zoektermen": ["secure development"]},
        "8.24": {"titel": "Cryptografie", "zoektermen": ["encryptie"]},
    }
}


def _doc(tekst: str) -> dict[str, Any]:
    return {"id": "d1", "naam": "Beleid.docx", "tekst": tekst}


def test_match_draagt_de_norm() -> None:
    gekoppeld, _ = koppel_documenten(
        [_doc("Ons documentbeheer is vastgelegd.")], _MAP_9001, norm="9001"
    )
    assert gekoppeld[0]["clausule_normen"] == [("7.5", "9001")]


def test_zelfde_nummer_in_beide_normen_levert_twee_koppelingen() -> None:
    """Het geval waar het om gaat: §7.5 betekent in beide normen iets anders."""
    doc = _doc("Ons documentbeheer is vastgelegd en secure development is ingericht.")

    negen, _ = koppel_documenten([doc], _MAP_9001, norm="9001")
    zevenentwintig, _ = koppel_documenten([doc], _MAP_27001, norm="27001")

    assert negen[0]["clausule_normen"] == [("7.5", "9001")]
    assert zevenentwintig[0]["clausule_normen"] == [("7.5", "27001")]


def test_clausules_blijft_de_lijst_met_id_s() -> None:
    """`clausules` wordt afgeleid uit `clausule_normen`, niet apart bijgehouden.

    Twee lijsten die hetzelfde beweren lopen uiteen zodra iemand er één vergeet — dezelfde
    reden dat de norm-DB een gegenereerde export werd in plaats van handwerk.
    """
    gekoppeld, _ = koppel_documenten(
        [_doc("Ons documentbeheer en de corrigerende maatregel staan vast.")],
        _MAP_9001,
        norm="9001",
    )
    doc = gekoppeld[0]
    assert sorted(doc["clausules"]) == ["10.2", "7.5"]
    assert sorted(c for c, _ in doc["clausule_normen"]) == ["10.2", "7.5"]


def test_zonder_norm_blijft_het_gedrag_gelijk() -> None:
    """Bestaande aanroepers zonder `norm` blijven werken; de norm is dan leeg."""
    gekoppeld, _ = koppel_documenten([_doc("documentbeheer")], _MAP_9001)
    assert gekoppeld[0]["clausules"] == ["7.5"]
    assert gekoppeld[0]["clausule_normen"] == [("7.5", "")]


def test_de_echte_maps_verliezen_geen_enkele_clausule() -> None:
    """Per norm koppelen betekent dat álle clausules kandidaat zijn, niet alleen de unieke.

    28 (9001) + 120 (27001: 27 managementclausules + 93 Bijlage A) = 148. Samenvoegen op nummer
    zou de overlappende nummers laten winnen door één norm — dat was de fout van 2026-08-24."""
    negen = laad_clause_map("9001")["clausules"]
    zevenentwintig = laad_clause_map("27001")["clausules"]
    assert len(negen) == 28
    assert len(zevenentwintig) == 120
    # Nummers komen in beide normen voor; per norm geteld zijn het er 148.
    assert len(negen) + len(zevenentwintig) == 148
    # 23 nummers komen in beide normen voor. Dat waren er 18 toen 27001 alleen Bijlage A kende;
    # sinds de managementclausules erbij zijn, overlappen ook 4.x, 9.x en 10.x — beide normen
    # volgen Annex SL. Precies daarom draagt een koppeling zijn norm mee en niet alleen een
    # nummer: 9001 §8.2 is "Eisen voor producten en diensten", 27001 §8.2 is een risicobeoordeling.
    assert len(set(negen) & set(zevenentwintig)) == 23
