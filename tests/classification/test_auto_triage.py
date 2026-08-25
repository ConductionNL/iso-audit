"""Auto-triage: het review-advies omzetten in een triage-status, met een spoor.

Dit is de grens waar dit tool het meest voorzichtig moet zijn. De auditor-spiegel is de
capability die het draagt: op vaste punten houdt een mens het oordeel. Tegelijk is "902
bevindingen in vier bulkacties op valide" — wat er op 2026-08-24 gebeurde — geen menselijk
oordeel maar capitulatie voor het aantal.

De uitweg is niet "de agent beslist" maar **de agent doet het onbetwiste voorwerk, expliciet
gemarkeerd**. Drie regels:

1. **Alleen wat de review zelf niet betwist.** `bevestigen` op een positieve bevinding is geen
   oordeel maar een bevestiging van wat er al stond.
2. **Nooit een NC.** Een NC vraagt om correctie, root-cause en verificatie; die beslissing is
   van de auditor, altijd.
3. **Alles met een spoor**, met een actor die zegt dat het automatisch ging — zodat een auditor
   in één blik ziet wat een mens heeft besloten en wat niet.
"""

from __future__ import annotations

from typing import Any

import pytest

from iso_audit.classification.auto_triage import AUTO_ACTOR, voorstellen


def _advies(advies: str, klasse: str | None = None) -> Any:
    from iso_audit.classification.review import Advies

    return Advies(
        advies=advies,
        voorgestelde_klasse=klasse,
        ernst=None,
        kern="Kern.",
        reden="Volgens Beleid.docx.",
        zonder_inhoud=0,
    )


def _groep(clausule: str, klassen: list[str]) -> Any:
    from iso_audit.classification.review import Clausulegroep

    return Clausulegroep(
        clausule=clausule,
        norm="27001",
        bevindingen=[
            {
                "id": f"{clausule}-{i}",
                "doc_id": f"d{i}",
                "document_naam": "Beleid.docx",
                "classificatie": k,
                "beschrijving": "Iets",
                "onderbouwing": "§" + clausule,
            }
            for i, k in enumerate(klassen)
        ],
    )


def test_een_bevestigde_positieve_bevinding_mag_automatisch() -> None:
    """Niets betwist, niets te beslissen: de review bevestigt wat er al stond."""
    voorstel = voorstellen(
        [(_groep("8.16", ["positief"]), _advies("bevestigen", "positief"), None)]
    )
    assert [(v.finding_id, v.status) for v in voorstel] == [("8.16-0", "valide")]
    assert voorstel[0].actor == AUTO_ACTOR


def test_een_nc_wordt_nooit_automatisch_getriageerd() -> None:
    """Een NC vraagt om correctie, root-cause-analyse en formele verificatie.

    Dat is een besluit met gevolgen voor de certificering; dat hoort bij een mens, ook als de
    review hem bevestigt.
    """
    assert voorstellen([(_groep("5.15", ["NC"]), _advies("bevestigen", "NC"), None)]) == []


def test_een_verlaging_blijft_bij_de_auditor() -> None:
    """Verlagen is een oordeel: de review vindt het bewijs onvoldoende voor de zwaarste klasse.

    Precies het soort beslissing waarvoor de auditor-spiegel bestaat.
    """
    assert voorstellen([(_groep("10.2", ["NC"]), _advies("verlagen", "OFI"), None)]) == []


def test_onvoldoende_bewijs_levert_geen_voorstel() -> None:
    assert voorstellen([(_groep("5.13", ["OFI"]), _advies("onvoldoende_bewijs", None), None)]) == []


def test_een_storing_levert_geen_voorstel() -> None:
    """Geen advies is geen groen licht."""
    assert voorstellen([(_groep("8.16", ["positief"]), None, "ReviewFoutError: stuk")]) == []


def test_alleen_de_positieve_bevindingen_in_een_gemengde_groep() -> None:
    """Een groep met een NC erin levert hooguit voorstellen voor de positieve regels op."""
    groep = _groep("8.16", ["positief", "NC", "positief"])
    voorstel = voorstellen([(groep, _advies("bevestigen", "positief"), None)])
    assert sorted(v.finding_id for v in voorstel) == ["8.16-0", "8.16-2"]


def test_elk_voorstel_draagt_de_reden_van_de_review() -> None:
    """Zonder reden is niet na te trekken waaróm iets automatisch is afgedaan."""
    voorstel = voorstellen(
        [(_groep("8.16", ["positief"]), _advies("bevestigen", "positief"), None)]
    )
    assert "Beleid.docx" in voorstel[0].reden
    assert "review" in voorstel[0].reden.lower()


@pytest.mark.parametrize("advies", ["samenvoegen", "verlagen", "onvoldoende_bewijs"])
def test_alleen_bevestigen_leidt_tot_een_voorstel(advies: str) -> None:
    assert voorstellen([(_groep("8.16", ["positief"]), _advies(advies, "positief"), None)]) == []
