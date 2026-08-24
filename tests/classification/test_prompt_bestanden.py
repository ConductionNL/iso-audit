"""Classificatie-prompts staan versiegestuurd op schijf, niet hardgecodeerd.

`CLAUDE.md` belooft het al: "Geheime classificatie-logica bestaat niet. Alle prompts staan
versiegestuurd in `src/iso_audit/classification/prompts/<versie>.md`." Tot 2026-08-24 bestond
die map niet en stonden de prompts als tripelquoted strings in `findings.py`. Wat er wél was:
`classifications.prompt_versie` bewaart een sha256 van de systeemprompt, dus achteraf is te zien
**dát** de prompt veranderde — niet wat er stond.

Voor een audittool is dat het verschil tussen een spoor en een spoor dat je kunt lezen. De
prompt bepaalt of iets een NC of een OFI wordt; die moet net zo navolgbaar zijn als de bevinding
zelf.

Deze tests dwingen twee dingen af: de prompts staan in bestanden, en de NC/OFI-definitie in die
bestanden is de formele ISO-definitie en niet "geen bewijs gevonden".
"""

from __future__ import annotations

from pathlib import Path

import pytest

PROMPTMAP = Path("src/iso_audit/classification/prompts")


def _promptbestanden() -> list[Path]:
    """De prompts zelf; `README.md` beschrijft de map en is er geen."""
    return sorted(p for p in PROMPTMAP.glob("*.md") if p.name != "README.md")


def test_de_promptmap_bestaat_en_is_gevuld() -> None:
    assert PROMPTMAP.is_dir(), f"{PROMPTMAP} ontbreekt terwijl CLAUDE.md hem belooft"
    assert _promptbestanden(), "geen versiegestuurde prompts gevonden"


def test_de_prompts_staan_niet_meer_hardgecodeerd() -> None:
    """Gate: geen tripelquoted systeemprompt in `findings.py`.

    Zonder deze test kruipt een prompt terug de code in bij de eerste haast, en dan lopen het
    bestand en wat er echt naar het model gaat uiteen — een tweede administratie op de plek
    waar het oordeel valt.
    """
    bron = Path("src/iso_audit/classification/findings.py").read_text(encoding="utf-8")
    assert "_SYSTEM_SCHERP = \"\"\"" not in bron
    assert "_SYSTEM_GENUANCEERD = \"\"\"" not in bron


@pytest.mark.parametrize("bestand", _promptbestanden(), ids=lambda p: p.name)
def test_elke_prompt_definieert_nc_als_bewezen_tekortkoming(bestand: Path) -> None:
    """NC is een **bewezen** tekortkoming, geen ontbrekend bewijs.

    De oude scherpe prompt zei: "NC: er is geen of onvoldoende bewijs; de eis is niet
    aantoonbaar gedekt". Dat maakt van elk document dat een clausule niet noemt een NC — en zo
    werden het er 387 in de run van 2026-08-24, waar de auditor er in het handgemaakte Q2-memo
    twee overhield.

    De formele definitie: een NC is een aangetoonde tekortkoming ten opzichte van een eis. Geen
    bewijs in één document toont niets aan; het betekent dat dít document er niets over zegt.
    """
    tekst = bestand.read_text(encoding="utf-8").lower()
    assert "bewezen" in tekst or "aangetoond" in tekst, (
        f"{bestand.name} definieert NC niet als bewezen tekortkoming"
    )
    assert "geen of onvoldoende bewijs" not in tekst, (
        f"{bestand.name} bevat nog de oude NC-definitie die van ontbrekend bewijs een NC maakt"
    )


@pytest.mark.parametrize("bestand", _promptbestanden(), ids=lambda p: p.name)
def test_elke_prompt_definieert_ofi_als_voldoet_maar_kan_beter(bestand: Path) -> None:
    """OFI betekent dat de eis **wél** wordt gehaald.

    Dat is het punt waarop de oude prompts het meest afweken: daar was OFI "de eis is
    gedeeltelijk gedekt". Gedeeltelijk gedekt is volgens de formele definitie een **kleine
    non-conformiteit**, geen verbeterkans — en dat verschil bepaalt of iemand iets moet
    corrigeren of mag negeren.
    """
    tekst = bestand.read_text(encoding="utf-8").lower()
    assert "voldoet" in tekst, f"{bestand.name} zegt niet dat de eis bij een OFI wordt gehaald"
    assert "vrijblijvend" in tekst or "optioneel" in tekst, (
        f"{bestand.name} zegt niet dat opvolging van een OFI optioneel is"
    )


