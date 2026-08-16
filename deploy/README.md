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

   c. **De audience-mapper is niet optioneel.** Keycloak zet de client niet als
      `aud` in het token — er staat alleen `azp` — en oauth2-proxy eist die claim.
      Zonder de mapper zie je het inlogportaal, log je in, en volgt een **500**,
      met in de proxy-log `audience claims [aud] do not exist in claims`. Gemeten
      2026-08-12 bij de eerste echte login.

      Doen: Clients → `iso-audit-portal` → Client scopes →
      `iso-audit-portal-dedicated` → Configure a new mapper → **Audience** →
      Included Client Audience `iso-audit-portal`, *Add to access token* aan. Geen
      herstart nodig; opnieuw inloggen volstaat.

      Bij een import met het bestand hierboven komt de mapper mee — hij staat er
      sinds 2026-08-12 in. `openwoo-provisioner` heeft hem nodig en werkt, dus daar
      is hij eerder met de hand toegevoegd; ook dat staat niet in Git.

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
4. **Geen sessie-inhoud nodig.** Sinds change `portal-dashboard` start het portaal op
   een **lege** audits-root: een initContainer (`seed-audits`) maakt
   `/var/lib/iso-audit/audits` aan en zet het profiel klaar, en de auditor maakt zelf
   een audit aan in de UI. Idempotent — bestaande auditdata wordt nooit overschreven.

   Dit was eerder handwerk en dat brak de eerste rollout: `iso-audit ui` weigerde te
   starten zonder `findings.json`, en die stond er niet. Die spanning is nu weg zonder
   de discipline op te geven — een audit bestaat pas als iemand hem aanmaakt.

**DNS vraagt geen stap.** external-dns kijkt cluster-breed naar Ingresses met
domain-filter `commonground.nu` en maakt het record uit `ingress.yaml`.

## Bootstrap (eenmalig, met de hand)

Argo CD wordt via Helm beheerd, dus een nieuw project registreer je één keer zelf —
het patroon dat `cluster-infra` ook gebruikt:

    kubectl apply -f argo/projects/iso-platform.yaml
    kubectl apply -f argo/applications/iso-audit-portal.yaml

Daarna synct Argo `deploy/` zelf. Handmatig kan ook: `kubectl apply -k deploy`
(nadat de Secrets bestaan).

## Uitrollen

Eén script doet de hele keten — pushen, wachten tot het image gebouwd is, mergen,
wachten tot Argo gesynct is, het cookie-secret roteren, herstarten en verifiëren:

    ./scripts/rollout-portal.sh              # volledig
    ./scripts/rollout-portal.sh --dry-run    # alleen tonen wat het zou doen

Het rotteert alléén de key `cookie-secret` met een patch, dus het
Keycloak-clientsecret dat al in het cluster staat blijft ongemoeid.

## Verifiëren

    kubectl -n iso-platform rollout status deploy/iso-audit-portal
    curl -sS https://iso.commonground.nu/ping        # "OK" — van oauth2-proxy zelf
    # / geeft de sign-in-pagina: de auth-gate doet zijn werk

Na inloggen: het landingsscherm is het **audit-overzicht**. Een nieuwe audit maak je
daar aan met norm + periode (`9001` + `2026-Q3` → id `9001-2026-Q3`); de routes zijn
sindsdien audit-gescoped (`/audits/{id}/…`). Configuratie is een eigen scherm: het
toont per bron of die gekoppeld is en wat er ontbreekt. Koppelen vanuit de UI is in
aanbouw (taak 3.6-3.9); tot dan komen bron-credentials uit de Secrets in
`secret.example.yaml`.

Dat koppelen hóórt in de UI te kunnen: een auditor heeft geen boodschap aan een
cluster, en het tool moet aan derden te leveren zijn. De controle is dat elke
wijziging en elke geraadpleegde bron wordt vastgelegd — niet dat configureren moeilijk
is.

**`/healthz` is extern níet bereikbaar, en dat is opzet.** Er staat geen
`skip_auth_routes` in `oauth2-proxy.cfg`, dus de proxy onderschept élk pad — ook
`/healthz` — en stuurt je naar Keycloak. Het app-endpoint bestaat voor de
kubelet-probe binnen de pod. Extern check je `/ping`, het eigen health-endpoint van
oauth2-proxy, dat buiten de auth-gate valt. Binnen de pod:

    kubectl -n iso-platform exec deploy/iso-audit-portal -c app -- \
      python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8081/healthz').status)"

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

## Secrets aanmaken

Eén script, idempotent (`create --dry-run=client | apply`), zodat bijwerken hetzelfde
commando is als aanmaken:

    KEYCLOAK_CLIENT_SECRET='...' ANTHROPIC_KEY='sk-ant-...' \
      JIRA_BASE_URL='https://ORGANISATIE.atlassian.net' \
      JIRA_API_TOKEN='ATSTT...' \
      GOOGLE_SA_FILE=/pad/naar/service-account.json \
      ./scripts/create-portal-secrets.sh

Wat er per credential nodig is, verschilt — en dat verschil is de moeite waard om te
kennen vóór je gaat rondzoeken:

