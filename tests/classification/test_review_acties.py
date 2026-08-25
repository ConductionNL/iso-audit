"""De review stelt acties voor: wat, welke rol, welke termijn.

Het handgemaakte Q2-memo heeft per NC een tabel Wat | Wie | Waar | Uiterlijk. Die velden bestaan
in het datamodel maar niemand vulde ze, en een memo zonder die tabel is een constatering zonder
opdracht — precies wat het management níet nodig heeft.

De review kan ze voorbereiden omdat hij als enige de clausule als geheel heeft gezien. Wat hij
levert is een **voorstel**: een rol en een termijn, geen naam en geen datum. Een naam toewijzen
is een besluit van de organisatie, en een agent die dat doet maakt van beoordelen bevestigen.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from iso_audit.classification.review import Clausulegroep, ReviewFoutError, lees_advies


def _groep() -> Clausulegroep:
    return Clausulegroep(
        clausule="8.14",
        norm="27001",
        bevindingen=[
            {
                "doc_id": "d1",
                "document_naam": "Continuiteitsplan.docx",
                "classificatie": "NC",
                "beschrijving": "Geen getest plan.",
                "onderbouwing": "§8.14",
            }
        ],
    )


def _antwoord(**kw: Any) -> str:
    basis: dict[str, Any] = {
        "advies": "bevestigen",
        "voorgestelde_klasse": "NC",
        "ernst": "minor",
        "kern": "Er is geen getest continuïteitsplan.",
        "reden": "Continuiteitsplan.docx beschrijft geen test.",
        "zonder_inhoud": 0,
        "acties": [
            {"wat": "BCM-plan opstellen met RTO/RPO", "wie": "IT-lead", "uiterlijk": "2026-Q3"}
        ],
    }
    basis.update(kw)
    return json.dumps(basis)


def test_een_voorgestelde_actie_wordt_gelezen() -> None:
    advies = lees_advies(_antwoord(), _groep())
    assert len(advies.acties) == 1
    assert advies.acties[0].wat.startswith("BCM-plan")
    assert advies.acties[0].wie == "IT-lead"
    assert advies.acties[0].uiterlijk == "2026-Q3"


def test_zonder_acties_is_geen_fout() -> None:
    """Bij een positieve bevinding of een verlaging valt er niets te doen."""
    advies = lees_advies(_antwoord(acties=[]), _groep())
    assert advies.acties == []


def test_een_actie_zonder_wat_wordt_overgeslagen() -> None:
    """Een actie zonder opdracht is geen actie; wie en wanneer zeggen dan niets."""
    advies = lees_advies(
        _antwoord(acties=[{"wat": "  ", "wie": "IT", "uiterlijk": "Q3"}]), _groep()
    )
    assert advies.acties == []


def test_een_persoonsnaam_wordt_geweigerd() -> None:
    """`wie` is een rol, geen mens.

    Een agent die een naam toewijst neemt een besluit van de organisatie. Bovendien staat er dan
    een persoonsnaam in een auditdocument die niemand heeft goedgekeurd.
    """
    with pytest.raises(ReviewFoutError, match="rol"):
        lees_advies(
            _antwoord(acties=[{"wat": "Plan opstellen", "wie": "Mark Westerweel"}]), _groep()
        )


def test_een_rol_met_meerdere_woorden_mag() -> None:
    advies = lees_advies(
        _antwoord(acties=[{"wat": "Plan opstellen", "wie": "KAM + MT", "uiterlijk": "2026-Q3"}]),
        _groep(),
    )
    assert advies.acties[0].wie == "KAM + MT"


def test_te_veel_acties_worden_afgekapt_en_gemeld() -> None:
    """Vier acties per NC is al veel voor drie A4; het Q2-memo had er drie."""
    from iso_audit.classification.review import MAX_ACTIES

    acties = [{"wat": f"Actie {i}", "wie": "IT-lead"} for i in range(MAX_ACTIES + 3)]
    advies = lees_advies(_antwoord(acties=acties), _groep())
    assert len(advies.acties) == MAX_ACTIES
