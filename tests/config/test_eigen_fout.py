"""Een fout die wij zelf formuleren, komt ongewijzigd bij de auditor aan.

Op 2026-08-28 koos de auditor hoofdstuk 4 voor ISO 27001 en zag: *"De verbinding kon niet worden
gelegd. Zie het serverlog voor details."* De echte melding stond in het log en was volstrekt
duidelijk: *"Geen clausules gevonden voor hoofdstuk '4'. Beschikbare hoofdstukken: 5, 6, 7, 8."*

De normalisatie die dat verving, bestaat met goede reden: `run()` vangt élke pipeline-fout, ook
die van Google, Jira en Anthropic, en zo'n tekst kan een URL met credential of een tokenfragment
bevatten. Tot 2026-08-14 landde dat rechtstreeks in de browser.

Maar een melding die wij zélf schrijven bevat per definitie geen leveranciersrespons. Die
onderscheiden is niet "een uitzondering maken" maar het verschil tussen een auditor die weet wat
hij moet doen en een auditor die naar een serverlog wordt gestuurd waar hij niet bij kan.

Het onderscheid is het **type**, niet de inhoud: wie een `EigenFoutError` opgooit, verklaart daarmee
dat de tekst van ons is. Op inhoud filteren zou raden zijn.
"""

from __future__ import annotations

from iso_audit.config.verbinding import EigenFoutError, normaliseer


def test_een_eigen_fout_houdt_zijn_tekst() -> None:
    _, tekst = normaliseer(
        EigenFoutError("Geen clausules gevonden voor hoofdstuk '4'. Beschikbaar: 5, 6, 7, 8."),
        bron="pipeline",
    )
    assert "hoofdstuk '4'" in tekst
    assert "5, 6, 7, 8" in tekst
    assert "serverlog" not in tekst


def test_de_soort_zegt_dat_het_configuratie_is() -> None:
    """Zodat de UI hem niet als storing presenteert."""
    soort, _ = normaliseer(EigenFoutError("iets"), bron="pipeline")
    assert soort == "niet_geconfigureerd"


def test_een_vreemde_fout_wordt_nog_steeds_afgeschermd() -> None:
    """De reden dat de normalisatie bestaat, verandert niet."""
    _, tekst = normaliseer(
        RuntimeError("401 from https://x.atlassian.net?token=geheim"), bron="jira"
    )
    assert "geheim" not in tekst
    assert "atlassian" not in tekst


def test_het_hoofdstukfilter_gooit_een_eigen_fout() -> None:
    """Dit was de fout die de auditor zag; hij hoort leesbaar te blijven."""
    import pytest

    from iso_audit.classification.clause_mapping import filter_clause_map

    with pytest.raises(EigenFoutError, match="5, 6, 7, 8"):
        filter_clause_map({"clausules": {"5.1": {}, "6.1": {}, "7.1": {}, "8.1": {}}}, "4")
