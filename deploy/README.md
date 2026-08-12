---
owner: info@conduction.nl
last_reviewed: 2026-08-12
---

# Deploy — het iso-audit-portaal op Kubernetes

Zet de auditor-API achter oauth2-proxy → Keycloak op `https://iso.commonground.nu`.

```
Ingress (nginx, TLS via cert-manager)
   └─▶ Service :80 ──▶ pod :4180  oauth2-proxy ──auth──▶ Keycloak ──▶ Google
                                       │ (X-Forwarded-Email)
                                       ▼
                                  app 127.0.0.1:8081  (uvicorn, FastAPI)
                                       │
                                       ▼
                                  PVC /var/lib/iso-audit  (de audit-trail)
```

Eén pod, twee containers. De app bindt **alleen localhost**; oauth2-proxy is de
enige netwerk-listener. Een NetworkPolicy laat pod-ingress bovendien **alleen** toe
uit de `ingress-nginx`-namespace op `:4180`. Samen is dat het trust-anker onder
`X-Forwarded-Email` — zie [portal-auth](../docs/explanation/portal-auth.md).

## Manifests

| Bestand | Wat |
|---|---|
| `namespace.yaml` | namespace `iso-platform` |
| `serviceaccount.yaml` | SA met token-automount **uit** (geen kube-API nodig) |
| `pvc.yaml` | `tier-1`, 8Gi, RWO — de audit-trail, géén emptyDir |
| `deployment.yaml` | app (uvicorn op localhost) + oauth2-proxy-sidecar; hardened securityContext |
| `service.yaml` | ClusterIP `:80 → :4180` |
| `ingress.yaml` | nginx + `letsencrypt-prod`; lange timeouts voor runs en render |
| `networkpolicy.yaml` | ingress alleen uit `ingress-nginx` |
| `oauth2-proxy.cfg` | proxy-config (Keycloak-OIDC; → gehashte ConfigMap via kustomize) |
| `secret.example.yaml` | **template** — echte Secrets out-of-band |
| `../argo/` | AppProject `iso-platform` + Application `iso-audit-portal` |

**Bewust niet aanwezig:** `rbac-*.yaml` (dit portaal pollt geen Argo-status, anders
dan openwoo-provisioner) en `networkpolicy-egress.yaml` (het origineel staat sinds
2026-07-13 uit wegens DNS-breuk onder Gardener/Calico — meenemen zou een bekend
defect kopiëren).

## Prerequisites

1. **Keycloak-client** `iso-audit-portal` in realm `commonground` (KeyCloak-repo,
   `clusters/prod/keycloak/20-keycloak/realm-commonground.yaml`), redirect
   `https://iso.commonground.nu/oauth2/callback`, met het
   `post.logout.redirect.uris`-attribuut. Kopie van het `openwoo-provisioner`-blok.
2. **Secrets** out-of-band aangemaakt — zie `secret.example.yaml` voor de
   commando's. Alleen `iso-audit-portal-oauth` is verplicht.
3. **Image** gebouwd en gepusht, en de ghcr-package op **public** (anders heeft de
   namespace een pull-secret nodig).
4. **Sessie-inhoud op de PVC.** `iso-audit ui` heeft geen env-fallbacks: het
   verwacht `/var/lib/iso-audit/sessie/findings.json`,
   `/var/lib/iso-audit/sessie/memo-input.yaml` en
   `/var/lib/iso-audit/conduction.profile.yaml`. Ontbreekt de findings, dan stopt de
   app met een leesbare fout in plaats van een lege sessie te verzinnen.

**DNS vraagt geen stap.** external-dns kijkt cluster-breed naar Ingresses met
domain-filter `commonground.nu` en maakt het record uit `ingress.yaml`.

## Bootstrap (eenmalig, met de hand)

Argo CD wordt via Helm beheerd, dus een nieuw project registreer je één keer zelf —
het patroon dat `cluster-infra` ook gebruikt:

    kubectl apply -f argo/projects/iso-platform.yaml
    kubectl apply -f argo/applications/iso-audit-portal.yaml

