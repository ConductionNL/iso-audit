---
status: draft
last_reviewed: 2026-08-12
---

# Portaal-authenticatie — waarom de identity-header te vertrouwen is

Het portaal op `iso.commonground.nu` heeft **geen eigen login**. Er staat
[oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/) voor, die de auditor
tegen **Keycloak** authenticeert (realm `commonground`,
`https://iam.commonground.nu`). Keycloak brokert op zijn beurt Google als identity
provider, zodat auditors met hun Google-account inloggen terwijl de app maar met
één identity-provider integreert — één integratie om te auditen, niet twee.

```
browser ──▶ oauth2-proxy ──OIDC──▶ Keycloak ──brokert──▶ Google
                  │  (zet X-Forwarded-Email / X-Forwarded-User)
                  ▼
            FastAPI-app (127.0.0.1:8081) ── faalt gesloten zonder die header
```

Dit patroon is 1-op-1 overgenomen van `openwoo-app-provisioner`
(`openwoo-app-config/webgui/auth/README.md`). Bewust: er is één trust-model in de
organisatie, niet één per applicatie.

## Het trust-model

De app vertrouwt `X-Forwarded-Email` **niet omdat de header er staat**, maar omdat
twee dingen buiten de applicatiecode het afdwingen.

**1. Topologie.** De app bindt `127.0.0.1`. oauth2-proxy is de enige
netwerk-listener in de pod, en een NetworkPolicy laat pod-ingress alleen toe uit de
`ingress-nginx`-namespace op de proxy-poort. Er is dus geen pad waarlangs iets
anders de header kan zetten.

**2. Fail closed.** `REQUIRE_AUTH` staat default aan. Een request zonder
identity-header krijgt 403, met als enige uitzondering het probe-endpoint
`/healthz`. Een verkeerd geconfigureerde ingress degradeert daarmee naar "op slot",
niet naar "open".

Die twee samen zijn het anker. Eén van de twee is niet genoeg: zonder de
localhost-bind is de header spoofbaar en is de fail-closed-check schijnzekerheid;
zonder de fail-closed-stand is een ontbrekende proxy een open portaal.

## Middleware, geen dependency per route

De gate zit in `iso_audit.api.auth_gate` als HTTP-middleware, niet als een
`Depends()` op elke route. Reden: een dependency moet bij élk nieuw endpoint
opnieuw worden aangezet, en vergeten betekent stil een open route. Middleware dekt
alles wat er is en alles wat er nog bij komt; een nieuw endpoint is beschermd
tenzij iemand het expliciet in `OPEN_PADEN` zet. De veilige default is de
default.

Een onbekende waarde in `REQUIRE_AUTH` (een typfout als `maybe`) betekent
**aan**. Alleen expliciete uit-waarden zetten de gate uit. Een typfout mag geen
portaal openzetten.

## De identiteit landt in de audit-trail

De gate zet de vastgestelde identiteit op `request.state.identiteit`, en
`POST /findings/{id}` geeft die door als `actor` aan `AuditSession.apply_triage()`.
Daarmee is elke regel in `triage_log.jsonl` toewijsbaar aan een mens.

Dat was eerder niet zo: het `actor`-veld bestond al en werd al weggeschreven, maar
de API gaf het niet mee, waardoor élke trail-regel de default `"auditor"` bevatte.
Een append-only trail zonder toewijsbare actor beantwoordt de eerste vraag van een
auditor niet — wie heeft deze bevinding gevalideerd of verworpen.

Draait de app met `REQUIRE_AUTH=false`, dan is de actor de onmiskenbare waarde
`dev:auth-uitgeschakeld`. Bewust greppbaar: als dat ooit in een echte trail
opduikt, is het direct herkenbaar als een dev-run in plaats van te worden
aangezien voor een mens.

## Wat dit model niet oplost

De sessie-cookie draagt de identiteit zelf (`session_cookie_minimal`), zodat de
cookie klein blijft. Gevolg: een Keycloak-account uitzetten maakt een al uitgegeven
cookie **niet** ongeldig. Toegang eindigt dan pas bij cookie-verval. Bij
offboarding is het uitzetten van het account dus niet genoeg — zie
[verify-portal-auth](../how-to/verify-portal-auth.md) voor de handeling die
toegang direct beëindigt, en de change `iso-portal` voor de vastgelegde maximale
restduur.

## Verwant

- [Fail-closed verifiëren zonder cluster](../how-to/verify-portal-auth.md)
- `openspec/changes/iso-portal/specs/portal-auth/spec.md` — de eisen
- `openspec/changes/iso-portal/design.md` — waarom dit patroon en niet een eigen
  auth-laag
