"""Dashboard-overzicht: één regel per audit, volledig afgeleid uit de bestanden.

De vier kolommen die de eigenaar vroeg — norm+periode met status, triage-voortgang en
of de memo klaar is, geraadpleegde bronnen, en wie er als laatste aan werkte — komen
alle uit `audit.json`, `findings.json`, `runs.jsonl` en de staart van
`triage_log.jsonl`.

**Status wordt berekend, nooit opgeslagen.** Een los statusveld gaat op termijn liegen
tegen de bestanden, en in een auditwerktuig is een veld dat liegt erger dan een
berekening die een fractie langzamer is.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from iso_audit.api import runs as runs_mod
from iso_audit.api.registry import (
    FINDINGS,
    MANIFEST,
    TRAIL,
    AuditOverzicht,
    AuditRegistry,
)

MEMO_BESTAND = "Auditmemo_management.pdf"

STATUS_NIEUW = "nieuw"
STATUS_LOOPT = "loopt"
STATUS_MEMO_KLAAR = "memo-klaar"

_OPEN_TRIAGE = "open"
"""`Finding.triage_status` waarde die als 'nog te doen' geldt."""


def _laad_json(pad: Path, default: Any) -> Any:
    if not pad.is_file():
        return default
    try:
        return json.loads(pad.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _laatste_trail_regel(pad: Path) -> dict[str, Any] | None:
    """Laatste geldige regel uit de append-only trail, of ``None``.

    Leest het hele bestand: de trail van één audit is klein (één regel per
    veldwijziging) en achteruit seeken voor een paar kilobyte is complexiteit zonder
    winst.
    """
    if not pad.is_file():
        return None
    laatste: dict[str, Any] | None = None
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel:
            continue
        try:
            laatste = json.loads(regel)
        except json.JSONDecodeError:
            continue
    return laatste


def _telling(findings: list[dict[str, Any]]) -> tuple[int, int]:
    """``(totaal, open)`` — open is alles wat nog op de default triage-status staat."""
    totaal = len(findings)
    openstaand = sum(
        1 for f in findings if str(f.get("triage_status", _OPEN_TRIAGE)) == _OPEN_TRIAGE
    )
    return totaal, openstaand


def _status(aantal_runs: int, openstaand: int, memo_klaar: bool) -> str:
    if aantal_runs == 0:
        return STATUS_NIEUW
    if openstaand == 0 and memo_klaar:
        return STATUS_MEMO_KLAAR
    return STATUS_LOOPT


def regel(audit_dir: Path) -> AuditOverzicht:
    """Bouw één dashboard-regel voor de audit in ``audit_dir``."""
    manifest: dict[str, Any] = _laad_json(audit_dir / MANIFEST, {})
    findings: list[dict[str, Any]] = _laad_json(audit_dir / FINDINGS, [])
    totaal, openstaand = _telling(findings)
    aantal_runs = runs_mod.som(audit_dir)
    memo_klaar = (audit_dir / MEMO_BESTAND).is_file()
    laatste = _laatste_trail_regel(audit_dir / TRAIL)

    return AuditOverzicht(
        id=str(manifest.get("id", audit_dir.name)),
        normen=[str(n) for n in manifest.get("normen", [])],
        periode=str(manifest.get("periode", "")),
        status=_status(aantal_runs, openstaand, memo_klaar),
        bevindingen=totaal,
        triage_open=openstaand,
        memo_klaar=memo_klaar,
        bronnen=runs_mod.geraadpleegde_bronnen(audit_dir),
        laatste_actor=str(laatste["actor"]) if laatste and "actor" in laatste else None,
        laatste_wijziging=str(laatste["timestamp"]) if laatste and "timestamp" in laatste else None,
        runs=aantal_runs,
    )


def alles(registry: AuditRegistry) -> list[AuditOverzicht]:
    """Alle audits, nieuwste periode eerst.

    Audits zónder run staan er ook in: een aangemaakte audit is een geldige toestand
    ("nog te starten") en hem verbergen tot er data is maakt het overzicht
    onbetrouwbaar als werklijst.
    """
    if not registry.root.is_dir():
        return []
    regels = [
        regel(d) for d in sorted(registry.root.iterdir()) if d.is_dir() and (d / MANIFEST).is_file()
    ]
    # Periode aflopend, dan norm — `2026-Q3` sorteert lexicografisch correct.
    return sorted(regels, key=lambda r: (r.periode, r.normen), reverse=True)
