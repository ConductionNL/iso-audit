"""Geen oordeel is geen OFI.

`(res_map.get(cid, {}) or {}).get("classificatie", "OFI")` maakte van elk ontbrekend antwoord
een OFI. Twee gevallen vielen daaronder:

1. Het model zegt niets over deze clausule (de clausule ontbreekt in het antwoord).
2. Het model zegt expliciet `null` — "dit document gaat hier niet over", de uitweg die de
   prompts sinds 2026-08-24 aanbieden.

Beide werden een OFI met een lege beschrijving en een lege onderbouwing. In de run van
2026-08-24 waren dat er **55**: een oordeel zonder inhoud dat wel meetelde in het rapport. En
het is de mechaniek achter 6,8 bevindingen per document — elk document-clausulepaar dat de
zoektermen opleverden moest een oordeel worden, ook als er niets over te zeggen viel.

Een bevinding zonder oordeel hoort niet te bestaan. Dat is geen filtering van een oordeel maar
het uitblijven ervan.
"""

from __future__ import annotations

from typing import Any

from iso_audit.classification.findings import bouw_bevindingen


def _antwoord(**kw: Any) -> dict[str, Any]:
    basis = {
        "clausule": "8.24",
        "classificatie": "NC",
        "beschrijving": "Geen cryptografiebeleid aangetroffen.",
        "onderbouwing": "27001 §8.24 eist regels voor het gebruik van cryptografie.",
    }
    basis.update(kw)
    return basis


def test_null_levert_geen_bevinding() -> None:
    """De uitweg uit de prompt moet ook echt een uitweg zijn."""
    bevindingen = bouw_bevindingen(
        doc={"id": "d1", "naam": "Onboarding.docx", "herkomst": "Drive"},
        clausules=["8.24"],
        resultaten=[_antwoord(classificatie=None)],
        clausule_titels={},
    )
    assert bevindingen == []


def test_ontbrekend_antwoord_levert_geen_bevinding() -> None:
    """Zwijgen is ook geen oordeel — dat werd voorheen stilzwijgend een OFI."""
    bevindingen = bouw_bevindingen(
        doc={"id": "d1", "naam": "Onboarding.docx", "herkomst": "Drive"},
        clausules=["8.24", "5.11"],
        resultaten=[_antwoord(clausule="8.24")],
        clausule_titels={},
    )
    assert [b["clausule"] for b in bevindingen] == ["8.24"]


def test_een_echt_oordeel_blijft_gewoon_staan() -> None:
    bevindingen = bouw_bevindingen(
        doc={"id": "d1", "naam": "Cryptobeleid.docx", "herkomst": "Drive"},
        clausules=["8.24"],
        resultaten=[_antwoord()],
        clausule_titels={"8.24": {"titel": "Gebruik van cryptografie"}},
    )
    assert len(bevindingen) == 1
    assert bevindingen[0]["classificatie"] == "NC"
    assert bevindingen[0]["clausule_titel"] == "Gebruik van cryptografie"


def test_de_ernst_van_een_nc_gaat_mee() -> None:
    """`major` tegen `minor` bepaalt of certificering in gevaar is; die mag niet wegvallen."""
    bevindingen = bouw_bevindingen(
        doc={"id": "d1", "naam": "Beleid.docx", "herkomst": "Drive"},
        clausules=["8.24"],
        resultaten=[_antwoord(ernst="major")],
        clausule_titels={},
    )
    assert bevindingen[0]["ernst"] == "major"


def test_een_nc_zonder_onderbouwing_wordt_gemeld() -> None:
    """Een NC vraagt om correctie en root-cause-analyse; dat kan niet op een leeg oordeel.

    Niet weggooien maar markeren: dát het model een NC zonder onderbouwing teruggaf, is zelf
    een gegeven over de classificatie.
    """
    bevindingen = bouw_bevindingen(
        doc={"id": "d1", "naam": "Beleid.docx", "herkomst": "Drive"},
        clausules=["8.24"],
        resultaten=[_antwoord(onderbouwing="", beschrijving="")],
        clausule_titels={},
    )
    assert len(bevindingen) == 1
    assert bevindingen[0]["onbruikbaar"] is True


def test_de_string_null_is_ook_geen_oordeel() -> None:
    """Het model schrijft soms `"null"` in plaats van JSON-`null`.

    Gemeten in de run van 2026-08-24: twee bevindingen kwamen met classificatie `'null'` de
    database in. De controle keek alleen of de waarde leeg was, en een niet-lege string is dat
    niet. Gevolg: een bevinding met een classificatie die nergens op slaat — hij telt mee, hij
    is niet te triageren als NC of OFI, en in het rapport staat er een lege categorie.

    Ook `"none"` en `"geen"` afvangen: het zijn alle drie manieren waarop een model "hier valt
    niets over te zeggen" opschrijft als het de JSON-vorm niet haalt.
    """
    for waarde in ("null", "NULL", "none", "geen", "  null  "):
        bevindingen = bouw_bevindingen(
            doc={"id": "d1", "naam": "Onboarding.docx", "herkomst": "Drive"},
            clausules=["8.24"],
            resultaten=[_antwoord(classificatie=waarde)],
            clausule_titels={},
        )
        assert bevindingen == [], f"{waarde!r} werd als oordeel geaccepteerd"


def test_een_onbekende_classificatie_wordt_geweigerd() -> None:
    """Alleen de drie afgesproken waarden tellen als oordeel.

    Een model dat "gedeeltelijk" of "onduidelijk" teruggeeft, levert een bevinding op die geen
    van de UI-filters kent en die in de memo tussen wal en schip valt. Liever geen bevinding dan
    een categorie die niemand kan verwerken.
    """
    bevindingen = bouw_bevindingen(
        doc={"id": "d1", "naam": "Beleid.docx", "herkomst": "Drive"},
        clausules=["8.24"],
        resultaten=[_antwoord(classificatie="gedeeltelijk")],
        clausule_titels={},
    )
    assert bevindingen == []
