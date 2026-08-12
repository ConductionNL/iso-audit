# Design — iso-portal

## De clevere valkuil, vooraf

De opdracht was "migreer de adapters naar MCP waar mogelijk". De inventarisatie
levert een ongemakkelijk antwoord: **MCP lost het probleem niet op.**

De beschikbare MCP-servers voor Atlassian, Google Drive en Gmail zijn
claude.ai-connectors die **per gebruiker via OAuth** authenticeren. De `gws` CLI
inruilen voor een Drive-connector verplaatst de persoonlijke credential van
`~/.config/gws` naar een OAuth-grant op dezelfde persoon — en werkt niet in een
headless portaalrun, want er is geen mens om de consent-flow te doorlopen. Het
zou een migratie zijn die de auditbevinding netjes lijkt af te dekken en er
feitelijk niets aan verandert.

Ontpersoonlijking komt van het **credential-model**: een Workspace service
account, een functioneel Atlassian-account, een org-owned Miro-token. MCP is
daarbovenop een transportkeuze — nuttig als het code weghaalt, verder niet.
Daarom: **credentials eerst, MCP per bron beoordeeld, en de uitkomst per bron
opgeschreven.**

Zelf-hosten van MCP-servers in-cluster met org-keys zou de OAuth-bezwaren
wegnemen, maar voegt drie services toe die beheerd, gemonitord en geaudit moeten
worden om REST-code te vervangen die werkt. Afgewezen op boring-and-auditable.

## Gekloond patroon — openwoo-app-provisioner

Bron: `openwoo-app-config/webgui/deploy/`. De ArgoCD-Application van openwoo
woont elders (`Nextcloud-base/nextcloud-platform/argo/apps/openwoo-provisioner.yaml`).

```
Ingress (nginx, TLS via cert-manager, letsencrypt-prod)
   └─▶ Service :80 ──▶ pod :4180  oauth2-proxy ──OIDC──▶ Keycloak ──brokers──▶ Google
                            │ (X-Forwarded-Email)
                            ▼
                       app 127.0.0.1:8081  (uvicorn, FastAPI) ── faalt gesloten
```

Het trust-anker onder `X-Forwarded-Email` bestaat uit twee dingen, en beide
worden meegenomen:

1. **Topologie.** De app bindt `127.0.0.1`; oauth2-proxy is de enige
   netwerk-listener in de pod. Een NetworkPolicy laat pod-ingress alleen toe uit
   `ingress-nginx` op `:4180`.
2. **Fail closed.** `REQUIRE_AUTH` staat default aan; een request zonder
   identity-header krijgt 403. Een verkeerd geconfigureerde ingress degradeert
   naar "op slot", niet naar "open".

`serve()` in `api/app.py:219` bindt al default op `127.0.0.1`. Dat blijft zo —
het is precies wat het sidecar-patroon vraagt.

### Wat wordt gekloond, wat niet

