"""De memo toont wat de auditor heeft bevestigd — niet een selectie die het tool zelf maakt.

Op 26-08-2026 bevestigde de auditor 47 NC's en werd de memo 27 pagina's. Kort daarna stond hier
een bovengrens van drie blokken. Die is er weer uit, en de reden is belangrijker dan de
paginatelling: zo'n grens laat NC's buiten de memo vallen op **omvang**, zonder dat een mens
erover besliste en zonder vastgelegde reden.

Wat niet in de memo thuishoort, wordt in de **triage** uitgesloten. Daar legt de append-only
trail vast wie dat besloot en waarom. De memo is dan een gevolg van auditor-beslissingen in
plaats van een keuze van het tool — dat is de auditor-spiegel, en die weegt zwaarder dan een
paginatelling.

Wat wél blijft: de volgorde. Zwaarte vóór omvang, zodat een lezer die na één blok stopt het
zwaarste heeft gezien.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from iso_audit.memo.builder import build_memo
from iso_audit.memo.models import Finding, MemoInput
from iso_audit.memo.norm_lookup import laad_norm_db
from iso_audit.memo.theme.profile import laad_profiel

_EX = Path("examples/auditmemo")
_CLAUSULES = [f"8.{n}" for n in range(1, 25)]


def _nc(index: int, thema: str, ernst: str = "") -> Finding:
    return Finding(
        id=f"nc{index}",
        severity="NC",
        standard="iso-27001-2022",
        clause=_CLAUSULES[index],
        title=f"§{_CLAUSULES[index]}",
        description="beschrijving",
        deviation=f"afwijking {index}",
        thema=thema,
        ernst=ernst,
        triage_status="valide",
    )


def _memo(findings: list[Finding]):
    ruw = (_EX / "memo-input.yaml").read_text(encoding="utf-8")
    return build_memo(
        findings=findings,
        historical_ncs=[],
        profile=laad_profiel(str(_EX / "conduction.profile.yaml")),
        norm_db=laad_norm_db("examples/norms"),
        memo_input=MemoInput(**yaml.safe_load(ruw)),
    )


def _vijf_themas() -> list[Finding]:
    fs: list[Finding] = []
    for n in range(5):
        fs += [_nc(n * 3 + i, f"Thema {n}") for i in range(3)]
    return fs


def test_elk_bevestigd_thema_komt_in_de_memo() -> None:
    """Geen bovengrens: uitsluiten hoort in de triage, met een vastgelegde reden."""
    assert len(_memo(_vijf_themas()).nc_blocks) == 5


def test_de_grootste_themas_staan_bovenaan() -> None:
    """Daar ligt het meeste bewijs; een lezer die na één blok stopt heeft het zwaarste gezien."""
    fs = [_nc(i, "Groot") for i in range(6)]
    fs += [_nc(6 + i, "Middel") for i in range(4)]
    fs += [_nc(10 + i, "Klein") for i in range(3)]
    fs += [_nc(13 + i, "Kleiner") for i in range(2)]
    assert [b.title for b in _memo(fs).nc_blocks][:3] == ["Groot", "Middel", "Klein"]


def test_een_major_gaat_voor_op_omvang() -> None:
    """Een zware bevinding hoort in de memo, ook als zijn thema klein is.

    Op de werkset van 26-08 was `ernst` op alle 47 leeg omdat de review er niet over gelopen was;
    dan valt dit terug op omvang. Zodra de review draait, telt zwaarte eerst.
    """
    fs = [_nc(i, "Groot maar licht") for i in range(6)]
    fs += [_nc(6 + i, "Klein maar zwaar", ernst="major") for i in range(2)]
    assert _memo(fs).nc_blocks[0].title == "Klein maar zwaar"


def test_een_uitgesloten_nc_haalt_de_memo_niet() -> None:
    """Dit is de plek waar weglaten hoort: de triage, met een reden in de trail."""
    fs = _vijf_themas()
    for f in fs[3:]:
        f.triage_status = "niet_valide"
    memo = _memo(fs)
    assert [b.title for b in memo.nc_blocks] == ["Thema 0"]


def test_een_follow_up_haalt_de_memo_ook_niet() -> None:
    """Bewijs buiten tool-scope: nog geen bevestigde NC, dus nog geen memo-blok."""
    fs = _vijf_themas()
    for f in fs:
        f.triage_status = "follow_up"
    assert _memo(fs).nc_blocks == []
