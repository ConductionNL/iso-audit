"""FastAPI-app voor het auditportaal.

Dunne schil op de audit-registry en `AuditSession` (en daarmee op de bestaande
motor). De API is het contract; `ui.html` consumeert het. Beslissingen lopen via
`POST /audits/{id}/findings/{fid}` en worden append-only vastgelegd.

**Audit-gescoped sinds change portal-dashboard.** Eerder kende de app precies één
sessie, meegegeven bij het starten. Daarmee kon je een audit doen maar geen
auditpraktijk draaien: een nieuwe audit vroeg een beheeractie en eerdere audits waren
onvindbaar. Nu is een audit een eerste-klas object en noemt elk verzoek zijn audit.

Audit-onafhankelijk blijven: `/healthz` (buiten de auth-gate, voor de kubelet-probe)
en `/instellingen/*` — of de bronnen gekoppeld zijn is geen eigenschap van één audit.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from iso_audit.api import overzicht as ov
from iso_audit.api import runs
from iso_audit.api.audit_log import log_event
from iso_audit.api.auth_gate import identiteit_van, installeer_auth_gate
from iso_audit.api.bron_config import BronConfig, ConfigError
from iso_audit.api.deps import Audits
from iso_audit.api.registry import MANIFEST, AuditRegistry, RegistryError
from iso_audit.api.routes_audit import maak_router as router_audit
from iso_audit.api.routes_memo import maak_router as router_memo
from iso_audit.api.routes_triage import maak_router as router_triage
from iso_audit.api.session import SessionError, bron_health, valideer_bronselectie
from iso_audit.classification.findings import (
    KIESBARE_MODELLEN,
    PRIJZEN_GRONDSLAG,
    PRIJZEN_PEILDATUM,
)
from iso_audit.classification.respons import OnleesbaarAntwoordError
from iso_audit.config import anthropic_auth as aa
from iso_audit.config import herkomst as hk
from iso_audit.config.settings import VELDEN, Settings, load_config
from iso_audit.config.verbinding import normaliseer
from iso_audit.memo.norm_lookup import laad_norm_db

_log_start = logging.getLogger("iso_audit.audit")

AUDITS_ROOT_ENV = "ISO_AUDIT_AUDITS_ROOT"
"""Root-directory met de audits. Expliciet, geen fallback — zie `audits_root()`."""

LOGOUT_URL_ENV = "ISO_AUDIT_LOGOUT_URL"
"""Waar de browser heen gaat ná het wissen van de proxy-sessie.

