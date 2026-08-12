"""Fail-closed identity-gate voor het portaal (`iso-portal`, capability portal-auth).

De app heeft **geen eigen login**. In het portaal staat oauth2-proxy ervoor, die de
operator tegen Keycloak authenticeert (realm `commonground`, dat Google brokert) en
de identiteit doorgeeft als `X-Forwarded-Email` / `X-Forwarded-User`. Deze module
is de enige plek die die header vertrouwt.

## Waarom de header te vertrouwen is

Niet omdat hij er staat, maar omdat twee dingen buiten deze module het afdwingen:

1. **Topologie.** De app bindt `127.0.0.1`; oauth2-proxy is de enige
   netwerk-listener in de pod, en een NetworkPolicy laat pod-ingress alleen toe
   uit `ingress-nginx`. Niets anders kán de header zetten.
2. **Fail closed.** `REQUIRE_AUTH` staat default aan, dus een request zonder
   header krijgt 403. Een verkeerd geconfigureerde ingress degradeert naar "op
   slot", niet naar "open".

Overgenomen van `openwoo-app-config/webgui/server.py` (`current_user()`), zodat er
één trust-model in de organisatie is en niet twee.

## Waarom middleware en geen per-route dependency

Een `Depends()` per route moet bij élk nieuw endpoint opnieuw worden aangezet, en
vergeten betekent stil een open route. Middleware dekt alles wat er is en alles
wat er nog bij komt; nieuwe endpoints zijn beschermd tenzij iemand ze expliciet in
`open_paden` zet. Dat is de veilige default, en het is in één functie na te lezen.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import Response

from iso_audit.api.audit_log import log_event

MUTEREND = frozenset({"POST", "PUT", "PATCH", "DELETE"})
"""Methodes die auditdata kunnen wijzigen; die worden altijd gelogd."""

EMAIL_HEADER = "X-Forwarded-Email"
"""Header die oauth2-proxy zet met het geverifieerde e-mailadres."""

USER_HEADER = "X-Forwarded-User"
"""Fallback-header; sommige proxy-configuraties zetten alleen deze."""

REQUIRE_AUTH_ENV = "REQUIRE_AUTH"
"""Env-var die de gate aan/uit zet. Default: aan."""

DEV_IDENTITEIT = "dev:auth-uitgeschakeld"
"""Identiteit bij `REQUIRE_AUTH=false`.

Bewust een onmiskenbare, greppbare waarde: als dit ooit in een audit-trail
opduikt, is dat direct herkenbaar als een dev-run en niet te verwarren met een
mens. De oude default `"auditor"` uit `apply_triage()` was juist wél te verwarren.
"""

OPEN_PADEN: tuple[str, ...] = ("/healthz",)
"""Paden zonder identiteits-eis. Alleen de probe — bewust geen `/` of statics:
de liveness/readiness-check moet werken zonder sessie, al het andere niet."""

_UIT_WAARDEN = frozenset({"false", "0", "no", "off", ""})


def auth_vereist() -> bool:
    """Staat de gate aan? Alles behalve een expliciete uit-waarde betekent ja.

    Onbekende waarden (typfouten, `REQUIRE_AUTH=maybe`) leveren dus **aan**. Een
    typfout mag geen portaal openzetten.
    """
    return os.environ.get(REQUIRE_AUTH_ENV, "true").strip().lower() not in _UIT_WAARDEN


def identiteit_uit_headers(request: Request) -> str:
    """Lees de geverifieerde identiteit uit de proxy-headers; `""` als die er niet is."""
    for header in (EMAIL_HEADER, USER_HEADER):
        waarde = request.headers.get(header)
        if waarde and waarde.strip():
            return waarde.strip()
    return ""


def identiteit_van(request: Request) -> str:
    """Geef de identiteit die de gate voor dit request heeft vastgesteld.

    Bedoeld voor routes die de actor in de audit-trail moeten vastleggen. Valt
    terug op de headers wanneer de middleware niet geïnstalleerd is, en daarna op
    :data:`DEV_IDENTITEIT`. Retourneert dus **nooit** een lege string: een
    trail-regel met een leeg `actor`-veld is erger dan een die zichtbaar "dev"
    zegt, want leeg leest als een ontbrekend veld in plaats van als een
    dev-run.
    """
    identiteit: str = getattr(request.state, "identiteit", "") or identiteit_uit_headers(request)
    return identiteit or DEV_IDENTITEIT


def installeer_auth_gate(app: FastAPI, *, open_paden: tuple[str, ...] = OPEN_PADEN) -> None:
    """Installeer de gate als HTTP-middleware op `app`.

    Zet de vastgestelde identiteit op `request.state.identiteit` zodat routes hem
    kunnen loggen, en weigert met 403 wanneer hij ontbreekt terwijl de gate aan
    staat.
    """

    @app.middleware("http")
    async def _gate(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in open_paden:
            return await call_next(request)

        identiteit = identiteit_uit_headers(request)
        if not identiteit:
            if auth_vereist():
                log_event(
                    "auth_geweigerd",
                    "(geen)",
                    methode=request.method,
                    pad=request.url.path,
                    status=403,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            f"Geen geverifieerde identiteit in {EMAIL_HEADER}. Dit endpoint "
                            "is alleen bereikbaar via de oauth2-proxy die de identiteit zet."
                        )
                    },
                )
            identiteit = DEV_IDENTITEIT

        request.state.identiteit = identiteit
        respons = await call_next(request)
        if request.method in MUTEREND:
            log_event(
                "mutatie",
                identiteit,
                methode=request.method,
                pad=request.url.path,
                status=respons.status_code,
            )
        return respons
