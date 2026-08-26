"""Verbeterpunten bundelen per thema, net als de NC's.

Twee dingen die niet werkten, gemeten op de werkset van 2026-08-25:

1. **Er kwam geen enkel verbeterpunt uit.** De selectie clusterde op *clausule* met drempel 10;
   geen enkele clausule haalde dat. De 53 OFI's verdeelden zich over 16 thema's — waar de
   patronen wél zichtbaar zijn: 7x logging & monitoring, 6x auditprogramma, 4x back-up.
2. **Eén representant per cluster.** Van drie waarnemingen op hetzelfde thema kwam er één in de
   memo en verdwenen er twee. Dat maakt van een patroon een anekdote.

Nu: een thema met genoeg OFI's wordt één verbeterblok met álle waarnemingen erin, en de drempel
telt thema's in plaats van clausules. Drie losse waarnemingen op hetzelfde thema zijn een
patroon; één is een waarneming, en die hoort in het detailrapport.

`Overig` clustert nooit — dat is geen thema maar het ontbreken ervan, en drie ongerelateerde
punten als één verbeteradvies presenteren is precies de suggestie die je niet wilt wekken.
"""

from __future__ import annotations

from iso_audit.memo.models import BronRef, Finding


def _ofi(fid: str, clausule: str, thema: str, *, promote: bool = False, kern: str = "") -> Finding:
    return Finding(
        id=fid,
        severity="OFI",
        standard="iso-27001-2022",
        clause=clausule,
        title=f"§{clausule}",
        description=f"waarneming op {clausule}",
        thema=thema,
        kern=kern,
        promote_to_improvement=promote,
        suggestion=f"suggestie voor {clausule}",
        bronnen=[BronRef(herkomst="Drive", doc_id=f"d{fid}", doc_naam=f"{fid}.docx")],
    )


def _blokken(findings: list[Finding], drempel: int = 3) -> list:
    from pathlib import Path

    import yaml

    from iso_audit.memo.builder import build_memo
    from iso_audit.memo.models import MemoInput
    from iso_audit.memo.norm_lookup import laad_norm_db
    from iso_audit.memo.theme.profile import laad_profiel

    ruw = Path("examples/auditmemo/memo-input.yaml").read_text(encoding="utf-8")
    memo = build_memo(
        findings=findings,
        historical_ncs=[],
        profile=laad_profiel("examples/auditmemo/conduction.profile.yaml"),
        norm_db=laad_norm_db("examples/norms"),
        memo_input=MemoInput(**yaml.safe_load(ruw)),
        threshold=drempel,
    )
    return memo.improvements


def test_een_thema_met_genoeg_ofis_wordt_een_verbeterblok() -> None:
    fs = [
        _ofi("1", "8.15", "Logging & monitoring"),
        _ofi("2", "8.16", "Logging & monitoring"),
        _ofi("3", "8.17", "Logging & monitoring"),
    ]
    blokken = _blokken(fs)
    assert len(blokken) == 1
    assert blokken[0].title == "Logging & monitoring"


def test_het_blok_houdt_alle_waarnemingen_en_niet_een_representant() -> None:
    """Van drie waarnemingen één tonen maakt van een patroon een anekdote."""
    fs = [
        _ofi("1", "8.15", "Logging & monitoring"),
        _ofi("2", "8.16", "Logging & monitoring"),
        _ofi("3", "8.17", "Logging & monitoring"),
    ]
    blokken = _blokken(fs)
    assert sorted(c.clause for c in blokken[0].citations) == ["8.15", "8.16", "8.17"]
    assert {b.doc_naam for b in blokken[0].bronnen} == {"1.docx", "2.docx", "3.docx"}


def test_een_thema_onder_de_drempel_haalt_de_memo_niet() -> None:
    fs = [_ofi("1", "8.15", "Logging & monitoring"), _ofi("2", "8.16", "Logging & monitoring")]
    assert _blokken(fs) == []


def test_de_drempel_telt_themas_en_niet_clausules() -> None:
    """Drie OFI's op drie verschillende clausules van één thema is een patroon.

    Onder de oude clausule-drempel telde dit als 1+1+1 en haalde het niets.
    """
    fs = [
        _ofi("1", "8.15", "Back-up & continuïteit"),
        _ofi("2", "5.29", "Back-up & continuïteit"),
        _ofi("3", "5.30", "Back-up & continuïteit"),
    ]
    assert len(_blokken(fs)) == 1


def test_overig_clustert_nooit() -> None:
    fs = [_ofi(str(i), f"8.{i}", "") for i in range(1, 6)]
    assert _blokken(fs) == []


def test_een_expliciet_gepromote_ofi_komt_er_altijd_in() -> None:
    """Ook alleen: de auditor heeft er zelf voor getekend."""
    assert len(_blokken([_ofi("1", "8.15", "Toegangsbeheer", promote=True)])) == 1


def test_een_gepromote_ofi_verdubbelt_zijn_thema_niet() -> None:
    fs = [
        _ofi("1", "8.15", "Logging & monitoring", promote=True),
        _ofi("2", "8.16", "Logging & monitoring"),
        _ofi("3", "8.17", "Logging & monitoring"),
    ]
    blokken = _blokken(fs)
    assert len(blokken) == 1
    assert len(blokken[0].citations) == 3


