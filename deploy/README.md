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

1. **Keycloak-client** `iso-audit-portal` in realm `commonground`. Twee stappen, en
   de tweede is niet optioneel:

   a. Het clientblok staat in de KeyCloak-repo,
      `clusters/prod/keycloak/20-keycloak/realm-commonground.yaml` (kopie van
      `openwoo-provisioner`, met `https://iso.commonground.nu/oauth2/callback` en
      het `post.logout.redirect.uris`-attribuut).

   b. **De client moet daarna met de hand worden aangemaakt in Keycloak.**
      `KeycloakRealmImport` is create-once: de operator importeert een realm die
      nog niet bestaat, maar werkt een bestaande realm níet bij. Argo synct de CR
      wel — de live resource bevat de nieuwe client — maar er wordt geen
      import-job meer gestart. Gemeten 2026-08-12: na de merge van het clientblok
      bleef de laatste import-job die van 3 augustus.

      Doen: Keycloak-UI → realm `commonground` → Clients → **Import client** met
      `keycloak-client.example.yaml` als bron (of de JSON-variant daarvan).

   **Wat dit betekent voor het auditspoor:** de realm-YAML is in deze opstelling
   *gewenste* staat, niet *toegepaste* staat. Er kan dus drift bestaan tussen Git
   en Keycloak die niemand ziet. Datzelfde geldt al voor de Google identity
   provider, die expliciet handmatig is aangemaakt. Een reconciliërende oplossing
   (`keycloak-config-cli` als sync-stap) is eigen werk; tot die tijd is deze
   handmatige stap de afspraak en hoort ze hier te staan in plaats van in iemands
   hoofd.
2. **Secrets** out-of-band aangemaakt — zie `secret.example.yaml` voor de
   commando's. Alleen `iso-audit-portal-oauth` is verplicht.
3. **Image** gebouwd en gepusht, en de ghcr-package op **public** (anders heeft de
   namespace een pull-secret nodig).

   Release-flow: één nummer op twee plekken. Bump `version` in `pyproject.toml` en
   zet dezelfde waarde als `newTag` in `kustomization.yaml`, in dezelfde PR.
   `.github/workflows/image.yml` bouwt het image op die PR — dus de tag bestaat
   vóór de merge — en faalt als versie en tag uiteenlopen.

   Dit was eerder merge-is-deploy, waarbij de workflow de tag zelf terugcommitte
   naar main. Dat is per 2026-08-12 weg: die workflow had `contents: write` nodig,
   waardoor branch-bescherming een uitzondering voor de bot vroeg en een
   gecompromitteerde stap de gedeployde tag kon verleggen. De workflow heeft nu
   geen schrijfrechten op de repo.
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

### Wat een lokale containertest níet dekt

Bij de eerste rollout (2026-08-12) viel de pod om op twee dingen die lokaal
allebei groen waren. Dat is geen toeval maar een systematisch gat, dus het staat
hier:

- **Numerieke uid.** Een lokale test met `docker run --user 10001:10001` geeft de
  uid van búiten mee, waardoor een `USER <naam>` in het image onzichtbaar blijft.
  De kubelet kijkt naar de USER ín het image en weigert met *"cannot verify user is
  non-root"*. Controleer dus het image zelf:

      docker inspect <image> --format '{{.Config.User}}'   # moet numeriek zijn

- **Secret-inhoud.** Een lokale run zonder oauth2-proxy zegt niets over of het
  cookie-secret door de proxy geaccepteerd wordt. Dat blijkt pas uit de
  proxy-logs. Bij een crashloop op de proxy: `kubectl logs … -c oauth2-proxy`
  eerst, want de foutmelding is expliciet.

Algemener: `kubectl describe pod` en de `Failed`-events zeggen hier meer dan de
containerlogs, omdat een container die de kubelet weigert aan te maken geen logs
heeft.

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
  2026-08-12). Kan nu wél zonder uitzondering aan: sinds het bot-commit uit
  `image.yml` verdwenen is, hoeft geen enkele automatisering naar main te schrijven.
  Zie taak 0.6.
- **De realm-YAML in de KeyCloak-repo reconcilieert niet.** `KeycloakRealmImport`
  is create-once, dus Git en Keycloak kunnen stil uiteenlopen. Zie prerequisite 1;
  een oplossing (`keycloak-config-cli`) is eigen werk.
- **Geen rate limit op de LLM-key** — besluit "loggen, niet begrenzen"
  (2026-08-12). Runs staan met identiteit in het audit-log; een limiet is een
  eigen change als het gaat knijpen.
- **Restrisico van 8 uur bij offboarding**: de sessiecookie draagt de identiteit
  zelf, dus alleen een account uitzetten is niet genoeg. Beëindig ook de actieve
  realm-sessies — zie
  [verify-portal-auth](../docs/how-to/verify-portal-auth.md).
- **Google identity provider staat niet in Git** maar is handmatig in de
  Keycloak-UI aangemaakt (bestaande, gedocumenteerde afwijking in de KeyCloak-repo).
