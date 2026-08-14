"""FastAPI-app voor het auditportaal.

Dunne schil op de audit-registry en `AuditSession` (en daarmee op de bestaande
motor). De API is het contract; `ui.html` consumeert het. Beslissingen lopen via
`POST /audits/{id}/findings/{fid}` en worden append-only vastgelegd.

**Audit-gescoped sinds change portal-dashboard.** Eerder kende de app precies één
sessie, meegegeven bij het starten. Daarmee kon je een audit doen maar geen
auditpraktijk draaien: een nieuwe audit vroeg een beheeractie en eerdere audits waren
onvindbaar. Nu is een audit een eerste-klas object en noemt elk verzoek zijn audit.

Audit-onafhankelijk blijven: `/healthz` (buiten de auth-gate, voor de kubelet-probe)
en `/config/*` — of de bronnen gekoppeld zijn is geen eigenschap van één audit.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from iso_audit.api import overzicht as ov
from iso_audit.api.audit_log import log_event
from iso_audit.api.auth_gate import identiteit_van, installeer_auth_gate
from iso_audit.api.bron_config import BronConfig, ConfigError
from iso_audit.api.deps import Audits
from iso_audit.api.registry import AuditRegistry, RegistryError
from iso_audit.api.routes_audit import maak_router as router_audit
from iso_audit.api.routes_memo import maak_router as router_memo
from iso_audit.api.routes_triage import maak_router as router_triage
from iso_audit.api.session import bron_health
from iso_audit.memo.norm_lookup import laad_norm_db

AUDITS_ROOT_ENV = "ISO_AUDIT_AUDITS_ROOT"
"""Root-directory met de audits. Expliciet, geen fallback — zie `audits_root()`."""

LOGOUT_URL_ENV = "ISO_AUDIT_LOGOUT_URL"
"""Waar de browser heen gaat ná het wissen van de proxy-sessie.

