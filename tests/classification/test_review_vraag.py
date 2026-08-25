"""De reviewvraag bevat het bewijs en meldt wat er is afgekapt."""

from __future__ import annotations

from iso_audit.classification.review import (
    MAX_BEVINDINGEN_PER_GROEP,
    Clausulegroep,
    bouw_reviewvraag,
)


def _groep(aantal: int) -> Clausulegroep:
    return Clausulegroep(
        clausule="10.2",
        norm="9001",
        bevindingen=[
            {
                "doc_id": f"d{i}",
                "document_naam": f"Doc{i}.docx",
                "classificatie": "NC",
                "beschrijving": f"Bevinding {i}",
                "onderbouwing": "§10.2",
            }
            for i in range(aantal)
        ],
    )


def test_de_vraag_noemt_clausule_norm_en_aantallen() -> None:
    vraag, _ = bouw_reviewvraag(_groep(3))
    assert "9001 §10.2" in vraag
    assert "3" in vraag


def test_elke_bevinding_gaat_mee_met_haar_document() -> None:
    vraag, afgekapt = bouw_reviewvraag(_groep(3))
    assert afgekapt == 0
    for i in range(3):
        assert f"Doc{i}.docx" in vraag


def test_afkappen_wordt_gemeld_in_de_vraag() -> None:
    """Een lijst die stil op 25 stopt leest als 'dit is alles'.

    Clausule 10.2 had 27 bevindingen in de run van 2026-08-24. Zonder deze melding zou het
    model over 25 oordelen en denken dat het er 25 waren.
    """
    vraag, afgekapt = bouw_reviewvraag(_groep(MAX_BEVINDINGEN_PER_GROEP + 2))
    assert afgekapt == 2
    assert "LET OP" in vraag
    assert str(afgekapt) in vraag


def test_normtekst_gaat_mee_als_hij_er_is() -> None:
    vraag, _ = bouw_reviewvraag(_groep(1), normtekst="De organisatie moet reageren op afwijkingen.")
    assert "moet reageren op afwijkingen" in vraag


def test_een_lege_beschrijving_wordt_zichtbaar_gemeld() -> None:
    """Het model moet kunnen tellen hoeveel bevindingen niets zeggen; dat is deelvraag 1."""
    groep = _groep(1)
    groep.bevindingen[0]["beschrijving"] = ""
    vraag, _ = bouw_reviewvraag(groep)
    assert "(geen beschrijving)" in vraag
