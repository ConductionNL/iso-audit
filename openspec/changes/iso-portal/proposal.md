# Proposal — iso-portal

## Why

De tool draait vandaag vanaf één werkstation op de persoonlijke credentials van
één medewerker: de `gws` CLI met diens OAuth-sessie (`~/.config/gws`) voor Drive
en Sheets, een persoonlijk Atlassian API-token voor Jira, en een persoonlijk
Miro-token. De repo zelf staat op `github.com/MWest2020/iso-audit` met een
persoonlijk e-mailadres als `authors` in `pyproject.toml`.

Die medewerker vertrekt eind augustus 2026. Zonder ingrijpen verdwijnt daarmee de
ISO 27001/9001-auditcapability, en zolang het zo staat is in een ISO 27001-audit
de hele keten — code-eigendom én toegang tot elk bronsysteem — terug te voeren op
één natuurlijk persoon. Dat is precies het soort single-point-of-dependency dat
de norm bij een auditwerktuig niet accepteert.

Wat er moet komen: een portaal op `iso.commonground.nu` waar auditors de tool
draaien, met uitsluitend org-owned credentials waarvan de eigenaar een **rol**
is (`info@conduction.nl`), niet een persoon.

**Capability-raking** (`docs/explanation/missie.md`): dit versterkt capability 1
(*onafhankelijke bronnen — toegang van tevoren ingericht en daarna onveranderlijk
binnen een auditperiode*). Vandaag is die "vooraf ingerichte toegang" in de
praktijk de sessie van één mens, die met diens vertrek verdampt. Na deze change
is het een org-account met expliciet gedeelde scope. Capability 2
(patroondetectie) en 3 (auditor-spiegel) worden niet geraakt.

## What Changes

- **Portaal-deployment.** Een `Dockerfile` (uv, non-root) en `deploy/`-manifests
  die de bestaande FastAPI-app (`src/iso_audit/api/app.py`) achter oauth2-proxy →
  Keycloak zetten op `iso.commonground.nu`. Het patroon is 1-op-1 gekloond van
  `openwoo-app-provisioner` (`openwoo-app-config/webgui/deploy/`) — geen nieuwe
  auth-laag, geen eigen sessiebeheer.
- **Fail-closed identity-gate.** Nieuw `src/iso_audit/api/auth_gate.py`: leest de
  identity-header die oauth2-proxy zet, `REQUIRE_AUTH` default `true`, 403 op
  alles behalve `/healthz`. Poort van de `current_user()`-gate uit openwoo's
  `webgui/server.py`.
- **Persistente audit-trail.** De sessie-directory (`findings.json` +
  append-only `triage_log.jsonl`) en de SQLite-DB (`AUDIT_DB_PATH`, met de
  append-only `decisions`/`classifications`-tabellen) gaan op een PVC. Dat is
  auditbewijs; het mag een pod-restart niet verliezen.
- **Credential-model.** Elk credential dat de tool gebruikt wordt org-owned,
  opgeslagen als cluster-Secret buiten Git, met een herleidbaarheidstabel
  credential → systeem → Secret → org-account → eigenaar-rol → rotatiemoment.
- **Migratiebesluit per bron, inclusief de uitzonderingen.** Vastgelegd in
  `design.md`: welke bron naar welk org-credential gaat, en per bron of een MCP
  passend is. Netto migreert in deze ronde **geen enkele** bron naar MCP; de
  reden staat per bron benoemd, zodat het een besluit is en geen omissie.

- **Toewijsbare trail en begrensde toegang.** Uit de security-audit op deze specs
  kwamen zeven gaps, nu als eis opgenomen. De vier materiële: de geverifieerde
  identiteit landt als `actor` in de trail (het veld bestaat al in
  `api/session.py:134`, de API geeft het niet mee — élke regel zegt nu dezelfde
  placeholder); toegang eindigt binnen een gedocumenteerd venster in plaats van
  pas bij cookie-verval; de deploy-keten staat in het credential-model en is niet
  ongereviewd te verleggen; auth-events worden gelogd en credentials niet.

Buiten deze repo, als aparte PR's: één Keycloak-client `iso-audit-portal` in de
realm `commonground`, en de repo-transfer naar `ConductionNL/iso-audit`.

## Capabilities

### Added Capabilities

- `portal-deployment` — de tool is als container achter Argo CD te deployen, met
  de audit-trail op persistente opslag.
- `portal-auth` — toegang loopt via het bestaande Keycloak-patroon; de app faalt
  gesloten zonder geverifieerde identiteit.
- `credential-model` — geen credential is persoonsgebonden; eigenaarschap is een
  rol en de koppeling is herleidbaar.

### Unmodified

De Source/Mode/Notifier-architectuur, de drie registries, de `Document`/
`Finding`-shapes, de append-only trail, de zeven beslispunten en de modes
`autonoom`/`integer` blijven ongewijzigd. De migratie vraagt **geen enkele
interface-wijziging**: alleen de auth-implementatie *binnen* een adapter wisselt.
Contracten blijven staan waar ze staan (`sources/base.py`, `sinks/base.py`,
`notifiers/base.py`).

## Scope-grens

**In scope:** het portaal (image, manifests, auth-gate, PVC), het
credential-model als document, en het vastgelegde migratieplan per bron.

**Buiten scope, expliciet:**

- **De feitelijke connector-migraties.** Elke bron krijgt een eigen change
  (`gsuite-service-account-sources`, `jira-functional-account`,
  `miro-org-token`, `notifier-org-credentials`), in die volgorde. Eén bron per
  keer, zodat een mislukte migratie één bron raakt en niet de auditcapability.
- **Meerdere gelijktijdige auditsessies.** `create_app(session)` neemt één
  `AuditSession` en `iso-audit ui --session <dir>` één working-dir. Het
  portaal serveert in v1 dus één auditsessie per deployment. Sessie-selectie is
  een latere change — niet een sluipende uitbreiding hier.
- **Een GitHub-source.** Die bestaat niet in deze repo (enige spoor: een
  TODO-comment in `sources/protocol_ingest.py:6`). Nieuwbouw, geen migratie.
- **De egress-NetworkPolicy.** Het openwoo-origineel staat sinds 2026-07-13
  bewust uitgeschakeld (brak DNS op prod, tweede keer onder Gardener/Calico).
  Meenemen zou een bekend defect kopiëren.
- **Rotatie-automatisering.** Het model legt rotatiemomenten vast; het
  automatiseren ervan is later werk.