| Nieuw bestand | Herkomst | Wijziging |
|---|---|---|
| `deploy/oauth2-proxy.cfg` | `webgui/deploy/oauth2-proxy.cfg` | vrijwel 1-op-1: `provider = keycloak-oidc`, issuer `iam.commonground.nu/realms/commonground`, `email_domains = ["conduction.nl"]`, `session_cookie_minimal`, `cookie_secure`/`samesite=lax`/`8h`, `skip_provider_button = false`, `whitelist_domains = ["iam.commonground.nu"]`. Alleen `client_id`, `redirect_url` en upstream wijzigen |
| `deploy/deployment.yaml` | idem | 2-container-patroon behouden (app + `oauth2-proxy:v7.7.1`), hardened securityContext behouden. **Weg:** GITHUB_TOKEN/TENANTS_REPO/REVEAL/ASSISTANT/PROMETHEUS-env en `automountServiceAccountToken: true`. **Nieuw:** SA-keyfile-mount, bron-env uit Secrets, PVC-mount |
| `deploy/ingress.yaml` | idem | host `iso.commonground.nu`, `secretName: iso-audit-portal-tls`, HSTS. Streaming-annotaties **behouden**: `/run/progress` polt een langlopende run en de memo-render duurt |
| `deploy/networkpolicy.yaml` | idem | 1-op-1 |
| `deploy/service.yaml`, `namespace.yaml`, `serviceaccount.yaml` | idem | namen → `iso-platform` / `iso-audit-portal`; token-automount **uit** |
| `deploy/kustomization.yaml` | idem | `configMapGenerator` voor de proxy-cfg (edit rolt de pod), `images: ghcr.io/conductionnl/iso-audit` |
| `deploy/secret.example.yaml` | idem | template; echte Secrets out-of-band |
| `deploy/README.md`, `docs/explanation/portal-auth.md`, `docs/how-to/verify-portal-auth.md` | `deploy/README.md` + `webgui/auth/README.md` | het fail-closed trust-model als proza. Dat is het auditbewijs — een reviewer moet kunnen nalezen *waarom* de header te vertrouwen is |
| `Dockerfile` | nieuw | `uv sync --frozen` (nooit pip), non-root, compatibel met `readOnlyRootFilesystem`, uvicorn op `127.0.0.1:8081`. WeasyPrint-systeemlibs meenemen — anders faalt de PDF-render pas in productie |
| `.github/workflows/image.yml` | openwoo's variant | merge-is-deploy: `sha-<short>` bouwen, pullbaarheid verifiëren, `newTag` terugcommitten met `[skip ci]` |

**Niet gekloond:** `rbac-argo.yaml` en `rbac-secrets.yaml` (openwoo-specifiek:
Argo-status-poll en nextcloud-secrets-reveal — het portaal heeft geen
kube-API-toegang nodig). `networkpolicy-egress.yaml` niet: staat in het origineel
bewust uit sinds 2026-07-13.

## Vastgelegde ontwerpbesluiten

1. **Geen eigen auth.** Het Keycloak-patroon van openwoo wordt overgenomen:
   realm `commonground`, confidential OIDC-client, Google gebrokerd binnen
   Keycloak. De app integreert dus met één identity-provider, niet twee.
2. **De audit-trail op een PVC, niet emptyDir.** openwoo gebruikt emptyDir omdat
   zijn state in Git leeft. Hier is de state het bewijs: `triage_log.jsonl` is
   append-only en `store.py` houdt append-only `decisions`/`classifications`.
   Verlies bij pod-restart zou de auditeerbaarheid breken die `CLAUDE.md` als
   harde eis stelt.
3. **Eén auditsessie per deployment in v1.** `create_app(session)` neemt één
   `AuditSession`. Een multi-sessie-portaal vraagt sessie-selectie, autorisatie
   per sessie en isolatie van de trail — een eigen change waard, geen bijproduct.
4. **Argo-Application in deze repo, handmatig ge-bootstrapt.** `cluster-infra` is
   expliciet voor cluster-brede infra; `nextcloud-platform` is de verkeerde
   projectgrens (dit is geen Nextcloud). Dus: AppProject `iso-platform` +
   Application `iso-audit-portal` onder `argo/` in deze repo, eenmalig met
   `kubectl apply` ge-bootstrapt — het patroon dat `cluster-infra` al gebruikt.
   Application: `repoURL https://github.com/ConductionNL/iso-audit.git`,
   `path: deploy`, namespace `iso-platform`, `automated` + `CreateNamespace=true`.
5. **DNS vraagt geen handmatige stap.** external-dns kijkt cluster-breed naar
   Ingresses met domain-filter `commonground.nu` en maakt het record uit de
   Ingress zelf. Dat wijkt af van openwoo's README, die DNS nog als prerequisite
   noemt.
