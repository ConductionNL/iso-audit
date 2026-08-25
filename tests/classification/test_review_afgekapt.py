"""Een afgekapt review-antwoord is een storing met een reden, geen JSON-fout.

In de run van 2026-08-25 22:38 kwamen 18 van de 37 storingen uit "Unterminated string" en
verwante JSON-fouten. Dat is geen onleesbaar model maar een **te krap budget**: `max_tokens`
stond nog op 1200 terwijl de prompt sinds die dag ook om een actietabel vraagt. Het antwoord
werd halverwege een string afgekapt.

De melding "antwoord is geen geldige JSON" wijst dan de verkeerde kant op — die laat je zoeken
naar een modelfout terwijl het budget de oorzaak is. Dezelfde les als bij de classificatie, waar
een afgekapt antwoord sinds 2026-08-17 ook geen leeg oordeel meer is maar een storing die zegt
wat er misging.
"""

from __future__ import annotations

import pytest

from iso_audit.classification.review import (
    MAX_ANTWOORD_TOKENS,
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
                "document_naam": "Beleid.docx",
                "classificatie": "NC",
                "beschrijving": "x",
                "onderbouwing": "y",
            }
        ],
    )


def test_het_budget_is_ruim_genoeg_voor_een_actietabel() -> None:
    """1200 tokens was krap voor advies + kern + reden + drie acties."""
    assert MAX_ANTWOORD_TOKENS >= 2000


def test_een_afgekapt_antwoord_noemt_de_afkapping() -> None:
    """Niet "geen geldige JSON": dat stuurt je naar het model in plaats van naar het budget."""
    afgekapt = '{"advies": "bevestigen", "kern": "Er is geen getest continuite'
    with pytest.raises(ReviewFoutError, match="afgekapt"):
        lees_advies(afgekapt, _groep())


def test_echte_rommel_blijft_een_json_fout() -> None:
    """Een antwoord dat nooit JSON was, is iets anders dan een antwoord dat het niet haalde."""
    with pytest.raises(ReviewFoutError, match="geen geldige JSON"):
        lees_advies("Ik kan deze clausule niet beoordelen.", _groep())
