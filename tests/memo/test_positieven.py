"""Positieve waarnemingen komen gebundeld in de memo, één zin per thema.

Een memo die alleen gebreken opsomt geeft een scheef beeld: een externe auditor wil zien wát
werkt, niet alleen wat niet werkt. Eén zin per thema is genoeg — wie meer wil weten, heeft de
bewijslast.

De rand die deze tests bewaken is dat er niets stils gebeurt: een positieve uitspraak in een
managementmemo is een uitspraak waar de organisatie op wordt aangesproken, dus staat er alleen
bevestigd materiaal in, en de notitie zegt wat er buiten viel.
"""

from __future__ import annotations

from iso_audit.memo.groepering import groepeer_positief
from iso_audit.memo.models import Finding


def _pos(nr: int, thema: str | None, status: str = "valide", kern: str = "") -> Finding:
    return Finding(
        id=f"p{nr}",
        severity="POSITIVE",
        standard="iso-27001-2022",
        clause=f"A.5.{nr}",
        title=f"Waarneming {nr}",
        description="…",
        thema=thema,
        kern=kern,
        triage_status=status,  # type: ignore[arg-type]
    )


def test_bundelt_op_thema_grootste_eerst() -> None:
    findings = [_pos(1, "Toegangsbeheer"), _pos(2, "Toegangsbeheer"), _pos(3, "Beleid")]
    groepen = groepeer_positief(findings)
    assert [(g.thema, len(g.bevindingen)) for g in groepen] == [
        ("Toegangsbeheer", 2),
        ("Beleid", 1),
    ]


def test_alleen_bevestigde_waarnemingen() -> None:
    """Een memo die zegt dat iets op orde is, hoort te rusten op een bevestiging."""
    findings = [_pos(1, "Toegangsbeheer", status="open"), _pos(2, "Toegangsbeheer")]
    groepen = groepeer_positief(findings)
    assert len(groepen) == 1
    assert [f.id for f in groepen[0].bevindingen] == ["p2"]


def test_zonder_thema_geen_los_blok() -> None:
    """`Overig` clustert niet en krijgt ook geen losse regels — dat maakt een memo alleen langer."""
    assert groepeer_positief([_pos(1, None), _pos(2, "")]) == []


def test_ncs_en_ofis_komen_hier_niet_in() -> None:
    nc = _pos(1, "Toegangsbeheer").model_copy(update={"severity": "NC"})
    ofi = _pos(2, "Toegangsbeheer").model_copy(update={"severity": "OFI"})
    assert groepeer_positief([nc, ofi]) == []


def test_de_zin_komt_uit_de_review_als_die_er_is() -> None:
    from iso_audit.memo.builder import _positieve_zin

    groep = groepeer_positief([_pos(1, "Beleid", kern="Het beleid is vastgesteld en bekend.")])[0]
    assert _positieve_zin(groep) == "Het beleid is vastgesteld en bekend."


def test_zonder_review_een_natrekbare_zin_en_geen_lofzang() -> None:
    """Feiten die je kunt nalopen, geen oordeel dat niemand heeft geveld."""
    from iso_audit.memo.builder import _positieve_zin

    groep = groepeer_positief([_pos(1, "Beleid"), _pos(2, "Beleid")])[0]
    zin = _positieve_zin(groep)
    assert "2 bevestigde waarnemingen" in zin
    assert "2 clausules" in zin
    assert "bewijslast" in zin
    for lofzang in ("uitstekend", "voorbeeldig", "volwassen", "sterk"):
        assert lofzang not in zin.lower()


def test_enkelvoud_leest_als_nederlands() -> None:
    from iso_audit.memo.builder import _positieve_zin

    groep = groepeer_positief([_pos(1, "Beleid")])[0]
    assert "1 bevestigde waarneming op 1 clausule" in _positieve_zin(groep)


