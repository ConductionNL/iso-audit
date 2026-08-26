"""Audit-niveau routes: detail, run-historie en runs starten.

Elke route noemt zijn audit expliciet in het pad. Er is **geen** impliciete "huidige
audit" in servergeheugen — dat is precies hoe je in een auditwerktuig beslissingen in
de verkeerde audit vastlegt, en in een append-only trail is dat niet terug te draaien.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from iso_audit.api import overzicht as ov
from iso_audit.api import runs as runs_mod
from iso_audit.api import uitlevering
from iso_audit.api.audit_log import log_event
from iso_audit.api.auth_gate import identiteit_van
from iso_audit.api.deps import Audits
from iso_audit.api.registry import MANIFEST, RegistryError, run_code
from iso_audit.api.routes_memo import MEMO_PDF
from iso_audit.api.session import RunLooptError, SessionError


class RunConfig(BaseModel):
    """Config waarop de run-samenvatting rapporteert: welke normen en bronnen."""

    norms: list[str] = []
    sources: list[str] = []


class Zichtbaarheid(BaseModel):
    """Een run uit de werklijst zetten (of terugzetten), met een reden.

    Op moduleniveau en niet in de router-functie: met `from __future__ import annotations`
    zijn annotaties strings, en FastAPI zoekt het model op in de **module**-globals. Een
    lokaal gedefinieerde klasse vindt hij daar niet, en dan wordt het body-model als
    queryparameter gelezen — resultaat: 422 op een geldig verzoek.
    """

    verborgen: bool = True
    reden: str = ""


class RunStartRequest(BaseModel):
    """Run-start binnen deze audit: live pipeline of sim-timer, met scoping.

    Géén `norm`-veld: de normen horen bij de audit en worden uit het manifest gelezen.
    Een run die een andere norm kan kiezen dan de audit, is een run waarvan de scope
    niet meer uit de audit volgt — en dan liegt de memo over wat er getoetst is.
    """

    mode: str = "sim"
    """`sim` (indexatie-timer) of `live` (de volledige pipeline).

    Bronnen inlezen zit niet hier maar op `POST /landschap/ingest`."""

    sources: list[str] = []
    chapter: str | None = None
    top_n: int = 0
    pace: float = 0.05
    review: bool | None = None
    """Autonome review aan (`true`), uit (`false`) of de omgeving laten beslissen (`null`).

    Drie standen en geen boolean met een default: `false` als standaard zou betekenen dat het
    portaal `ISO_AUDIT_REVIEW` altijd overstemt, en dan is de env-var-fallback voor cron zinloos.
    Zie `classification/review.ReviewInstelling`."""
    review_steekproef: int = 0
    """Beoordeel alleen de N zwaarste clausules; 0 is alles."""
    auto_triage: bool | None = None
    """Het onbetwiste deel automatisch afdoen. Zonder review gebeurt er niets."""


def maak_router(audits: Audits) -> APIRouter:
    """Router voor `/audits/{audit_id}` en de run-routes daaronder."""
    router = APIRouter(prefix="/audits/{audit_id}")

    @router.get("/download")
    def download(
        audit_id: str,
        scope: str = Query("memo", pattern="^(memo|bewijslast)$"),
    ) -> Response:
        """Lever de output als zip, zodat de auditor er daadwerkelijk bij kan.

        De export meldde eerder alleen een serverpad in een pod met een read-only filesystem,
        achter een oauth-proxy. Niemand kon daarbij, en dat gold ook voor de bewijslast-rapporten.
        """
        sessie = audits.sessie(audit_id)
        normen = audits.registry.normen_van(audit_id)
        try:
            inhoud = uitlevering.bouw_zip(
                audit_id,
                sessie.dir,
                scope=scope,
                run_code=run_code(normen),
                memo_pdf=MEMO_PDF,
            )
        except uitlevering.UitleveringError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(
            content=inhoud,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{audit_id}_{scope}.zip"',
            },
        )

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
        """Run-historie, oudste eerst — inclusief mislukte en lopende runs.

        `samengevat()` en niet `lijst()`: een run heeft twee append-only records (start en
        afsluiting) en de UI wil de laatste stand per run. Het ruwe spoor blijft
        onaangetast in `runs.jsonl`.
        """
        alles = runs_mod.samengevat(audits.dir(audit_id))
        # Verborgen runs gaan mee met een vlag in plaats van eruit gefilterd te worden: de
        # UI beslist wat zichtbaar is, en `GET /runs` blijft de volledige trail. Zo kan een
        # auditor "toon verborgen" aanzetten zonder een tweede endpoint.
        return alles

    @router.post("/runs/{run_id}/zichtbaarheid")
    def run_zichtbaarheid(
        audit_id: str, run_id: str, body: Zichtbaarheid, request: Request
    ) -> dict[str, object]:
        """Zet een run uit of aan in de werklijst — append-only, met wie en waarom.

        Geen `DELETE`: `runs.jsonl` is de audittrail. Een run die faalde moet zichtbaar
        blijven voor wie ernaar zoekt; hij hoeft alleen niet in de weg te staan. Zie
        `runs.verberg()` voor de afweging.

        Een lopende run kan niet verborgen worden: dat zou de enige aanwijzing weghalen dat
        er iets bezig is.
        """
        wie = audits.muteert(audit_id, request)
        dir_ = audits.dir(audit_id)
        huidig = {str(r.get("run_id")): r for r in runs_mod.samengevat(dir_)}
        record = huidig.get(run_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Onbekende run: {run_id}")
        if body.verborgen and record.get("status") == "loopt":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Deze run loopt nog. Een lopende run verbergen haalt de enige aanwijzing "
                    "weg dat er iets bezig is."
                ),
            )
        uit = runs_mod.verberg(dir_, run_id, door=wie, reden=body.reden, verborgen=body.verborgen)
        log_event(
            "run_verborgen" if body.verborgen else "run_teruggezet",
            wie,
            audit=audit_id,
            run=run_id,
            reden=body.reden[:200],
        )
        return uit

    @router.post("/run/start")
    def run_start(
        audit_id: str, request: Request, req: RunStartRequest | None = None
    ) -> dict[str, object]:
        """Start een run binnen deze audit en registreer hem append-only."""
        sessie = audits.sessie(audit_id)
        r = req or RunStartRequest()
        wie = audits.muteert(audit_id, request)

        # De norm komt uit de audit, niet uit het verzoek. Faalt hier als de audit een
        # norm bevat die de pipeline nog niet kan draaien.
        manifest = json.loads((audits.dir(audit_id) / MANIFEST).read_text(encoding="utf-8"))
        try:
            norm = run_code([str(n) for n in manifest.get("normen", [])])
        except RegistryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        dir_ = audits.dir(audit_id)

        # Eerst het startrecord, dan starten. Dat record reserveert het run-nummer en
        # zorgt dat een run die halverwege sneuvelt (pod-restart, OOM) een spoor heeft.
        # De worker sluit het af met de echte tellingen.
        record = runs_mod.registreer(
            dir_,
            door=wie,
            modus=r.mode,
            norm=norm,
            bronnen=r.sources,
            hoofdstuk=r.chapter,
        )
        run_id = str(record["run_id"])

        try:
            resultaat = sessie.start_run(
                mode=r.mode,
                norm=norm,
                sources=r.sources,
                chapter=r.chapter,
                top_n=r.top_n,
                pace_s=r.pace,
                review=r.review,
                review_steekproef=r.review_steekproef,
                auto_triage=r.auto_triage,
                run_id=run_id,
            )
        except RunLooptError as exc:
            # 409 en niet 400: het verzoek is niet ongeldig, het moment is verkeerd. Het
            # record wordt afgesloten zodat er geen tweede "loopt nog" in de historie blijft
            # staan — precies wat er op 2026-08-21 vier keer gebeurde.
            runs_mod.afsluiten(dir_, run_id, fout=str(exc))
            log_event(
                "run_geweigerd_dubbel",
                wie,
                audit=audit_id,
                modus=r.mode,
                reden=str(exc)[:200],
            )
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (SessionError, ValueError, OSError) as exc:
            # Ook een geweigerde run hoort in de historie: "iemand probeerde te draaien
            # zonder bron" is precies de diagnose die je later mist. Afsluiten, niet
            # opnieuw registreren — anders krijgt de audit een tweede run-nummer.
            runs_mod.afsluiten(dir_, run_id, fout=str(exc))
            log_event(
                "run_geweigerd",
                wie,
                audit=audit_id,
                modus=r.mode,
                bronnen=",".join(r.sources),
                reden=str(exc)[:200],
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Kosten-attributie (sec-bevinding 6 van change iso-portal, besluit "loggen,
        # niet begrenzen"): de classifier houdt token-verbruik al bij, maar niet wie
        # de run startte. Zonder die koppeling is een kostenpiek niet adresseerbaar.
        # Ná `start_run`, want anders staat er "gestart" in het toegangslog bij een run
        # die geweigerd is.
        log_event(
            "run_gestart",
            wie,
            audit=audit_id,
            modus=r.mode,
            norm=norm,
            bronnen=",".join(r.sources),
            hoofdstuk=r.chapter or "",
        )

        # Een sim-run met `pace<=0` is al klaar als `start_run` terugkeert (synchroon,
        # voor tests); die sluit hier af, want er is geen worker die het doet.
        if r.mode != "live" and resultaat.get("status") == "done":
            toegevoegd, overgeslagen = sessie.laatste_merge
            runs_mod.afsluiten(dir_, run_id, toegevoegd=toegevoegd, overgeslagen=overgeslagen)
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
