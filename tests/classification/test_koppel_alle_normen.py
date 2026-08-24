"""Een gecombineerde audit koppelt per norm en verliest geen clausules.

`koppel_alle_normen` vervangt de aanroep met `laad_clause_map("beide")`. Die samenvoeging
(`{**map_9001, **map_27001}`) liet 27001 de 9001-ingang overschrijven bij een botsend nummer:
103 ingangen waar er 121 horen, en 18 ISO 9001-clausules die in een gecombineerde audit nooit
werden getoetst.
"""

from __future__ import annotations

from typing import Any

from iso_audit.classification.clause_mapping import koppel_alle_normen


def _doc(id_: str, tekst: str) -> dict[str, Any]:
    return {"id": id_, "naam": f"{id_}.docx", "tekst": tekst}


def test_beide_normen_leveren_beide_koppelingen() -> None:
    """Een document dat beide §7.5-onderwerpen raakt, krijgt twee koppelingen."""
    doc = _doc("d1", "Onze processen en procedures staan vast; er is brandbescherming en een UPS.")

    gekoppeld, _ = koppel_alle_normen([doc], "beide")

    normen = {n for c, n in gekoppeld[0]["clausule_normen"] if c == "7.5"}
    assert normen == {"9001", "27001"}, f"niet beide normen gekoppeld: {normen}"


def test_een_norm_koppelt_alleen_die_norm() -> None:
    doc = _doc("d1", "Onze processen en procedures staan vast.")

    gekoppeld, _ = koppel_alle_normen([doc], "9001")

    assert all(n == "9001" for _, n in gekoppeld[0]["clausule_normen"])


def test_een_document_zonder_match_blijft_ongeclassificeerd() -> None:
    gekoppeld, niet = koppel_alle_normen([_doc("d1", "kattenplaatjes")], "beide")
    assert not gekoppeld
    assert [d["id"] for d in niet] == ["d1"]


def test_een_document_komt_maar_een_keer_terug() -> None:
    """Twee normen koppelen mag het document niet verdubbelen — één rij, twee matches."""
    doc = _doc("d1", "processen en procedures, plus brandbescherming")

    gekoppeld, _ = koppel_alle_normen([doc], "beide")

    assert len(gekoppeld) == 1
    assert len(gekoppeld[0]["clausule_normen"]) >= 2


def test_negenduizendeen_clausules_blijven_bestaan_naast_27001() -> None:
    """De regressie waar het om begonnen is: §7.5 van 9001 verdwijnt niet meer.

    In de echte maps is 9001 §7.5 "Gedocumenteerde informatie" en 27001 §7.5 "Bescherming
    tegen fysieke en omgevingsbedreigingen" — heel verschillende onderwerpen onder één nummer.
    """
    doc = _doc("d1", "Onze processen en procedures staan vast.")

    gekoppeld, _ = koppel_alle_normen([doc], "beide")

    koppelingen = gekoppeld[0]["clausule_normen"]
    assert ("7.5", "9001") in koppelingen, (
        "ISO 9001 §7.5 werd niet gekoppeld — 27001 heeft de ingang weer overschreven"
    )