def test_de_notitie_benoemt_wat_er_buiten_viel() -> None:
    """Een sectie die zwijgt over wat er niet in staat, leest als 'dit was alles'."""
    from iso_audit.memo.builder import _positieve_notitie

    findings = [
        _pos(1, "Beleid"),
        _pos(2, "Beleid"),
        _pos(3, "Toegangsbeheer", status="open"),
        _pos(4, None),
    ]
    notitie = _positieve_notitie(findings, groepeer_positief(findings))
    assert "1 positieve waarneming(en) zijn nog niet bevestigd" in notitie
    assert "1 bevestigde waarneming(en) vielen buiten een thema" in notitie
    assert "bewijslast" in notitie


def test_de_notitie_verlaagt_geen_hoofdletters() -> None:
    """`capitalize()` maakte van "Alle" "alle" — en zou een themanaam verminken."""
    from iso_audit.memo.builder import _positieve_notitie

    findings = [_pos(1, "Beleid"), _pos(2, "Toegangsbeheer", status="open")]
    assert "Alle waarnemingen staan in de bewijslast." in _positieve_notitie(
        findings, groepeer_positief(findings)
    )


def test_zonder_positieven_geen_notitie() -> None:
    from iso_audit.memo.builder import _positieve_notitie

    assert _positieve_notitie([], []) == ""


# --- Rendering: het model is pas iets waard als het in de PDF terechtkomt -------------------


def _memo_met_positieven(blokken: list[object], notitie: str = "") -> object:
    from iso_audit.memo.models import AuditMemo, MemoContext

    return AuditMemo(
        title="Auditmemo — Test",
        subtitle="Mark | ISO-auditor · Q3 2026",
        date="31-08-2026",
        version="v1",
        lead_summary="Samenvatting.",
        context=MemoContext(
            audit_cycle="Q3 2026",
            scope={"ISO 27001:2022": "§4-10 + Bijlage A"},
            sources=["Google Drive"],
            dataset_counts={"NC": 0, "OFI": 0, "positief": 3},
            scope_caveat="Tool zag alleen Drive.",
        ),
        nc_blocks=[],
        improvements=[],
        positives=blokken,  # type: ignore[arg-type]
        positives_note=notitie,
        historical_ncs=[],
        detail_report_ref="detail.pdf",
    )


def _profiel() -> object:
    from iso_audit.memo.theme.profile import Profile

    return Profile(
        schema_version=1,
        slug="conduction",
        organization={"name": "Conduction B.V."},
        auditor={"name": "Mark", "role": "ISO-auditor"},
        brand={
            "logo_svg": '<svg viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>',
            "colors": {"primary": "#4376fc"},
        },
    )


def test_de_positieve_sectie_komt_in_de_html() -> None:
    from iso_audit.memo.models import ClauseCitation, PositiveBlock
    from iso_audit.memo.renderer.html import MemoRendererImpl

    blok = PositiveBlock(
        code="POS 1",
        title="Toegangsbeheer",
        citations=[
            ClauseCitation(
                standard="ISO 27001:2022", clause="A.5.15", title="Toegangsbeheer", text="…"
            )
        ],
        kern="4 bevestigde waarnemingen op 3 clausules; geen afwijkingen aangetroffen.",
        aantal=4,
    )
    html = MemoRendererImpl().render_html(
        _memo_met_positieven([blok], "1 waarneming viel buiten een thema."),  # type: ignore[arg-type]
        _profiel(),  # type: ignore[arg-type]
    )
    assert "Wat aantoonbaar op orde is" in html
    assert "POS 1" in html and "Toegangsbeheer" in html
    assert "4 bevestigde waarnemingen op 3 clausules" in html
    assert "A.5.15" in html
    assert "1 waarneming viel buiten een thema." in html


def test_zonder_positieven_geen_lege_kop() -> None:
    """Een kop zonder inhoud kost een lezer aandacht en levert niets."""
    from iso_audit.memo.renderer.html import MemoRendererImpl

    html = MemoRendererImpl().render_html(
        _memo_met_positieven([]),  # type: ignore[arg-type]
        _profiel(),  # type: ignore[arg-type]
    )
    assert "Wat aantoonbaar op orde is" not in html