Optioneel en per omgeving instelbaar, want dit tool moet aan derden te leveren zijn: een
andere partij heeft een andere identity-provider. Staat hij niet gezet, dan wist het
portaal alleen zijn eigen sessie — dan ben je uit het portaal maar niet uit de
identity-provider, en dat is beter dan een hardcoded URL die bij iemand anders naar de
verkeerde plek wijst."""


class BronVelden(BaseModel):
    """Ingevulde velden voor één bron; sleutels moeten uit de catalogus komen."""

    velden: dict[str, str]


class NieuweAudit(BaseModel):
    """Een audit aanmaken: één of meer normen + periode; de rest is afgeleid.

    Meerdere normen is een gewone audit, geen speciaal geval: 9001 én 27001 samen
    levert één audit met één memo. De normen mogen norm-DB-slugs zijn
    (`iso-9001-2015`) of korte codes (`9001`) — `registry.norm_code` maakt er één
    vocabulaire van.
    """

    normen: list[str]
    periode: str


def audits_root() -> Path:
    """Root-directory met audits, uit de omgeving.

    Geen fallback naar een pad binnen de repo: dat zou in het portaal onder
    `readOnlyRootFilesystem` alsnog falen, en auditdata op een vluchtig filesystem
    zetten is erger dan een harde fout bij het starten.
    """
    waarde = os.environ.get(AUDITS_ROOT_ENV)
    if not waarde:
        raise RuntimeError(
            f"{AUDITS_ROOT_ENV} niet gezet. Het portaal moet expliciet weten waar de "
            "audits staan; er is bewust geen fallback."
        )
    return Path(waarde)


def create_app(
    registry: AuditRegistry,
    *,
    profile: str,
    norms_dir: str | Path,
) -> FastAPI:
    """Bouw de app rond een audit-registry."""
    app = FastAPI(title="iso-audit — auditorportaal", version="0.2.0")
    installeer_auth_gate(app)

    # Bron-configuratie naast de audits op de PVC, en meteen in de omgeving zodat de
    # adapters hem zien. Waarden uit het manifest of een Secret blijven voorgaan.
    bronnen = BronConfig(registry.root.parent)
    bronnen.naar_omgeving()
    _audits = Audits(registry=registry, profile=profile, norms_dir=norms_dir)

    def _run_loopt() -> str | None:
        """Naam van de audit met een lopende run, of None.

        Configuratie wijzigen tijdens een run levert een run waarvan de helft een andere
        scope had: een Source leest zijn config bij start en daarna niet meer.
        """
        for aid, sessie in _audits._sessies.items():
            if sessie.run_progress().get("status") == "running":
                return aid
        return None

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        """Probe-endpoint: bewust buiten de identiteits-gate en buiten elke audit.

        Liveness/readiness moet werken zonder sessie. Geeft geen auditdata terug —
        alleen dat het proces staat.
        """
        return {"status": "ok"}

    # --- audits -------------------------------------------------------------

    @app.get("/me")
    def wie_ben_ik(request: Request) -> dict[str, str | None]:
        """Wie is ingelogd, en waar gaat uitloggen naartoe.

        De UI heeft dit nodig voor "ingelogd als X" en de uitlogknop. Zonder zo'n knop
        kun je een portaal niet verlaten zonder je browser te sluiten.
        """
        return {
            "identiteit": identiteit_van(request),
            "logout_url": os.environ.get(LOGOUT_URL_ENV) or None,
        }

    @app.get("/audits")
    def lijst_audits() -> list[dict[str, object]]:
        """Dashboard: één regel per audit, inclusief audits zonder run.

        Een aangemaakte audit zonder run is een geldige toestand ("nog te starten");
        hem verbergen tot er data is maakt het overzicht onbetrouwbaar als werklijst.
        """
        return [asdict(r) for r in ov.alles(registry)]

    @app.post("/audits", status_code=201)
    def maak_audit(nieuw: NieuweAudit, request: Request) -> dict[str, object]:
        """Maak een audit aan. Een auditorhandeling, geen beheeractie."""
        wie = identiteit_van(request)
        try:
            aid = registry.maak(normen=nieuw.normen, periode=nieuw.periode, door=wie)
        except RegistryError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_event(
            "audit_aangemaakt",
            wie,
            audit=aid,
            normen=",".join(nieuw.normen),
            periode=nieuw.periode,
        )
        return asdict(ov.regel(registry.pad(aid)))

    # --- audit-onafhankelijke configuratie ----------------------------------

    @app.get("/config/options")
    def config_options() -> dict[str, list[str]]:
        """Beschikbare normen (norm-DB) en geregistreerde bronnen."""
        from iso_audit.ingest import beschikbare_bronnen

        return {
            "norms": laad_norm_db(norms_dir).standards(),
            "sources": beschikbare_bronnen(),
        }

    @app.get("/config/bronnen")
    def config_bronnen() -> list[dict[str, object]]:
        """Per bron: welke velden nodig zijn en of ze ingesteld zijn.

        Geheime velden geven alleen `ingesteld`; de waarde komt er nooit uit.
        """
        return bronnen.alles()

    @app.post("/config/bronnen/{bron}")
    def config_bron_zetten(bron: str, body: BronVelden, request: Request) -> dict[str, object]:
        """Koppel een bron of pas zijn scope aan — zonder cluster, zonder beheerder."""
        loopt = _run_loopt()
        if loopt:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Er loopt een run in audit {loopt}. Wacht tot die klaar is: een bron "
                    "die halverwege van scope wisselt levert een run met twee scopes."
                ),
            )
        wie = identiteit_van(request)
        try:
            bronnen.zet(bron, body.velden, door=wie)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_event("bron_geconfigureerd", wie, bron=bron, velden=",".join(sorted(body.velden)))
        return bronnen.status(bron)

    @app.get("/config/wijzigingen")
    def config_wijzigingen() -> list[dict[str, object]]:
        """Append-only spoor van configuratiewijzigingen: wie, wanneer, welke velden."""
        return bronnen.wijzigingen()

    @app.get("/config/health")
    def config_health() -> dict[str, dict[str, object]]:
        """Per-bron koppelstatus — één bron van waarheid, ook voor het configscherm.

        Bewust géén tweede koppel-administratie ernaast: twee plekken die zeggen of
        een bron werkt lopen uiteen, en deze bevraagt het echte systeem.
        """
        return bron_health()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _UI_HTML

    # Drie routers op hetzelfde prefix, gescheiden per onderwerp zodat geen enkel
    # route-bestand over de 200-regelgrens gaat.
    for maak in (router_audit, router_triage, router_memo):
        app.include_router(maak(_audits))
    return app


_UI_HTML = (Path(__file__).resolve().parent / "ui.html").read_text(encoding="utf-8")


def serve(
    audits_dir: str | Path,
    *,
    profile: str,
    norms_dir: str | Path,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Start de server, default gebonden aan 127.0.0.1.

    Die default is niet cosmetisch: in het portaal is oauth2-proxy de enige
    netwerk-listener, en dat is wat de identity-header betrouwbaar maakt.
    """
    import uvicorn

    registry = AuditRegistry(audits_dir)
    registry.root.mkdir(parents=True, exist_ok=True)
    uvicorn.run(
        create_app(registry, profile=profile, norms_dir=norms_dir),
        host=host,
        port=port,
    )