| Credential | Ook via de UI te zetten? |
|---|---|
| Jira-token, Miro-token, Anthropic-key | **Ja.** Een auditor vult ze in het configuratiescherm in; die waarde landt in Secret `iso-audit-portal-config` en gaat vóór op wat hier in de omgeving staat (herkomst `ui-override`). Zo is een geroteerde key te vervangen zonder clusterbeheerder. |
| Google-service-account-keyfile | **Nee.** Dit is een gemount *bestand* (`/etc/iso-audit/google/service-account.json`), geen env-var, en dus niet vanuit de UI te zetten. Moet als Secret bestaan. |
| Keycloak-clientsecret, cookie-secret | Nee — die horen bij de proxy, niet bij de auditor. |

Het script weigert een keyfile die geen `service_account` is: een `authorized_user`-JSON
komt uit een persoonlijke OAuth-login en is precies wat deze opzet wegneemt.

Ontbreekt het Google-Secret, dan is de mount leeg (`optional: true`) en melden Drive en
de auditplanning zich in het portaal als **niet gekoppeld**. Het script waarschuwt daarop
in plaats van stil over te slaan.

Verifiëren zonder waarden te tonen:

    kubectl -n iso-platform get secret iso-audit-portal-sources \
      -o jsonpath='{.data}' | tr ',' '\n' | cut -d'"' -f2

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
| UI-configuratie | het portaal zelf | `iso-audit-portal-config` / `bron_config.json` | n.v.t. — door auditors gevuld | `info@conduction.nl` | volgt de credential erin |
| kube-API-token | Kubernetes | n.v.t. — projected volume, geen Secret | SA `iso-audit-portal` | `info@conduction.nl` | 1 uur, automatisch geroteerd |
| ghcr-push | GitHub Packages | n.v.t. — `GITHUB_TOKEN` in Actions | `ConductionNL/iso-audit` | `info@conduction.nl` | per run, kortlevend |
| tag-bump-commit | GitHub contents | n.v.t. — `GITHUB_TOKEN` in Actions | `github-actions[bot]` | `info@conduction.nl` | per run, kortlevend |

**Geen enkele credential mag op naam van een natuurlijk persoon staan.** Een
migratie is pas af als het persoonlijke credential is *ingetrokken*, met een
`CHANGELOG.md`-regel die zegt welke en wanneer.

De 12-maandstermijn is een keuze, niet een technische grens: de meeste van deze
credentials verlopen niet uit zichzelf. Zonder vastgelegd plafond is "rotatiemoment"
een intentie zonder datum.

**Roteren kan ook zonder clusterbeheerder.** Een auditor kan een credential die uit een
Secret komt vanuit het portaal vervangen, als expliciete handeling. De herkomst wordt dan
`ui-override` en er staat een regel in het wijzigingsspoor met wie en wanneer — nooit de
waarde. Dat is bewust toegestaan: een key die verloopt terwijl niemand met clustertoegang
beschikbaar is, legt anders de hele auditcapability stil.

Twee dingen om te weten bij het roteren van een Secret:

- vervang je hier een Secret terwijl er een overschrijving op staat, dan blijft die
  overschrijving in gebruik. Het portaal meldt bij dat veld dat de omgeving inmiddels een
  andere waarde heeft, zodat je niet in het cluster gaat zoeken naar een fout die er niet
  is;
- de overschrijving verdwijnt door het veld in het portaal leeg te maken; daarna geldt de
  Secret-waarde weer.

Zie [`credential-rotatie-door-auditor`](../openspec/changes/credential-rotatie-door-auditor/proposal.md).

## Kube-API-toegang: waarom de app een token heeft

Tot 2026-08-14 had dit portaal **geen** kube-API-toegang, en dat stond zo in
`serviceaccount.yaml`. Sinds de UI-configuratie in een Secret staat, heeft de app die
toegang wél nodig. Een reviewer die de oude regel kent, moet kunnen vinden waarom hij is
veranderd — daarom staat het hier en niet alleen in een commit-bericht.

De toegang is zo smal mogelijk gemaakt:

| Keuze | Waarom |
|---|---|
| `automountServiceAccountToken: false` blijft staan | Automount zet de token in **élke** container van de pod, ook in de oauth2-proxy-sidecar. Die heeft bij de kube-API niets te zoeken. |
| Projected token, alleen in de `app`-container | Kortlevend (1 uur), automatisch geroteerd, met expliciete audience. Het legacy Secret-token verliep nooit. |
| Role, geen ClusterRole | De rechten gelden alleen in `iso-platform`. |
| `resourceNames: ["iso-audit-portal-config"]` | Zonder die beperking mag de pod élk Secret in de namespace lezen — inclusief het oauth2-secret en de bron-credentials. |
| `get` + `patch`, geen `list` | `list` zou alle Secrets opsommen en `resourceNames` in de praktijk zinloos maken. Geen `create`/`delete`: het Secret komt van een beheerder. |

Te verifiëren:

```
kubectl auth can-i --as=system:serviceaccount:iso-platform:iso-audit-portal \
  get secret/iso-audit-portal-config -n iso-platform     # yes
kubectl auth can-i --as=system:serviceaccount:iso-platform:iso-audit-portal \
  get secret/iso-audit-portal-oauth -n iso-platform      # no
kubectl auth can-i --as=system:serviceaccount:iso-platform:iso-audit-portal \
  list secrets -n iso-platform                           # no
```

**De PVC-terugval blijft.** Is de kube-API onbereikbaar of is
`ISO_AUDIT_CONFIG_SECRET` niet gezet, dan schrijft het portaal naar
`bron_config.json` op de PVC met een waarschuwing in de log. Zonder die terugval is het
tool niet meer buiten dit cluster te draaien — en dat was juist de reden om configuratie
uit het cluster te halen.

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