6. **Secrets out-of-band, één mechanisme.** Cluster-Secrets in `iso-platform`,
   aangemaakt buiten Git — de conventie die openwoo's `secret.example.yaml` en
   `KeyCloak/docs/REALMS.md:26` al zetten. Wil je ze versleuteld in Git, dan
   SOPS/age **óf** External Secrets (ESO staat al in `cluster-infra`), niet beide
   naast elkaar.

## Schrijfpaden en hun fallbacks

Gemeten 2026-08-12 (taak 2.1). Wat het portaal wegschrijft, en waar het landt als
niemand het configureert:

| Pad | Herkomst | Fallback zonder config |
|---|---|---|
| `findings.json`, `triage_log.jsonl` | `AuditSession`, expliciet argument | **geen** — `SessionError` als `findings.json` ontbreekt; al conform |
| `Auditmemo_management.pdf` | `session.dir` | volgt de sessie-dir; al conform |
| SQLite `audit.db` (`decisions`, `classifications`) | `AUDIT_DB_PATH` | `<repo>/output/audit.db` — **binnen het image** |
| Auditrapporten | `LOCAL_REPORT_DIR` / `AUDIT_RUN_ID` | `<repo>/output/audit_reports/<run>` — **binnen het image** |

De onderste twee zijn het probleem: onder `readOnlyRootFilesystem: true` faalt die
write, en zonder de PVC uit taak 2.4 is een append-only trail op een vluchtig
filesystem geen trail. `AUDIT_DB_PATH` is in taak 2.2 van een stille fallback een
gemelde fallback geworden, en het portaal zet hem expliciet in `deployment.yaml`.

`LOCAL_REPORT_DIR` is in deze change **niet** aangepast: het betreft rapport-output
en niet de audit-trail, en valt buiten de scope die taak 2 afbakent. Het staat hier
zodat het een vastgelegd punt is en geen verrassing bij de eerste render in het
cluster.

## Keycloak — buiten deze repo

Eén client toevoegen aan
`KeyCloak/clusters/prod/keycloak/20-keycloak/realm-commonground.yaml`, als kopie
van het `openwoo-provisioner`-blok (regels 244-270):

- `clientId: iso-audit-portal`, confidential, `standardFlowEnabled: true`,
  `directAccessGrantsEnabled: false`
- `redirectUris: [https://iso.commonground.nu/oauth2/callback]` + `webOrigins`
- attribuut `post.logout.redirect.uris` in de `##`-vorm (RP-initiated logout)
- `defaultClientScopes: openid profile email`, optioneel `groups`

Prod-pad-edit → aparte PR met expliciete confirmatie. Client secret niet in Git.

**Erfelijke afwijking, te documenteren en niet hier op te lossen:** de Google
identity provider is handmatig via de Keycloak-UI aangemaakt en staat expliciet
niet in de realm-import (`realm-commonground.yaml:198-201`, met reden). De nieuwe
client erft die situatie; hem hier rechttrekken zou de scope van deze change
verdubbelen.

## Migratiebesluit per bron