@pytest.mark.parametrize("bestand", _promptbestanden(), ids=lambda p: p.name)
def test_elke_prompt_onderscheidt_major_en_minor(bestand: Path) -> None:
    """Een NC die certificering blokkeert is iets anders dan een losse misser."""
    tekst = bestand.read_text(encoding="utf-8").lower()
    assert "major" in tekst and "minor" in tekst, (
        f"{bestand.name} maakt geen onderscheid tussen een major en een minor NC"
    )


@pytest.mark.parametrize("bestand", _promptbestanden(), ids=lambda p: p.name)
def test_elke_prompt_eist_een_onderbouwing_bij_een_nc(bestand: Path) -> None:
    """Een NC moet uitleggen wát is aangetoond en waaruit.

    De formele definitie vraagt om correctie, root-cause-analyse en formele verificatie. Dat
    kan niemand zonder te weten welke eis niet gehaald wordt, waaruit dat blijkt, en wat er in
    de praktijk misgaat. In de run van 2026-08-24 hadden 55 bevindingen een lege beschrijving
    én een lege onderbouwing — een oordeel zonder inhoud dat wel meetelde in het rapport.

    Een NC zonder onderbouwing is geen bevinding maar een verdenking.
    """
    tekst = bestand.read_text(encoding="utf-8").lower()
    assert "onderbouwing" in tekst
    assert "verplicht" in tekst or "moet" in tekst, (
        f"{bestand.name} maakt de onderbouwing bij een NC niet verplicht"
    )


@pytest.mark.parametrize("bestand", _promptbestanden(), ids=lambda p: p.name)
def test_geen_oordeel_is_een_geldige_uitkomst(bestand: Path) -> None:
    """Een document dat over iets anders gaat, toont geen tekortkoming aan.

    Zonder deze uitweg moet het model kiezen tussen NC, OFI en positief voor elk document-
    clausulepaar dat de zoektermen opleverden — en dan wordt "dit gaat er niet over" een
    oordeel. Dat is de mechaniek achter 6,8 bevindingen per document.
    """
    tekst = bestand.read_text(encoding="utf-8").lower()
    assert "null" in tekst, f"{bestand.name} biedt geen uitweg voor 'hier valt niets over te zeggen'"


@pytest.mark.parametrize("bestand", _promptbestanden(), ids=lambda p: p.name)
def test_minor_is_de_standaard_en_major_de_uitzondering(bestand: Path) -> None:
    """Major mag niet de default worden, en dat werd hij wel.

    De eerste run met major/minor gaf **71 major tegen 8 minor**. Dat kan niet: major betekent
    dat het proces organisatiebreed afwezig of gebroken is. Wat er stond was "Minor — een op
    zichzelf staande misser", geformuleerd als de uitzondering — en dan kiest een model bij
    twijfel de andere.

    Dieper zit dat het oordeel per document valt: uit één tool-ontwerpdocument volgt niet dat
    de organisatie geen classificatieschema heeft. Zolang dat zo is, kan major daar niet uit
    volgen. Eén oordeel per clausule over al het bewijs heen is
    `openspec/changes/autonome-review/`.
    """
    # Witruimte normaliseren: de prompts breken regels af, dus een letterlijke substring
    # zou op een regeleinde stuklopen en dan toetst de test de opmaak in plaats van de regel.
    tekst = " ".join(bestand.read_text(encoding="utf-8").lower().split())
    assert "standaardkeuze" in tekst, (
        f"{bestand.name} maakt minor niet de standaard; dan wordt major de default"
    )
    assert "bij twijfel altijd minor" in tekst, f"{bestand.name} mist de twijfelregel"
