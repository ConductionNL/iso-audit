"""Auto-triage doet ook OFI's af, niet alleen positieve bevindingen.

Op de run van 2026-08-25 stonden 136 OFI's en 171 positieve bevindingen tegenover 108 NC's.
Auto-triage raakte alleen die 171 — de OFI's bleven met de hand te doen, terwijl er precies
hetzelfde voor geldt als voor een positieve bevinding: de review bevestigt wat de classificatie
al zei, en er valt geen oordeel te vellen dat de certificering raakt.

Wat níet verandert, en dat is de kern van de afspraak: **een NC blijft van de auditor.** Correctie
en formele verificatie zijn gevolgen die de organisatie draagt, en de trail moet daar een
mens-account tonen. Dat wordt sinds a54 op de schrijfweg afgedwongen
(`tests/api/test_nc_alleen_door_mens.py`); dit hier is de laag ervoor.
"""

from __future__ import annotations

from typing import Any

from iso_audit.classification.auto_triage import AUTOMATISCH_AF_TE_DOEN, voorstellen
from iso_audit.classification.review import Advies, Clausulegroep


def _groep(classificatie: str, bev_id: str = "b1") -> Clausulegroep:
    return Clausulegroep(
        norm="27001",
        clausule="8.14",
        bevindingen=[{"id": bev_id, "classificatie": classificatie}],
    )


def _advies(advies: str, klasse: str | None) -> Advies:
    return Advies(
        advies=advies,
        voorgestelde_klasse=klasse,
        reden="de review vond het bewijs afdoende",
        ernst=None,
        kern="",
        acties=[],
        zonder_inhoud=[],
    )


def _ids(uitkomsten: list[tuple[Any, Any, Any]]) -> list[str]:
    return [v.finding_id for v in voorstellen(uitkomsten)]


def test_ofi_staat_in_de_lijst_met_automatisch_af_te_doen_klassen() -> None:
    assert "OFI" in AUTOMATISCH_AF_TE_DOEN
    assert "positief" in AUTOMATISCH_AF_TE_DOEN
    assert "NC" not in AUTOMATISCH_AF_TE_DOEN


def test_een_bevestigde_ofi_wordt_automatisch_afgedaan() -> None:
    assert _ids([(_groep("OFI"), _advies("bevestigen", "OFI"), None)]) == ["b1"]


def test_een_bevestigde_positieve_bevinding_nog_steeds_ook() -> None:
    assert _ids([(_groep("positief"), _advies("bevestigen", "positief"), None)]) == ["b1"]


def test_een_nc_blijft_van_de_auditor() -> None:
    assert _ids([(_groep("NC"), _advies("bevestigen", "NC"), None)]) == []


def test_een_verlaging_blijft_van_de_auditor() -> None:
    """Verlagen is juist wél een oordeel: de review vindt het bewijs onvoldoende."""
    assert _ids([(_groep("NC"), _advies("verlagen", "OFI"), None)]) == []


def test_een_klasse_die_niet_matcht_wordt_niet_afgedaan() -> None:
    """De review adviseert OFI terwijl de bevinding positief is — dat is een wijziging."""
    assert _ids([(_groep("positief"), _advies("bevestigen", "OFI"), None)]) == []


def test_een_storing_levert_niets_op() -> None:
    """Geen advies is geen groen licht."""
    assert _ids([(_groep("OFI"), None, "model gaf geen antwoord")]) == []


def test_de_reden_noemt_de_klasse_zodat_de_trail_leesbaar_blijft() -> None:
    v = voorstellen([(_groep("OFI"), _advies("bevestigen", "OFI"), None)])
    assert "OFI" in v[0].reden
    assert "27001 §8.14" in v[0].reden
