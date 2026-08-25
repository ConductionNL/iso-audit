"""De review vraagt het model één ding per clausule, en controleert het antwoord.

Wat er misgaat als je dat niet controleert, is vandaag drie keer gebeurd: een classificatie
`'null'` als string, een advies dat nergens naar verwijst, en een oordeel zonder inhoud dat toch
meetelde. Dezelfde discipline als bij de Bronbevrager: tolerant voor de vorm, streng op de
inhoud.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from iso_audit.classification.review import (
    Clausulegroep,
    ReviewFoutError,
    lees_advies,
)


def _groep() -> Clausulegroep:
    return Clausulegroep(
        clausule="8.16",
        norm="27001",
        bevindingen=[
            {
                "doc_id": "d1",
                "document_naam": "Monitoringbeleid.docx",
                "classificatie": "NC",
                "beschrijving": "Geen monitoring beschreven.",
                "onderbouwing": "§8.16 eist monitoring van activiteiten.",
            },
            {
                "doc_id": "d2",
                "document_naam": "Logboek.md",
                "classificatie": "positief",
                "beschrijving": "Logging is ingericht.",
                "onderbouwing": "§8.16",
            },
        ],
    )


def _antwoord(**kw: Any) -> str:
    basis = {
        "advies": "verlagen",
        "voorgestelde_klasse": "OFI",
        "ernst": None,
        "kern": "Monitoring bestaat maar is niet vastgelegd.",
        "reden": "Logboek.md toont logging; Monitoringbeleid.docx beschrijft het niet.",
        "zonder_inhoud": 0,
    }
    basis.update(kw)
    return json.dumps(basis)


def test_een_geldig_advies_wordt_gelezen() -> None:
    advies = lees_advies(_antwoord(), _groep())
    assert advies.advies == "verlagen"
    assert advies.voorgestelde_klasse == "OFI"
    assert advies.kern


def test_een_onbekend_advies_is_een_storing() -> None:
    """Liever geen advies dan een advies dat geen enkel scherm kent."""
    with pytest.raises(ReviewFoutError, match="advies"):
        lees_advies(_antwoord(advies="misschien"), _groep())


def test_een_advies_zonder_verwijzing_is_een_storing() -> None:
    """Zonder documentnaam is het advies niet na te trekken.

    Dezelfde regel als bij de Bronbevrager, waar een antwoord zonder bronverwijzing een storing
    is en geen antwoord.
    """
    with pytest.raises(ReviewFoutError, match="verwijz"):
        lees_advies(_antwoord(reden="Het bewijs is onvoldoende."), _groep())


def test_een_verwijzing_naar_een_niet_meegegeven_document_is_een_storing() -> None:
    """Verzonnen bronnen zijn erger dan geen bronnen."""
    with pytest.raises(ReviewFoutError, match="verwijz"):
        lees_advies(_antwoord(reden="Zie Verzonnen.docx."), _groep())


def test_een_lege_kern_is_een_storing() -> None:
    """De kernzin gaat naar de memo; leeg betekent dat de memo niets te melden heeft."""
    with pytest.raises(ReviewFoutError, match="kern"):
        lees_advies(_antwoord(kern="   "), _groep())


def test_onleesbare_json_is_een_storing() -> None:
    with pytest.raises(ReviewFoutError):
        lees_advies("dit is geen json", _groep())


def test_json_in_een_codeblok_wordt_wel_gelezen() -> None:
    """Tolerant voor de vorm: modellen zetten er graag ```json omheen."""
    advies = lees_advies(f"```json\n{_antwoord()}\n```", _groep())
    assert advies.advies == "verlagen"


def test_een_klasse_buiten_de_drie_is_een_storing() -> None:
    with pytest.raises(ReviewFoutError, match="klasse"):
        lees_advies(_antwoord(voorgestelde_klasse="gedeeltelijk"), _groep())


def test_onvoldoende_bewijs_mag_zonder_klasse() -> None:
    """Als er geen oordeel te vellen is, hoort er ook geen klasse te staan."""
    advies = lees_advies(_antwoord(advies="onvoldoende_bewijs", voorgestelde_klasse=None), _groep())
    assert advies.voorgestelde_klasse is None
