"""Memo-routes binnen één audit: input redigeren, preview en export.

De memo is gated op volledige triage. Dat is geen gemak maar de missie: een
management-memo op half getrieerde bevindingen presenteert een oordeel dat de auditor
niet heeft gegeven.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from iso_audit.api.deps import Audits
from iso_audit.api.session import AuditSession, SessionError

MEMO_PDF = "Auditmemo_management.pdf"
"""Vaste bestandsnaam in de audit-directory; het overzicht leidt hieruit
`memo-klaar` af, dus die naam is contract en geen detail."""


def _eis_triage_compleet(sessie: AuditSession) -> None:
    stand = sessie.triage_summary()
    if not stand["complete"]:
        raise HTTPException(
            status_code=409,
            detail=f"Triage niet compleet: {stand['open']} kandidaat-NC('s) nog open.",
        )


def maak_router(audits: Audits) -> APIRouter:
    """Router voor de memo-routes onder `/audits/{audit_id}`."""
    router = APIRouter(prefix="/audits/{audit_id}/memo")

    @router.get("/input")
    def memo_input_get(audit_id: str) -> dict[str, object]:
        """De bewerkbare memo-koptekst + context, vóór generatie."""
        return audits.sessie(audit_id).memo_input_data()

    @router.post("/input")
    def memo_input_post(
        audit_id: str, data: dict[str, object], request: Request
    ) -> dict[str, object]:
        """Sla de aangepaste memo-input op in déze audit."""
        sessie = audits.sessie(audit_id)
        audits.muteert(audit_id, request)
        try:
            return sessie.update_memo_input(data)
        except (ValueError, OSError) as exc:
            # Validatie hier, niet pas bij de render: een onvolledige memo-input moet
            # een leesbare 400 geven en geen mislukte PDF.
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/preview", response_class=HTMLResponse)
    def memo_preview(audit_id: str) -> str:
        sessie = audits.sessie(audit_id)
        _eis_triage_compleet(sessie)
        try:
            return sessie.render_html()
        except (SessionError, ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/export")
    def memo_export(audit_id: str, request: Request) -> dict[str, str]:
        """Render de memo naar PDF in de audit-directory."""
        sessie = audits.sessie(audit_id)
        _eis_triage_compleet(sessie)
        audits.muteert(audit_id, request)
        return {"pdf": str(sessie.export_pdf(sessie.dir / MEMO_PDF))}

    @router.get("/pdf")
    def memo_pdf(audit_id: str) -> Response:
        """De geëxporteerde memo, inline — voor de besprekingsmodal in het portaal.

        Inline en niet als bijlage: dit is de bespreekweergave. Wie hem wil meenemen gebruikt
        `/download`, dat een zip met een manifest levert.
        """
        pad = audits.sessie(audit_id).dir / MEMO_PDF
        if not pad.is_file():
            raise HTTPException(
                status_code=404,
                detail="Het memo is nog niet geëxporteerd; draai eerst de export.",
            )
        return Response(
            content=pad.read_bytes(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{MEMO_PDF}"'},
        )

    return router