def test_drempel_nul_betekent_alleen_expliciete_promotie() -> None:
    fs = [_ofi(str(i), f"8.{i}", "Logging & monitoring") for i in range(1, 6)]
    assert _blokken(fs, drempel=0) == []


def test_met_een_kern_verhuist_het_detail_ook_hier_naar_de_bijlage() -> None:
    """Zelfde regel als bij de NC-blokken; anders groeit het blok mee met zijn omvang."""
    fs = [
        _ofi("1", "8.15", "Logging & monitoring", kern="Logging is niet centraal belegd."),
        _ofi("2", "8.16", "Logging & monitoring"),
        _ofi("3", "8.17", "Logging & monitoring"),
    ]
    blokken = _blokken(fs)
    assert blokken[0].kern == "Logging is niet centraal belegd."
    assert blokken[0].deviation == ""


def test_de_suggesties_van_alle_waarnemingen_blijven_staan() -> None:
    """Het verbeteradvies is juist waar het om gaat; dat mag niet naar de bijlage."""
    fs = [
        _ofi("1", "8.15", "Logging & monitoring"),
        _ofi("2", "8.16", "Logging & monitoring"),
        _ofi("3", "8.17", "Logging & monitoring"),
    ]
    tekst = _blokken(fs)[0].suggestion or ""
    for clausule in ("8.15", "8.16", "8.17"):
        assert f"suggestie voor {clausule}" in tekst


# --- hoeveel thema's komen er in de memo ------------------------------------

_ECHTE = [f"8.{n}" for n in range(1, 16)]
"""Bestaande 27001-clausules. Verzonnen nummers laat `norm_lookup` terecht falen: een memo mag
geen verzonnen citaat bevatten."""


def _vijf_themas() -> list[Finding]:
    fs: list[Finding] = []
    for n in range(5):
        fs += [_ofi(f"o{n}{i}", _ECHTE[n * 3 + i], f"Thema {n}") for i in range(3)]
    return fs


def test_hoogstens_drie_verbeterblokken_in_de_memo() -> None:
    """Een kwartaal met zeven verbeterrichtingen is geen agenda maar een lijst.

    Twee losse knoppen, en dat onderscheid is het punt: `THEMA_DREMPEL` bepaalt hoe groot een
    thema moet zijn om te tellen (3 waarnemingen), `MAX_VERBETERBLOKKEN` bepaalt hoeveel er in
    de memo komen (3). Op de werkset van 2026-08-25 haalden zeven thema's de drempel.
    """
    assert len(_blokken(_vijf_themas())) == 3


def test_de_grootste_themas_komen_erin() -> None:
    """Daar ligt het meeste bewijs; een lezer die na één blok stopt heeft het zwaarste gezien."""
    fs = [_ofi(f"g{i}", _ECHTE[i], "Groot") for i in range(6)]
    fs += [_ofi(f"m{i}", _ECHTE[6 + i], "Middel") for i in range(4)]
    fs += [_ofi(f"k{i}", _ECHTE[10 + i], "Klein") for i in range(3)]
    fs += [_ofi(f"kl{i}", _ECHTE[i], "Kleiner") for i in range(3)]
    assert [b.title for b in _blokken(fs)] == ["Groot", "Middel", "Klein"]


def _memo(findings: list[Finding], drempel: int = 3):
    from pathlib import Path

    import yaml

    from iso_audit.memo.builder import build_memo
    from iso_audit.memo.models import MemoInput
    from iso_audit.memo.norm_lookup import laad_norm_db
    from iso_audit.memo.theme.profile import laad_profiel

    ruw = Path("examples/auditmemo/memo-input.yaml").read_text(encoding="utf-8")
    return build_memo(
        findings=findings,
        historical_ncs=[],
        profile=laad_profiel("examples/auditmemo/conduction.profile.yaml"),
        norm_db=laad_norm_db("examples/norms"),
        memo_input=MemoInput(**yaml.safe_load(ruw)),
        threshold=drempel,
    )


def test_wat_niet_in_de_memo_komt_wordt_genoemd() -> None:
    """Weglaten zonder het te zeggen is de fout die dit project het vaakst heeft gemaakt.

    Als eigen regel onder de sectie en niet weggestopt in het laatste blok: de lezer moet zien
    dát er meer is, zonder ernaar te zoeken.
    """
    notitie = _memo(_vijf_themas()).improvements_note
    assert "2" in notitie
    assert "detail" in notitie.lower() or "bijlage" in notitie.lower()


def test_de_melding_staat_in_de_gerenderde_memo() -> None:
    from iso_audit.memo.renderer.html import MemoRendererImpl
    from iso_audit.memo.theme.profile import laad_profiel

    html = MemoRendererImpl().render_html(
        _memo(_vijf_themas()), laad_profiel("examples/auditmemo/conduction.profile.yaml")
    )
    assert "2 andere thema" in html


def test_minder_dan_het_maximum_verandert_niets() -> None:
    fs = [_ofi(f"e{i}", _ECHTE[i], "Enige") for i in range(3)]
    memo = _memo(fs)
    assert len(memo.improvements) == 1
    assert memo.improvements_note == ""