Optioneel en per omgeving instelbaar, want dit tool moet aan derden te leveren zijn: een
andere partij heeft een andere identity-provider. Staat hij niet gezet, dan wist het
portaal alleen zijn eigen sessie — dan ben je uit het portaal maar niet uit de
identity-provider, en dat is beter dan een hardcoded URL die bij iemand anders naar de
verkeerde plek wijst."""


class LoginCode(BaseModel):
    """De code die de auditor uit de browser terugplakt."""

    sessie: str
    code: str


class LandschapVerzoek(BaseModel):
    """Welke bronnen ingelezen worden voor het documentenlandschap."""

    bronnen: list[str] = []


class AssistentVraag(BaseModel):
    """Eén vraag aan de assistent. Geen gespreksgeschiedenis: elk antwoord staat los.

    `norm` bepaalt welke normteksten meegaan; `9001` en `27001` zijn de twee die
    `data/normteksten` kent.
    """

    vraag: str
    norm: str = "27001"


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

    # Wat een beheerder van buiten meegaf, vastgelegd vóórdat er iets naar `os.environ`
    # is geschreven. Zonder deze momentopname is "komt deze waarde uit de omgeving?"
    # zelfreferentieel — zie `BronConfig.basis` en `load_config(omgeving=...)`.
    basis_omgeving = dict(os.environ)

    # Schema klaarzetten bij het opstarten, niet bij het eerste gebruik. `initialiseer`
    # voert ook migraties uit, en die hoorden niet halverwege een run van twintig minuten
    # te gebeuren omdat dat toevallig het eerste pad was dat hem aanriep. Faalt dit, dan
    # start het portaal niet — een kapot schema is niets om verkeer op te serveren.
    from iso_audit.store import initialiseer as _init_schema
    from iso_audit.store import verbinding as _db

    _schema_conn = _db()
    try:
        _init_schema(_schema_conn)
        _schema_conn.commit()
    finally:
        _schema_conn.close()

    # Bron-configuratie naast de audits op de PVC, en meteen in de omgeving zodat de
    # adapters hem zien. Waarden uit het manifest of een Secret blijven voorgaan, tenzij
    # een auditor expliciet voor overschrijven heeft gekozen.
    bronnen = BronConfig(registry.root.parent, omgeving=basis_omgeving)

    # Eén loader bepaalt welke waarde wint (env > config.yaml > UI) en levert per veld
    # de herkomst mee. Alles wat configuratie nodig heeft, komt hierlangs — niet
    # rechtstreeks bij os.environ, want dan is de herkomst weg.
    def _laad_settings() -> Settings:
        s = load_config(
            root=registry.root.parent,
            ui_waarden=bronnen.ui_waarden(),
            omgeving=basis_omgeving,
            overschrijvingen=set(bronnen.overschrijvingen()),
        )
        s.naar_omgeving()
        return s

    def _vastgezette_velden() -> frozenset[str]:
        """Env-namen die een beheerder heeft gezet en die niet zijn overschreven.

        Alleen `env` en `yaml` tellen. `default` niet: dat is een ingebouwde waarde die
        een auditor juist wél mag vervangen. `ui-override` ook niet — daar heeft iemand de
        beheerderswaarde al bewust opzij gezet.
        """
        huidig = _laad_settings()
        return frozenset(
            veld.env for veld in VELDEN if huidig[veld.sleutel].bron in ("env", "yaml")
        )

    settings = _laad_settings()
    hk.log_herkomst(settings)
    _audits = Audits(registry=registry, profile=profile, norms_dir=norms_dir)

    # Runs die `loopt` zeggen bij een verse start kunnen niet lopen: een run leeft in een
    # thread van dit proces. Op 2026-08-21 stonden er vier zulke records in één audit nadat
    # het proces was omgevallen — de historie beweerde dat er vier runs bezig waren. Een
    # trail die zegt dat er iets loopt wat niet loopt, is erger dan een lege trail.
    if registry.root.is_dir():
        for _dir in sorted(registry.root.iterdir()):
            # `MANIFEST` en geen letterlijke naam: hier stond "manifest.json" terwijl het
            # bestand `audit.json` heet, waardoor deze lus élke audit oversloeg en de
            # reconciliatie stil niets deed. De test riep de functie direct aan en bewees
            # daarmee dat hij werkt, niet dat hij aangesloten is.
            if not (_dir.is_dir() and (_dir / MANIFEST).is_file()):
                continue
            _verweesd = runs.sluit_verweesde_runs(_dir)
            if _verweesd:
                _log_start.warning(
                    "Run(s) %s stonden op 'loopt' bij het opstarten en zijn afgesloten als "
                    "afgebroken (audit %s).",
                    ", ".join(_verweesd),
                    _dir.name,
                )

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

    class AuditArchiveren(BaseModel):
        """Reden verplicht: zonder reden is later niet te zien of dit opruimen was."""

        reden: str

    @app.post("/audits/{audit_id}/archiveer")
    def archiveer_audit(audit_id: str, body: AuditArchiveren, request: Request) -> dict[str, str]:
        """Haal een audit uit het overzicht door hem naar het archief te verplaatsen.

        **Verplaatsen, niet verwijderen.** Een audit die gedraaid heeft is bewijs dát er
        geaudit is; die weggooien maakt "wat is er in Q2 getoetst?" onbeantwoordbaar. Er is
        daarom geen route die echt verwijdert — wie een dossier definitief kwijt wil, doet dat
        bewust op de opslag en niet met één klik in een auditwerktuig.
        """
        wie = identiteit_van(request)
        loopt = _run_loopt()
        if loopt == audit_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Er loopt een run in deze audit. Wacht tot die klaar is: de map "
                    "verplaatsen tijdens een run levert een run op die in het niets schrijft."
                ),
            )
        try:
            doel = registry.archiveer(audit_id, door=wie, reden=body.reden)
        except RegistryError as exc:
            code = 404 if "bestaat niet" in str(exc) else 400
            raise HTTPException(status_code=code, detail=str(exc)) from exc
        log_event("audit_gearchiveerd", wie, audit=audit_id, reden=body.reden.strip())
        return {"audit_id": audit_id, "archief": str(doel)}

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

    @app.get("/instellingen/options")
    def config_options() -> dict[str, list[str]]:
        """Beschikbare normen (norm-DB) en geregistreerde bronnen."""
        from iso_audit.ingest import beschikbare_bronnen

        return {
            "norms": laad_norm_db(norms_dir).standards(),
            "sources": beschikbare_bronnen(),
        }

    @app.get("/instellingen/bronnen")
    def config_bronnen() -> list[dict[str, object]]:
        """Per bron: welke velden nodig zijn en of ze ingesteld zijn.

        Geheime velden geven alleen `ingesteld`; de waarde komt er nooit uit.
        """
        return bronnen.alles()

    @app.post("/instellingen/bronnen/{bron}")
    def config_bron_zetten(bron: str, body: BronVelden, request: Request) -> dict[str, object]:
        """Koppel een bron of pas zijn scope aan — zonder cluster, zonder beheerder.

        Een ingevulde waarde geldt, ook als er een beheerderswaarde in de omgeving staat.
        Dat is nodig om een geroteerde of ingetrokken credential te kunnen vervangen; kan
        dat niet, dan is de auditcapability weer gebonden aan iemand met clustertoegang.

        Er zit geen extra bevestigingsstap omheen. Die heeft hier even gestaan en was
        fout: hij loste een probleem op dat toen al verholpen was (een save die slaagde en
        genegeerd werd), en maakte configureren moeilijker in plaats van beter
        registreerbaar. De controle is dat het vastligt — herkomst `ui-override`, plus een
        regel in het append-only spoor — niet dat het gedoe is.
        """
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
        vast = _vastgezette_velden()
        vervangt = sorted(n for n, w in body.velden.items() if n in vast and w.strip())
        try:
            bronnen.zet(bron, body.velden, door=wie)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_event(
            "bron_overschreven" if vervangt else "bron_geconfigureerd",
            wie,
            bron=bron,
            velden=",".join(sorted(body.velden)),
        )
        # De herkomst is nu veranderd: leg de nieuwe situatie vast, zodat de trail en
        # /config/herkomst niet uiteenlopen met wat de adapters straks lezen.
        hk.log_herkomst(_laad_settings())
        return bronnen.status(bron)

    @app.get("/instellingen/herkomst")
    def config_herkomst() -> dict[str, object]:
        """Per veld: welke bron won, en of het is ingesteld.

        Dit is wat een auditor achteraf vraagt — liep die run op een cluster-Secret of
        op iets dat iemand in de UI had ingetypt? Geheime waarden komen gemaskeerd
        terug, nooit volledig.
        """
        huidig = _laad_settings()
        return {"config_version": huidig.config_version, "velden": hk.overzicht(huidig)}

    @app.get("/instellingen/anthropic")
    def anthropic_status() -> dict[str, object]:
        """Welke modus, welk model, en of er een actieve sessie is.

        Bij `api_key` is de status een simpele "is de key ingesteld"; bij `sso` vragen we
        de CLI. Dat verschil is expliciet, want een auditor moet weten waaróm het werkt.
        """
        huidig = _laad_settings()
        modus = huidig.auth_mode
        if modus == "sso":
            sessie = aa.status()
        else:
            key = huidig["anthropic.api_key"]
            sessie = {
                "actief": key.ingesteld,
                "reden": "" if key.ingesteld else "Er is geen API-key ingesteld.",
            }
        return {
            "modus": modus,
            "model": huidig["anthropic.model"].waarde,
            "modellen": list(KIESBARE_MODELLEN),
            "prijzen_peildatum": PRIJZEN_PEILDATUM,
            # Een bedrag zonder grondslag is niet te lezen: lijstprijs is niet hetzelfde
            # als wat er gefactureerd wordt. Sinds 2026-08-20 staat de tabel op het
            # werkelijke tarief; de UI hoort te zeggen welke van de twee ze ziet.
            "prijzen_grondslag": PRIJZEN_GRONDSLAG,
            # Wat dit portaal heeft uitgegeven — niet het accountsaldo. Dat laatste is met een
            # gewone API-key niet op te vragen (de Admin API weigert hem), en een saldo-endpoint
            # bestaat sowieso niet. De vraag achter "hoeveel credit heb ik nog" is in de praktijk
            # "wat verbruikt dit ding", en dát kunnen we met gemeten eigen cijfers beantwoorden.
            "verbruik": ov.verbruik(registry.root),
            **sessie,
        }

    @app.post("/instellingen/anthropic/login")
    def anthropic_login_start(request: Request) -> dict[str, str]:
        """Start de browserstap. Het portaal heeft geen browser en hoort er geen te hebben."""
        try:
            sessie, url = aa.start_login()
        except aa.AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_event("anthropic_login_gestart", identiteit_van(request))
        return {"sessie": sessie, "url": url}

    @app.post("/instellingen/anthropic/login/code")
    def anthropic_login_code(body: LoginCode, request: Request) -> dict[str, object]:
        """Lever de code aan. De code wordt niet gelogd en niet bewaard."""
        try:
            aa.voltooi_login(body.sessie, body.code)
        except aa.AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_event("anthropic_login_voltooid", identiteit_van(request))
        return aa.status()

    @app.post("/instellingen/anthropic/logout")
    def anthropic_logout(request: Request) -> dict[str, object]:
        try:
            aa.uitloggen()
        except aa.AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        log_event("anthropic_uitgelogd", identiteit_van(request))
        return aa.status()

    @app.get("/instellingen/wijzigingen")
    def config_wijzigingen() -> list[dict[str, object]]:
        """Append-only spoor van configuratiewijzigingen: wie, wanneer, welke velden."""
        return bronnen.wijzigingen()

    @app.get("/instellingen/health")
    def config_health() -> dict[str, dict[str, object]]:
        """Per-bron koppelstatus — één bron van waarheid, ook voor het configscherm.

        Bewust géén tweede koppel-administratie ernaast: twee plekken die zeggen of
        een bron werkt lopen uiteen, en deze bevraagt het echte systeem.
        """
        return bron_health()

    @app.get("/landschap")
    def landschap_staat() -> dict[str, object]:
        """Wat er is ingelezen: hoeveel documenten, per bron, en wanneer voor het laatst.

        Bewust buiten elke audit: de voorraad is van de organisatie en wordt door alle
        audits gebruikt. De opslag was al gedeeld; alleen de handeling hing er nog onder.
        """
        from iso_audit.api import landschap

        return landschap.staat()

    @app.get("/landschap/documenten")
    def landschap_documenten(
        zoek: str = "", bron: str = "", limiet: int = 200
    ) -> list[dict[str, object]]:
        """De ingelezen documenten met hun clausule-koppelingen, doorzoekbaar.

        Dit is waarop een auditor controleert óf het landschap klopt: welke bestanden zijn
        gezien, waar komen ze vandaan, aan welke clausules zitten ze. Zonder dat scherm is
        een run een black box.
        """
        from iso_audit.api import landschap

        return landschap.documenten(zoek=zoek, bron=bron, limiet=limiet)

    @app.post("/assistent/vraag")
    def assistent_vraag(body: AssistentVraag, request: Request) -> dict[str, object]:
        """Beantwoord één vraag uit het corpus. Leest; schrijft alleen in de trail.

        Achter dezelfde auth-gate als de rest van het portaal: het corpus bevat
        auditbevindingen en interne memo's, en openstellen is een publicatiebesluit met een
        eigen afweging.

        Geweigerd tijdens een lopende run, om dezelfde reden als bij de configuratieroute:
        een vraag tijdens een run leest een halve werkset, en het antwoord zou een dekking
        suggereren die pas na de run bestaat.

        Een onverifieerbaar antwoord is een storing en wordt als 502 teruggegeven — niet als
        antwoord met een waarschuwing eronder, want een auditor die een plausibel antwoord
        ziet met een voetnoot leest het antwoord.
        """
        from iso_audit.assistent import vraag as assistent
        from iso_audit.store import bewaar_assistentvraag, initialiseer, verbinding

        tekst = body.vraag.strip()
        if not tekst:
            raise HTTPException(status_code=400, detail="Geen vraag opgegeven.")
        loopt = _run_loopt()
        if loopt:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Er loopt een run in audit {loopt}. Wacht tot die klaar is: een vraag "
                    "tijdens een run leest een halve werkset."
                ),
            )
        wie = identiteit_van(request)
        conn = verbinding()
        try:
            initialiseer(conn)
            try:
                uit = assistent.beantwoord(conn, tekst, norm=body.norm)
            except (assistent.AntwoordOnverifieerbaarError, OnleesbaarAntwoordError) as exc:
                # Ook een storing gaat in de trail: dat is het enige spoor dat de
                # verwijzingscontrole heeft gewerkt.
                _, veilig = normaliseer(exc, bron="assistent")
                bewaar_assistentvraag(
                    conn,
                    agent="bronbevrager",
                    record={"vraag": tekst, "antwoord": "", "model": ""},
                    storing=str(exc)[:500],
                    gesteld_door=wie,
                )
                raise HTTPException(status_code=502, detail=veilig) from exc
            except Exception as exc:
                # Een onverwachte fout liet tot 2026-08-24 géén spoor na: alleen de twee
                # bekende assistent-fouten werden opgevangen. Die dag gaf elke vraag met een
                # koppelteken een 500 (FTS5 las `non-conformiteiten` als kolomnaam), en
                # achteraf was niet vast te stellen wát er gevraagd was toen het misging —
                # precies het moment waarop de trail het meest waard is.
                #
                # De fout wordt onveranderd doorgegeven: dit is een fout in onze eigen code en
                # geen weigering van de verwijzingscontrole, en dat onderscheid hoort zichtbaar
                # te blijven in de status én in de stacktrace.
                bewaar_assistentvraag(
                    conn,
                    agent="bronbevrager",
                    record={"vraag": tekst, "antwoord": "", "model": ""},
                    storing=f"{type(exc).__name__}: {exc}"[:500],
                    gesteld_door=wie,
                )
                raise
            record = uit.als_record()
            bewaar_assistentvraag(conn, agent="bronbevrager", record=record, gesteld_door=wie)
        finally:
            conn.close()
        log_event("assistent_vraag", wie, bronnen=str(len(uit.meegegeven)))
        return record

    @app.post("/landschap/ingest")
    def landschap_inlezen(
        request: Request, body: LandschapVerzoek | None = None
    ) -> dict[str, object]:
        """Lees de gekozen bronnen in en leg vast wat er gelezen is.

        Raakt de classificatie-API niet, dus dit werkt zonder Anthropic-key en is de manier
        om de keten naar de bronnen te verifiëren los van het oordeel.

        Synchroon: dit kan minuten duren, maar het is een expliciete handeling waarvan de
        auditor de uitkomst wil zien. Een achtergrondtaak zou hier een tweede
        voortgangs-administratie vragen naast die van de runs.
        """
        from iso_audit.api import landschap

        r = body or LandschapVerzoek()
        wie = identiteit_van(request)
        try:
            valideer_bronselectie(r.bronnen, streng=True)
        except SessionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        log_event("landschap_ingest", wie, bronnen=",".join(r.bronnen))
        uit = landschap.lees_in(r.bronnen)
        return uit

    @app.get("/instellingen/health/{bron}")
    def config_health_bron(bron: str) -> dict[str, object]:
        """Koppelstatus van één bron — de "Testen"-knop naast het formulier.

        Apart van `/instellingen/health` omdat dat álle bronnen langsgaat: wie een Jira-token
        invult wil niet wachten op een Drive-listing, en wil ook niet zelf ergens anders
        gaan kijken of het gelukt is.
        """
        from iso_audit.api.session import _check_source
        from iso_audit.ingest import beschikbare_bronnen

        if bron not in beschikbare_bronnen():
            raise HTTPException(status_code=404, detail=f"Onbekende bron: {bron}")
        return _check_source(bron)

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        """Het portaal is één HTML-bestand, zonder buildstap en dus zonder versie in de URL.

        Daarom expliciet `no-store`: zonder cache-header stuurde deze route een kale 200 en
        cachet een browser hem heuristisch. Na een uitrol zit een auditor dan op een oud
        scherm zonder het te weten — precies het soort stille afwijking dat dit tool juist
        hoort te voorkomen. Het bestand is klein en wordt uit het geheugen geserveerd, dus
        opnieuw ophalen kost niets.
        """
        return HTMLResponse(_UI_HTML, headers={"Cache-Control": "no-store"})

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
