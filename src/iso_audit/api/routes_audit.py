"""Audit-niveau routes: detail, run-historie en runs starten.

Elke route noemt zijn audit expliciet in het pad. Er is **geen** impliciete "huidige
audit" in servergeheugen — dat is precies hoe je in een auditwerktuig beslissingen in
de verkeerde audit vastlegt, en in een append-only trail is dat niet terug te draaien.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from iso_audit.api import overzicht as ov
from iso_audit.api import runs as runs_mod
from iso_audit.api.audit_log import log_event
from iso_audit.api.auth_gate import identiteit_van
from iso_audit.api.deps import Audits
from iso_audit.api.session import SessionError


class RunConfig(BaseModel):
    """Config waarop de run-samenvatting rapporteert: welke normen en bronnen."""

    norms: list[str] = []
    sources: list[str] = []


class RunStartRequest(BaseModel):
    """Run-start binnen deze audit: live pipeline of sim-timer, met scoping."""

    mode: str = "sim"
    norm: str = "9001"
    sources: list[str] = []
    chapter: str | None = None
    top_n: int = 0
    pace: float = 0.05


def maak_router(audits: Audits) -> APIRouter:
    """Router voor `/audits/{audit_id}` en de run-routes daaronder."""
    router = APIRouter(prefix="/audits/{audit_id}")

    @router.get("")
    def audit_detail(audit_id: str, request: Request) -> dict[str, object]:
        """Samenvatting van de audit, plus de waarschuwing bij gelijktijdig werk."""
        regel = ov.regel(audits.dir(audit_id))
        return {
            "audit": asdict(regel),
            "andere_actief": audits.registry.andere_actief(audit_id, identiteit_van(request)),
        }

    @router.get("/runs")
    def run_historie(audit_id: str) -> list[dict[str, object]]:
        """Append-only run-historie, oudste eerst — inclusief mislukte runs."""
        return runs_mod.lijst(audits.dir(audit_id))

    @router.post("/run/start")
    def run_start(
        audit_id: str, request: Request, req: RunStartRequest | None = None
    ) -> dict[str, object]:
        """Start een run binnen deze audit en registreer hem append-only."""
        sessie = audits.sessie(audit_id)
        r = req or RunStartRequest()
        wie = audits.muteert(audit_id, request)

        # Kosten-attributie (sec-bevinding 6 van change iso-portal, besluit "loggen,
        # niet begrenzen"): de classifier houdt token-verbruik al bij, maar niet wie
        # de run startte. Zonder die koppeling is een kostenpiek niet adresseerbaar.
        log_event(
            "run_gestart",
            wie,
            audit=audit_id,
            modus=r.mode,
            norm=r.norm,
            bronnen=",".join(r.sources),
            hoofdstuk=r.chapter or "",
        )

        dir_ = audits.dir(audit_id)
        try:
            resultaat = sessie.start_run(
                mode=r.mode,
                norm=r.norm,
                sources=r.sources,
                chapter=r.chapter,
                top_n=r.top_n,
                pace_s=r.pace,
            )
        except (SessionError, ValueError, OSError) as exc:
            # Ook een mislukte run hoort in de historie: een run die faalde op een
            # ontbrekende credential is precies wat je later wil terugzien.
            runs_mod.registreer(
                dir_,
                door=wie,
                modus=r.mode,
                norm=r.norm,
                bronnen=r.sources,
                hoofdstuk=r.chapter,
                fout=str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        toegevoegd, overgeslagen = sessie.laatste_merge
        runs_mod.registreer(
            dir_,
            door=wie,
            modus=r.mode,
            norm=r.norm,
            bronnen=r.sources,
            hoofdstuk=r.chapter,
            toegevoegd=toegevoegd,
            overgeslagen=overgeslagen,
        )
        return resultaat

    @router.get("/run/progress")
    def run_progress(audit_id: str) -> dict[str, object]:
        """Voortgang van de lopende run: done/total + verstreken tijd + ETA."""
        return audits.sessie(audit_id).run_progress()

    @router.post("/run")
    def run_samenvatting(audit_id: str, config: RunConfig | None = None) -> dict[str, object]:
        """Samenvatting na de run: gekozen config + tellingen per severity."""
        c = config or RunConfig()
        return audits.sessie(audit_id).run_summary(norms=c.norms, sources=c.sources)

    return router
