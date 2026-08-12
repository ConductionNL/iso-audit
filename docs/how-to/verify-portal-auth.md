---
status: draft
last_reviewed: 2026-08-12
---

# Fail-closed verifiëren zonder cluster

De fail-closed-stand van het portaal is lokaal aan te tonen, zonder oauth2-proxy,
zonder Keycloak en zonder cluster. Dat is het punt: het auditbewijs is niet dat de
code klopt, maar dat iemand het zelf kan naspelen.

Het *waarom* achter deze stand staat in
[portal-auth](../explanation/portal-auth.md).

## Met de testsuite

```bash
uv run pytest tests/api/test_auth_gate.py -v
```

Dekt: 403 zonder header, 200 met `X-Forwarded-Email`, `X-Forwarded-User` als
fallback, een lege header die niet als identiteit telt, `/healthz` altijd open, de
UI-route wél bewaakt, `REQUIRE_AUTH=false` laat door, en de actor in de trail.

## Met een draaiende server

Start de app zoals het portaal dat doet — gebonden aan localhost:

```bash
uv run iso-audit ui --session <sessie-dir> --profile <slug> \
  --norms examples/norms --memo-input <memo-input.yaml> \
  --host 127.0.0.1 --port 8081
```

Dan, in een tweede terminal:

```bash
# default (REQUIRE_AUTH aan): geen identity-header -> 403
curl -si http://127.0.0.1:8081/findings | head -1

# mét de header die oauth2-proxy in productie zet -> 200
curl -si -H 'X-Forwarded-Email: jij@conduction.nl' \
     http://127.0.0.1:8081/findings | head -1

# de probe blijft open, ook met de gate aan -> 200
curl -si http://127.0.0.1:8081/healthz | head -1
```

Voor lokale ontwikkeling zonder proxy:

```bash
REQUIRE_AUTH=false uv run iso-audit ui --session <sessie-dir> --profile <slug> \
  --norms examples/norms --memo-input <memo-input.yaml>
```

Let op wat er dan in de trail komt te staan: `actor` wordt
`dev:auth-uitgeschakeld`. Dat is opzet — een dev-run mag niet als een mens
gelezen kunnen worden.

## Controleren dat de actor klopt

Na een triage-beslissing via het portaal:

```bash
curl -s -H 'X-Forwarded-Email: jij@conduction.nl' \
     http://127.0.0.1:8081/trail | python3 -m json.tool | grep actor
```

Er hoort je eigen adres te staan. Staat er `"auditor"`, dan is de identiteit niet
doorgegeven en is de trail niet toewijsbaar.

## Toegang beëindigen bij offboarding

Het uitzetten van een Keycloak-account is **niet** voldoende: de sessie-cookie
draagt de identiteit zelf, dus een al uitgegeven cookie blijft geldig tot hij
verloopt. Beëindig daarom beide:

1. het account of de groepslidmaatschap in Keycloak, én
2. de actieve sessies van die gebruiker in de realm (`Sessions` → `Logout`),
   zodat er geen nieuwe cookie meer gemint kan worden.

De maximale restduur bij alleen stap 1 is de cookie-levensduur uit
`deploy/oauth2-proxy.cfg`. Die waarde is een vastgelegd geaccepteerd risico; zie
taak 1.6 van de change `iso-portal`.
