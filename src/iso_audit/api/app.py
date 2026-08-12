"""FastAPI-app voor de auditor-flow (MVP: triage + memo).

Dunne schil op `AuditSession` (en daarmee de bestaande motor). De API is het
contract; een frontend (web nu, Nextcloud later) consumeert dit. Beslissingen
lopen via `POST /findings/{id}` en worden append-only vastgelegd.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from iso_audit.api.audit_log import log_event
from iso_audit.api.auth_gate import identiteit_van, installeer_auth_gate
from iso_audit.api.session import AuditSession, SessionError
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


class RunConfig(BaseModel):
    """Stap 1-config: welke normen + bronnen in de run-scope."""

    norms: list[str] = []
    sources: list[str] = []


class RunStartRequest(BaseModel):
    """Stap 2-start: live pipeline of sim-timer, met chapter-scoping."""

    mode: str = "sim"  # "sim" | "live"
    norm: str = "9001"  # run-code: 9001 | 27001 | beide
    sources: list[str] = []
    chapter: str | None = None  # hoofdstuk-filter (scoping), bv. "8"
    top_n: int = 0  # 0 = alle NC-kandidaten draften (geen cap)
    pace: float = 0.05


class FindingSummary(BaseModel):
    id: str
    severity: Severity
    clause: str
    title: str
    triage_status: TriageStatus
    source: str | None = None  # bevinding berust op bron Y


def create_app(session: AuditSession) -> FastAPI:
    """Bouw de FastAPI-app rond één geladen auditsessie."""
    app = FastAPI(title="iso-audit — auditor-API", version="0.1.0")
    installeer_auth_gate(app)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Probe-endpoint: bewust buiten de identiteits-gate.

        Liveness/readiness moet werken zonder sessie. Geeft geen auditdata terug —
        alleen dat het proces staat.
        """
        return {"status": "ok"}

    @app.get("/findings", response_model=list[FindingSummary])
    def lijst_findings(severity: Severity | None = None) -> list[FindingSummary]:
        return [
            FindingSummary(
                id=f.id,
                severity=f.severity,
                clause=f.clause,
                title=f.title,
                triage_status=f.triage_status,
                source=f.source,
            )
            for f in session.findings()
            if severity is None or f.severity == severity
        ]

    @app.post("/findings/{finding_id}", response_model=FindingSummary)
    def triage(finding_id: str, update: TriageUpdate, request: Request) -> FindingSummary:
        try:
            f = session.apply_triage(
                finding_id,
                severity=update.severity,
                triage_status=update.triage_status,
                title=update.title,
                deviation=update.deviation,
                corrective_measure=update.corrective_measure,
                suggestion=update.suggestion,
                reason=update.reason,
                # De geverifieerde identiteit, niet de default `"auditor"`: een
                # append-only trail zonder toewijsbare actor beantwoordt de eerste
                # vraag van een auditor niet (sec-bevinding 1 van change iso-portal).
                actor=identiteit_van(request),
            )
        except SessionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FindingSummary(
            id=f.id,
            severity=f.severity,
            clause=f.clause,
            title=f.title,
            triage_status=f.triage_status,
            source=f.source,
        )

    @app.get("/findings/{finding_id}", response_model=Finding)
    def finding_detail(finding_id: str) -> Finding:
        """Volledige finding (incl. afwijking/maatregel) voor de editor."""
        f = next((x for x in session.findings() if x.id == finding_id), None)
        if f is None:
            raise HTTPException(status_code=404, detail=f"Finding {finding_id!r} niet gevonden.")
        return f

    @app.get("/findings/{finding_id}/context")
    def finding_context(finding_id: str) -> dict[str, object]:
        """Hover-context: normtekst per clausule + redenatie (waarom NC-kandidaat)."""
        try:
            return session.finding_context(finding_id)
        except SessionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/trail")
    def trail() -> list[dict[str, str]]:
        """De append-only triage-trail (auditor-beslissingen)."""
        return session.trail()

    @app.get("/config/options")
    def config_options() -> dict[str, list[str]]:
        """Stap 1: beschikbare normen + bronnen om de run te configureren."""
        return session.config_options()

    @app.get("/config/health")
    def config_health() -> dict[str, dict[str, object]]:
        """Korte per-bron healthcheck; de UI greyt niet-gekoppelde bronnen uit."""
        return session.source_health()

    @app.post("/run/start")
    def run_start(request: Request, req: RunStartRequest | None = None) -> dict[str, object]:
        """Stap 2: start de run (live pipeline of sim-timer); voortgang via /run/progress."""
        r = req or RunStartRequest()
        # Kosten-attributie (sec-bevinding 6, besluit "loggen, niet begrenzen"): de
        # classifier houdt het token-verbruik al bij via `Kostenteller`; wat ontbrak
        # is wie de run startte. Deze regel maakt kosten herleidbaar naar een mens.
        log_event(
            "run_gestart",
            identiteit_van(request),
            modus=r.mode,
            norm=r.norm,
            bronnen=",".join(r.sources),
            hoofdstuk=r.chapter or "",
        )
        return session.start_run(
            mode=r.mode,
            norm=r.norm,
            sources=r.sources,
            chapter=r.chapter,
            top_n=r.top_n,
            pace_s=r.pace,
        )

    @app.get("/run/progress")
    def run_progress() -> dict[str, object]:
        """Voortgang stap 2: done/total + verstreken tijd + aftellende ETA."""
        return session.run_progress()

    @app.post("/run")
    def run(config: RunConfig | None = None) -> dict[str, object]:
        """Stap 2: samenvatting (config + tellingen) — toon na afronden van de run."""
        c = config or RunConfig()
        return session.run_summary(norms=c.norms, sources=c.sources)

    @app.get("/triage/status")
    def triage_status() -> dict[str, object]:
        """Voortgang van de triage; de memo is gated tot dit compleet is."""
        return session.triage_summary()

    @app.get("/conclusion")
    def conclusion() -> dict[str, object]:
        """Saturatie-conclusie na triage: telling valide/niet-valide/follow-up + advies."""
        return session.conclusion()

    def _eis_triage_compleet() -> None:
        s = session.triage_summary()
        if not s["complete"]:
            raise HTTPException(
                status_code=409,
                detail=f"Triage niet compleet: {s['open']} kandidaat-NC('s) nog open.",
            )

    @app.get("/memo/input")
    def memo_input_get() -> dict[str, object]:
        """De bewerkbare memo-koptekst + context (voor de pre-generatie editor)."""
        return session.memo_input_data()

    @app.post("/memo/input")
    def memo_input_post(data: dict[str, object]) -> dict[str, object]:
        """Sla de aangepaste memo-input op (auditor past de memo aan vóór generatie)."""
        try:
            return session.update_memo_input(data)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/memo/preview", response_class=HTMLResponse)
    def memo_preview() -> str:
        _eis_triage_compleet()
        try:
            return session.render_html()
        except (SessionError, ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/memo/export")
    def memo_export() -> dict[str, str]:
        _eis_triage_compleet()
        pad = session.export_pdf(session.dir / "Auditmemo_management.pdf")
        return {"pdf": str(pad)}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _UI_HTML

    return app


_UI_HTML = (Path(__file__).resolve().parent / "ui.html").read_text(encoding="utf-8")


def serve(
    session_dir: str | Path,
    *,
    profile: str,
    norms_dir: str | Path,
    memo_input_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Start de lokale server (gebonden aan 127.0.0.1)."""
    import uvicorn

    session = AuditSession(
        session_dir, profile=profile, norms_dir=norms_dir, memo_input_path=memo_input_path
    )
    uvicorn.run(create_app(session), host=host, port=port)
