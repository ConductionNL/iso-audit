"""Drie eisen aan de memo als bespreekstuk, gemeld door de auditor op 2026-08-26.

1. **Bronnen met een identificatie.** "Geraadpleegde bronnen: Google Drive, Jira, Planning,
   Nextcloud" zegt niets. Wélke Drive-map, wélk Jira-project? Zonder die aanduiding kan een
   externe auditor de scope van de audit niet natrekken, en is de zin decoratie.

2. **Blokken met een code.** "NC 1 — Back-up & continuïteit", niet alleen het thema. Zo is het
   memo-blok aan te wijzen in een vergadering en terug te vinden in het detailrapport. Precies
   zoals het handgemaakte Q2-memo het deed.

3. **Kort genoeg om te bespreken.** Een managementmemo is 1-3 A4. De bijlage mag lang zijn en er
   mag naar verwezen worden — normtekst, onderbouwing en de volledige bronlijst horen daar.
   In de memo staat wat het is, waarom, wie er wat aan doet en voor wanneer.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from iso_audit.memo.builder import build_memo
from iso_audit.memo.models import ActionRow, BronRef, Finding, MemoInput
from iso_audit.memo.norm_lookup import laad_norm_db
from iso_audit.memo.theme.profile import laad_profiel

_EX = Path("examples/auditmemo")


def _nc(clausule: str, thema: str, kern: str = "Het gebrek in één zin.") -> Finding:
    return Finding(
        id=f"nc-{clausule}",
        severity="NC",
        standard="iso-27001-2022",
        clause=clausule,
        title=f"§{clausule}",
        description="beschrijving",
        deviation=f"afwijking op {clausule}",
        thema=thema,
        kern=kern,
        triage_status="valide",
        corrective_measure="Stel het beheer vast en toets het.",
        bronnen=[BronRef(herkomst="Drive", doc_id=f"d{clausule}", doc_naam=f"{clausule}.docx")],
        actions=[ActionRow(wat=f"actie {clausule}", wie="CISO", uiterlijk="2026-10-01")],
    )


def _ofi(clausule: str, thema: str) -> Finding:
    return Finding(
        id=f"ofi-{clausule}",
        severity="OFI",
        standard="iso-27001-2022",
        clause=clausule,
        title=f"§{clausule}",
        description="waarneming",
        thema=thema,
        suggestion=f"suggestie {clausule}",
    )


def _memo(findings: list[Finding], context: dict[str, object] | None = None):
    ruw = yaml.safe_load((_EX / "memo-input.yaml").read_text(encoding="utf-8"))
    if context:
        ruw["context"] = {**ruw.get("context", {}), **context}
    return build_memo(
        findings=findings,
        historical_ncs=[],
        profile=laad_profiel(str(_EX / "conduction.profile.yaml")),
        norm_db=laad_norm_db("examples/norms"),
        memo_input=MemoInput(**ruw),
    )


# --- 1. bronnen met identificatie -------------------------------------------


def test_een_bron_met_url_houdt_zijn_url() -> None:
    memo = _memo(
        [], context={"sources": [{"naam": "Google Drive", "url": "https://drive.example/1"}]}
    )
    assert memo.context is not None
    assert memo.context.sources[0].url == "https://drive.example/1"


def test_een_bron_als_kale_tekst_blijft_werken() -> None:
    """Bestaande memo-input.yaml-bestanden hebben een lijst strings; die mogen niet breken."""
    memo = _memo([], context={"sources": ["Google Drive"]})
    assert memo.context is not None
    assert memo.context.sources[0].naam == "Google Drive"
    assert memo.context.sources[0].url is None


def test_de_identificatie_komt_in_de_gerenderde_memo() -> None:
    from iso_audit.memo.renderer.html import MemoRendererImpl

    memo = _memo(
        [], context={"sources": [{"naam": "Google Drive", "url": "https://drive.example/1"}]}
    )
    html = MemoRendererImpl().render_html(memo, laad_profiel(str(_EX / "conduction.profile.yaml")))
    assert "https://drive.example/1" in html


# --- 2. codes voor de blokken -----------------------------------------------


def test_nc_blokken_zijn_genummerd() -> None:
    memo = _memo([_nc("8.14", "Continuïteit"), _nc("5.12", "Informatieclassificatie")])
    assert [b.code for b in memo.nc_blocks] == ["NC 1", "NC 2"]


def test_verbeterblokken_krijgen_een_ofi_code() -> None:
    fs = [
        _ofi("8.15", "Logging & monitoring"),
        _ofi("8.16", "Logging & monitoring"),
        _ofi("8.17", "Logging & monitoring"),
    ]
    assert [b.code for b in _memo(fs).improvements] == ["OFI 1"]


def test_de_code_staat_in_de_gerenderde_kop() -> None:
    from iso_audit.memo.renderer.html import MemoRendererImpl

    memo = _memo([_nc("8.14", "Back-up & continuïteit")])
    html = MemoRendererImpl().render_html(memo, laad_profiel(str(_EX / "conduction.profile.yaml")))
    assert "NC 1 — Back-up &amp; continuïteit" in html or "NC 1 — Back-up & continuïteit" in html


# --- 3. kort genoeg om te bespreken -----------------------------------------


def test_de_memo_citeert_de_normtekst_niet_meer() -> None:
    """Normtekst is bijlage-materiaal; de clausuleverwijzing blijft."""
    from iso_audit.memo.renderer.html import MemoRendererImpl

    memo = _memo([_nc("8.14", "Back-up & continuïteit")])
    html = MemoRendererImpl().render_html(memo, laad_profiel(str(_EX / "conduction.profile.yaml")))
    assert "norm-quote" not in html
    assert "8.14" in html


def test_zes_ncs_over_twee_themas_passen_in_drie_a4(tmp_path: Path) -> None:
    """Het formaat van het handgemaakte Q2-memo: twee blokken van drie clausules."""
    from iso_audit.memo.renderer.html import MemoRendererImpl

    fs = [_nc(c, "Back-up & continuïteit") for c in ("8.14", "5.29", "5.30")]
    fs += [_nc(c, "Toegangsbeheer") for c in ("8.2", "8.5", "5.17")]
    profiel = laad_profiel(str(_EX / "conduction.profile.yaml"))
    r = MemoRendererImpl()
    budget = r.render_pdf(r.render_html(_memo(fs), profiel), tmp_path / "memo.pdf")
    assert budget.past, f"{budget.paginas} pagina's: {budget.melding}"