Daarna synct Argo `deploy/` zelf. Handmatig kan ook: `kubectl apply -k deploy`
(nadat de Secrets bestaan).

## Verifiëren

    kubectl -n iso-platform rollout status deploy/iso-audit-portal
    curl -sS https://iso.commonground.nu/healthz     # ok, zonder login
    # / vraagt een Google-login via Keycloak

Daarna: verwijder de pod en controleer dat `GET /trail` dezelfde beslissingen
teruggeeft. Dat is de PVC-test, en het is de enige die telt voor de
append-only-belofte.

## Credential-herleidbaarheid

Elke credential die het portaal gebruikt, met eigenaar als **rol** en niet als
persoon. Dit is de tabel waar een ISO-audit om vraagt.

| Credential | Systeem | Secret (namespace `iso-platform`) | Org-account | Eigenaar-rol | Max. leeftijd |
|---|---|---|---|---|---|
| Keycloak-clientsecret | Keycloak `commonground` | `iso-audit-portal-oauth` / `client-secret` | client `iso-audit-portal` | `info@conduction.nl` | 12 maanden |
| Cookie-secret | oauth2-proxy | `iso-audit-portal-oauth` / `cookie-secret` | n.v.t. (random) | `info@conduction.nl` | 12 maanden |
| Anthropic-key | Anthropic API | `iso-audit-portal-llm` / `api-key` | org-workspace-key | `info@conduction.nl` | 12 maanden |
| Google-service-account | Drive, Docs, Sheets | `iso-audit-portal-google` / `service-account.json` | Workspace-SA | `info@conduction.nl` | **12 maanden** — verloopt niet zelf, dus rotatie is een agenda-item |
| Jira-token | Jira Cloud | `iso-audit-portal-sources` / `jira-api-token` | functioneel Atlassian-account | `info@conduction.nl` | 12 maanden |
| Miro-token | Miro REST v2 | `iso-audit-portal-sources` / `miro-api-token` | org-owned token/app | `info@conduction.nl` | 12 maanden |
| ghcr-push | GitHub Packages | n.v.t. — `GITHUB_TOKEN` in Actions | `ConductionNL/iso-audit` | `info@conduction.nl` | per run, kortlevend |
| tag-bump-commit | GitHub contents | n.v.t. — `GITHUB_TOKEN` in Actions | `github-actions[bot]` | `info@conduction.nl` | per run, kortlevend |

**Geen enkele credential mag op naam van een natuurlijk persoon staan.** Een
migratie is pas af als het persoonlijke credential is *ingetrokken*, met een
`CHANGELOG.md`-regel die zegt welke en wanneer.

De 12-maandstermijn is een keuze, niet een technische grens: de meeste van deze
credentials verlopen niet uit zichzelf. Zonder vastgelegd plafond is "rotatiemoment"
een intentie zonder datum.

## Bekende openstaande punten

- **`main` van de repo is onbeschermd** (`"Branch not protected"`, gemeten
  2026-08-12). Gecombineerd met merge-is-deploy kan een gecompromitteerde
  workflow-stap de gedeployde tag verleggen. Zie taak 0.6 / 3.5.
- **Geen rate limit op de LLM-key** — besluit "loggen, niet begrenzen"
  (2026-08-12). Runs staan met identiteit in het audit-log; een limiet is een
  eigen change als het gaat knijpen.
- **Restrisico van 8 uur bij offboarding**: de sessiecookie draagt de identiteit
  zelf, dus alleen een account uitzetten is niet genoeg. Beëindig ook de actieve
  realm-sessies — zie
  [verify-portal-auth](../docs/how-to/verify-portal-auth.md).
- **Google identity provider staat niet in Git** maar is handmatig in de
  Keycloak-UI aangemaakt (bestaande, gedocumenteerde afwijking in de KeyCloak-repo).