| Bron | Auth nu | Doel | MCP-besluit |
|---|---|---|---|
| `drive` (`sources/drive.py`) | `gws` CLI, persoonlijke OAuth-sessie | service account via het bestaande `auth.py` (`drive_read_service`, scopes `drive.readonly` + `documents.readonly`); keyfile uit cluster-Secret; auditmap expliciet met het SA gedeeld | **nee** — Drive-connector dekt search/read functioneel, maar is per-user-OAuth |
| `planning` (`sources/planning.py`) | `gws` CLI (SA-modus is destijds bewust geschrapt) | `auth.py`-`sheets_service`; planning-sheet met het SA gedeeld; hardcoded default sheet-ID (`planning.py:35`) naar config | **nee, functieverlies** — geen `values.get` / multi-tab in de Drive-connector |
| `jira` (`sources/jira.py`) | persoonlijk Atlassian API-token (staat zo in de docstring) | functioneel Atlassian-account; token in cluster-Secret; adaptercode ongewijzigd (env-vars volstaan) | **bewuste uitzondering** — Atlassian-MCP is plausibel dekkend, maar haalt geen code weg: 271 regels REST die werkt, tegen een nieuwe runtime-afhankelijkheid |
| `miro` (`miro/client.py`) | persoonlijk token | org-owned token of Miro-app; READ-only blijft | **geen MCP beschikbaar** — expliciete uitzondering |
| `slack` / `email` (notifiers) | env-tokens, herkomst niet in de repo vastgelegd | org-owned Slack-webhook of bot-token op een Conduction-app; SMTP via org-relay-account — dat vervangt ook de `gmail.send`-scope uit `auth.py` | Slack-MCP bestaat maar is een notifier, geen bron: geen winst. Gmail-MCP heeft `create_draft` en **geen send** → functieverlies |
| Anthropic | `ANTHROPIC_API_KEY` | org-workspace-key. Geen persoonlijke subscription-token — openwoo legde dat als *tijdelijke* afwijking vast; die niet overnemen | n.v.t. |

Netto: **nul bronnen naar MCP** in deze ronde. Dat staat hier als besluit met
reden per bron, niet als stille omissie.

Twee Google-auth-paden bestaan nu naast elkaar: `auth.py` (service account,
least-privilege scopes, org-capable) en `clients/gws.py` (persoonlijke CLI). De
migratie convergeert op `auth.py` en maakt `clients/gws.py` daarna overbodig —
opruimen gebeurt in de bron-changes, niet hier.

## Credential-model

- **Opslag:** cluster-Secrets in `iso-platform`, out-of-band aangemaakt, nooit in
  Git.
- **Eigenaar:** `info@conduction.nl`, als `owner:`-frontmatter in
  `deploy/README.md` — dezelfde vorm die `KeyCloak/docs/REALMS.md` gebruikt.
- **Herleidbaarheid:** één tabel in `deploy/README.md`: credential → systeem →
  Secret-naam → org-account → eigenaar-rol → rotatiemoment. Dat is wat een
  auditor vraagt, en het koppelt aan een rol.
- **Intrekken hoort bij migreren.** Een bron waarvan het org-credential werkt
  terwijl het persoonlijke token nog geldig is, is niet gemigreerd. Elke
  bron-change eindigt met intrekken + een `CHANGELOG.md`-entry die vermeldt welk
  persoonlijk credential is ingetrokken en op welke datum.

## Stack & grenzen

- Geen nieuwe Python-dependencies. FastAPI, uvicorn en pydantic staan al in
  `pyproject.toml`; de auth-gate is stdlib + FastAPI.
- `uv` blijft: `uv sync --frozen` in CI en in het image, nooit `pip`.
- Max 200 regels per file; `auth_gate.py` blijft een dunne laag (~60 regels).
- Geen stille fallback: ontbrekende config geeft een harde, leesbare fout — de
  discipline die `specs/connector-orchestration` uit `auditmemo-ui` al eist.

## Niet opgelost / aandachtspunten

- **SOPS/age versus External Secrets.** Beide passen bij de huisstijl. Te kiezen
  bij implementatie van taak 4.1; de eis is dat het er precies één wordt.
- **PVC-storageclass en -grootte.** Afhankelijk van wat op de Gardener-shoot
  beschikbaar is; vast te stellen bij taak 2.4.
- **Wie de auditor-rol krijgt in Keycloak.** `email_domains = ["conduction.nl"]`
  is de grove poort die openwoo ook gebruikt. Fijnmaziger via de bestaande
  `groups`-scope is mogelijk, maar vraagt een groep-naar-rol-mapping in het
  portaal — een eigen change.
- **Repo-transfer eerst.** De ghcr-namespace `conductionnl` en `CODEOWNERS`
  hangen aan de transfer. Zolang die niet gedaan is, kan taak 3 (image) niet af.
