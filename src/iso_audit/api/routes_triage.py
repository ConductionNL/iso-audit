"""Triage-routes binnen één audit: bevindingen, beslissingen en de trail.

De actor in de trail is de geverifieerde identiteit uit de auth-gate, niet de default
`"auditor"` op `apply_triage`. Dat was sec-bevinding 1 van change `iso-portal` en het
blijft hier gelden — een append-only trail zonder toewijsbare actor beantwoordt de
eerste vraag van een auditor niet.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from iso_audit.api.deps import Audits
from iso_audit.api.session import SessionError
from iso_audit.memo.models import Finding, Severity, TriageStatus


class TriageUpdate(BaseModel):
    """Reclassificatie/triage en/of redactie van de kop-NC-tekst, met reden."""

    severity: Severity | None = None
    triage_status: TriageStatus | None = None
    title: str | None = None
    deviation: str | None = None
    corrective_measure: str | None = None  # NC: vereiste maatregel
    suggestion: str | None = None  # OFI: aanbeveling
    reason: str = ""


class FindingSummary(BaseModel):
    id: str
    severity: Severity
    clause: str
    title: str
    triage_status: TriageStatus
    source: str | None = None  # bevinding berust op bron Y


def _kort(f: Finding) -> FindingSummary:
    return FindingSummary(
        id=f.id,
        severity=f.severity,
        clause=f.clause,
        title=f.title,
        triage_status=f.triage_status,
        source=f.source,
    )


def _bron_matcht(f: Finding, bron: str | None) -> bool:
    """Deeltekst, hoofdletterongevoelig: de auditor typt "drive", niet het volledige pad."""
    if not bron:
        return True
    return bron.lower() in (f.source or "").lower()


def _clausule_matcht(f: Finding, clausule: str | None) -> bool:
    """Exact, of het hele hoofdstuk eronder: `8` geeft §8.x, `8.14` alleen §8.14.

    Nadrukkelijk geen kale `startswith`: dan zou `8.1` ook §8.14 opleveren, en dat is een ander
    onderwerp. Alleen op een punt mag de match doorlopen.
    """
    if not clausule:
        return True
    return f.clause == clausule or f.clause.startswith(f"{clausule}.")


def maak_router(audits: Audits) -> APIRouter:
    """Router voor de triage-routes onder `/audits/{audit_id}`."""
    router = APIRouter(prefix="/audits/{audit_id}")

    @router.get("/findings", response_model=list[FindingSummary])
    def lijst_findings(
        audit_id: str,
        severity: Severity | None = None,
        triage_status: TriageStatus | None = None,
        source: str | None = None,
        clause: str | None = None,
    ) -> list[FindingSummary]:
        """De bevindingenlijst, gefilterd. Alle filters combineren met AND.

        Met 271 bevindingen in één audit is "laat zien wat nog open staat" de eerste vraag van
        een triage-sessie; zonder filter is het antwoord scrollen.
        """
        return [
            _kort(f)
            for f in audits.sessie(audit_id).findings()
            if (severity is None or f.severity == severity)
            and (triage_status is None or f.triage_status == triage_status)
            and _bron_matcht(f, source)
            and _clausule_matcht(f, clause)
        ]

    @router.get("/findings/{finding_id}", response_model=Finding)
    def finding_detail(audit_id: str, finding_id: str) -> Finding:
        """Volledige finding (incl. afwijking/maatregel) voor de editor."""
        f = next((x for x in audits.sessie(audit_id).findings() if x.id == finding_id), None)
        if f is None:
            raise HTTPException(status_code=404, detail=f"Finding {finding_id!r} niet gevonden.")
        return f

    @router.get("/findings/{finding_id}/context")
    def finding_context(audit_id: str, finding_id: str) -> dict[str, object]:
        """Hover-context: normtekst per clausule + waarom dit een NC-kandidaat is."""
        try:
            return audits.sessie(audit_id).finding_context(finding_id)
        except SessionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/findings/{finding_id}", response_model=FindingSummary)
    def triage(
        audit_id: str, finding_id: str, update: TriageUpdate, request: Request
    ) -> FindingSummary:
        """Leg een auditor-beslissing vast in déze audit, met de echte actor."""
        sessie = audits.sessie(audit_id)
        wie = audits.muteert(audit_id, request)
        try:
            f = sessie.apply_triage(
                finding_id,
                severity=update.severity,
                triage_status=update.triage_status,
                title=update.title,
                deviation=update.deviation,
                corrective_measure=update.corrective_measure,
                suggestion=update.suggestion,
                reason=update.reason,
                actor=wie,
            )
        except SessionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _kort(f)

    @router.get("/trail")
    def trail(audit_id: str) -> list[dict[str, str]]:
        """De append-only triage-trail van deze audit."""
        return audits.sessie(audit_id).trail()

    @router.get("/triage/status")
    def triage_status(audit_id: str) -> dict[str, object]:
        """Voortgang van de triage; de memo is gated tot dit compleet is."""
        return audits.sessie(audit_id).triage_summary()

    @router.get("/conclusion")
    def conclusion(audit_id: str) -> dict[str, object]:
        """Saturatie-conclusie: telling valide/niet-valide/follow-up + advies."""
        return audits.sessie(audit_id).conclusion()

    return router
