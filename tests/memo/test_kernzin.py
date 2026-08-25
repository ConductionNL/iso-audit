"""De synthese-alinea uit de review komt in het NC-blok terecht.

Het handgemaakte Q2-memo heeft per NC één zin die zegt wat het gemeenschappelijke gebrek is:
"Drie clausules, één hoofdgebrek: er is geen gedocumenteerd en getest continuïteitsbeheer."
Dat is wat een memo van drie A4 leesbaar maakt — zonder die zin is het een opsomming van
citaten.

De review produceert precies zo'n zin per clausule (`kern`). Deze test legt vast dat hij ook
in de memo terechtkomt, want een kernzin die alleen in de trail staat helpt niemand.
"""

from __future__ import annotations

from iso_audit.memo.models import Finding, NCBlock


def _finding(**kw: object) -> Finding:
    basis: dict[str, object] = {
        "id": "nc-8.14",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.14",
        "title": "Bedrijfscontinuïteit",
        "description": "Geen getest continuïteitsplan.",
        "triage_status": "valide",
    }
    basis.update(kw)
    return Finding(**basis)  # type: ignore[arg-type]


def test_een_finding_kan_een_kernzin_dragen() -> None:
    f = _finding(kern="Drie clausules, één hoofdgebrek: geen getest continuïteitsbeheer.")
    assert f.kern.startswith("Drie clausules")


def test_zonder_kernzin_blijft_het_veld_leeg() -> None:
    """Leeg en geen placeholder: een verzonnen synthese is erger dan geen synthese."""
    assert _finding().kern == ""


def test_het_nc_blok_neemt_de_kernzin_over() -> None:
    blok = NCBlock(
        title="NC 1",
        citations=[],
        deviation="afwijking",
        corrective_measure="maatregel",
        kern="Eén hoofdgebrek.",
    )
    assert blok.kern == "Eén hoofdgebrek."


def test_het_nc_blok_mag_zonder_kernzin() -> None:
    """Bestaande memo's zonder review moeten blijven werken."""
    blok = NCBlock(title="NC 1", citations=[], deviation="a", corrective_measure="b")
    assert blok.kern == ""


def test_de_kernzin_staat_in_de_gerenderde_memo() -> None:
    """Een kernzin die alleen in het model staat, helpt de lezer niet."""
    from pathlib import Path

    partial = Path("src/iso_audit/memo/templates/management-memo/partials/nc.html.j2")
    inhoud = partial.read_text(encoding="utf-8")
    assert "nc.kern" in inhoud


def test_de_kernzin_staat_vóór_de_details() -> None:
    """Eerst de conclusie, dan de onderbouwing — anders leest een NC-blok als een bijlage."""
    from pathlib import Path

    inhoud = Path("src/iso_audit/memo/templates/management-memo/partials/nc.html.j2").read_text(
        encoding="utf-8"
    )
    assert inhoud.index("nc.kern") < inhoud.index("nc.deviation")
