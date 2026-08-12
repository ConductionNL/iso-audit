# Tasks — iso-portal

> Stack: Python 3.12, `uv` (`uv sync --frozen`, nooit pip), FastAPI + uvicorn,
> kustomize, oauth2-proxy v7.7.1, Argo CD. Max 200 regels per file.
> Patroon-bron: `openwoo-app-config/webgui/deploy/` + `webgui/auth/README.md`.
> Geen nieuwe Python-dependencies. `/review` na elke task;
> `/security-review` na taak 1, 2 en 4.
>
> **Volgorde is bindend:** taak 0 blokkeert taak 3 (ghcr-namespace), taak 1-4
> blokkeren taak 6 (rollout), en taak 6 blokkeert de bron-changes in taak 7.

## 0. Voorwaarde — repo-eigenaarschap

- [x] 0.1 Org-eigendom geregeld **2026-08-12 via route B**: stale org-repo hernoemd
      naar `ConductionNL/iso-audit-scaffold-2026-05` (niets verwijderd), daarna
      transfer van `MWest2020/iso-audit`. Historie, 15 branches, **public**-
      zichtbaarheid en een permanente redirect verhuisden mee; `origin` staat om.
      Daarmee vervalt 0.4 (geen twee remotes met dezelfde historie)

- [x] 0.2 `pyproject.toml`: `authors` + `maintainers` → Conduction
      (`info@conduction.nl`), `Repository`-URL → ConductionNL. `CODEOWNERS`
      toegevoegd, met de deploy-/auth-paden expliciet benoemd
- [ ] 0.3 Vaststellen: ghcr-package `ghcr.io/conductionnl/iso-audit` moet **public**
      staan, anders heeft de namespace een pull-secret nodig (les uit openwoo's
      `deploy/README.md`). Vergt `admin:packages` — niet te doen met de huidige
      `write:packages`-scope

- [x] 0.5 Zichtbaarheid: **public**, en dat is de gewenste stand — het
      EUPL-1.2-besluit van juni blijft daarmee geldig. De transfer nam de
      zichtbaarheid mee, dus er was niets te wijzigen. Bijkomend voordeel:
      `secret_scanning` en `secret_scanning_push_protection` staan hierdoor aan
- [ ] 0.6 Branch-bescherming op `main` van de org-repo. **Gemeten met
      admin-rechten 2026-08-12: `"Branch not protected"`** — de eerdere 404 was
      geen rechtenkwestie. Onbeschermd + merge-is-deploy betekent dat een
      workflow-commit de gedeployde tag ongereviewd kan verleggen; dat is
      sec-bevinding 3 in levende lijve. Hoort bij taak 3.5

## 1. Auth-gate (capability: portal-auth)

- [x] 1.1 `src/iso_audit/api/auth_gate.py` (~60 regels): leest `X-Forwarded-Email`
      / `X-Forwarded-User`, `REQUIRE_AUTH` default `true`, 403 zonder header.
      Poort van `current_user()` uit openwoo's `webgui/server.py`
- [x] 1.2 `api/app.py`: gate op alle routes; ongeauthenticeerde `GET /healthz`
      voor de probes. `serve()` blijft op `127.0.0.1` binden.
      **Afwijking van de oorspronkelijke formulering:** geïmplementeerd als HTTP-
      middleware, niet als `Depends()` per route. Een dependency moet bij élk nieuw
      endpoint opnieuw worden aangezet en vergeten betekent stil een open route;
      middleware dekt ook wat er later bij komt. `OPEN_PADEN` is de expliciete
      uitzonderingenlijst en bevat alleen `/healthz`
- [x] 1.3 Tests: 403 zonder header, 200 met header, `/healthz` altijd open,
      `REQUIRE_AUTH=false` laat door
- [x] 1.4 Trust-model als proza. **Let op:** main heeft sinds `66f4309` een
      docs-contract (Diátaxis; geen markdown buiten `how-to/`, `reference/`,
      `explanation/` — de flat pagina's zijn deprecated stubs). Dus niet
      `docs/auth.md` maar `docs/explanation/portal-auth.md` (waarom de header te
      vertrouwen is) + `docs/how-to/verify-portal-auth.md` (de smoke-test zonder
      cluster), beide vermeld in `docs/index.md`
- [x] 1.5 **Identiteit in de trail** (sec-bevinding 1): `POST /findings/{id}` geeft
      de geverifieerde identiteit door als `actor` aan `apply_triage()` — het veld
      bestaat al (`api/session.py:134`, geschreven op regel 166) maar de API laat
      hem op de default `"auditor"` staan. Test: trail-regel bevat het adres van de
      auditor, niet de placeholder
- [x] 1.6 **Sessie-intrekking** (sec-bevinding 2): `cookie_expire` vaststellen en
      in `docs/how-to/verify-portal-auth.md` de offboarding-handeling beschrijven waarmee toegang
      *direct* eindigt (Keycloak-sessie + account), plus de maximale restduur bij
      alleen accountuitzetting als geaccepteerd risico
- [x] 1.7 **Logging** (sec-bevinding 4): auth-events en muterende requests loggen
      met identiteit; test dat geen credential-waarde, token of cookie-inhoud in
      de logregels voorkomt
- [x] 1.8 **Run-limiet** (sec-bevinding 6) — **besluit 2026-08-12: loggen, niet
      begrenzen.** Geen rate limit, in afwijking van openwoo's
      `ASSISTANT_RATE_LIMIT`. In plaats daarvan kosten-attributie: `POST /run/start`
      logt de identiteit + run-config, zodat een kostenpiek adresseerbaar is
      (`Kostenteller` hield het verbruik al bij, maar niet wie de run startte).
      Restrisico expliciet aanvaard in de spec: de gebruikersgroep is klein en
      geverifieerd via `email_domains`

## 2. Persistentie (capability: portal-deployment)

- [x] 2.1 Schrijfpaden geïnventariseerd; tabel in `design.md` onder
      "Schrijfpaden en hun fallbacks"
- [x] 2.2 Geen stille fallback. **Sessie-dir was al conform:**
      `AuditSession.__init__` gooit `SessionError` als `findings.json` ontbreekt —
      niet opnieuw gebouwd, wel vastgelegd in een test zodat het niet in een
      fallback verandert. **DB-pad afwijkend opgelost:** `store.db_pad()` een harde
      fout laten gooien zou de lokale CLI breken, wat buiten deze change valt.
      Gekozen voor de repo-conventie uit `CLAUDE.md` ("env-var-fallbacks bestaan,
      maar loggen expliciet dat er fallback wordt gebruikt"): één waarschuwing per
      proces die het repo-interne pad noemt. Het portaal zet `AUDIT_DB_PATH` in
      `deployment.yaml`, dus daar treedt de fallback nooit op
- [x] 2.3 Tests in `tests/api/test_persistentie.py`: trail identiek na herstart,
      append-only over herstarts heen (oudere regels ongemuteerd), harde fout zonder
      `findings.json`, en de fallback-waarschuwing op `db_pad()`
- [x] 2.4 PVC-manifest: storageclass + grootte vaststellen op wat de shoot biedt.
      **Geen emptyDir** voor deze paden

## 3. Container-image (capability: portal-deployment)

- [x] 3.1 `Dockerfile`: `uv sync --frozen`, non-root, compatibel met
      `readOnlyRootFilesystem`, uvicorn op `127.0.0.1:8081`
- [x] 3.2 WeasyPrint-systeemlibs in het image; **end-to-end geverifieerd in de
      container 2026-08-12** onder `--read-only --user 10001:10001` (PDF-render,
      fail-closed, actor in de trail, herstart-persistentie). Details in de
      CHANGELOG. Base-images op **digest** gepind: `ghcr.io/astral-sh/uv` heeft geen
      versie-specifieke tag, alleen een floating tag
- [x] 3.3 `.github/workflows/image.yml`: merge-is-deploy — `sha-<short>` bouwen,
      pullbaarheid verifiëren, `newTag` terugcommitten met `[skip ci]`.
      **Bouwen vóór bumpen**: een tag zetten die nog niet bestaat richt Argo op
      een niet-pullbaar image
- [x] 3.4 Deploy-keten in het credential-model: `ghcr-push` en
      `tag-bump-commit` staan in de herleidbaarheidstabel van `deploy/README.md`,
      beide als kortlevend `GITHUB_TOKEN` per run
- [ ] 3.5 Zie taak 0.6 — dezelfde branch-bescherming. Documenteer daarbij het
      gedrag bij een geweigerde bot-push: het image bestaat dan wél en alleen de
      rollout staat stil, wat de veilige kant van die fout is


## 4. Manifests (capability: portal-deployment, portal-auth)

- [x] 4.1 Secret-mechanisme gekozen: **out-of-band kubectl-Secrets, geen ESO en
      geen SOPS.** ESO draait wel in dit cluster, maar de bestaande
      `nextcloud-shared-store` bestaat om één seed-Secret naar véél
      tenant-namespaces te distribueren. `iso-platform` is één namespace — er is
      niets uit te delen, dus ESO zou een hop en een te auditen component toevoegen
      zonder dat er iets geheimer wordt. Reden vastgelegd in
      `deploy/secret.example.yaml`. Herzien wanneer er een echte vault komt
- [x] 4.2 `deploy/`: `namespace.yaml` (`iso-platform`), `serviceaccount.yaml`
      (token-automount **uit**), `service.yaml`, `deployment.yaml` (app +
      oauth2-proxy sidecar, hardened securityContext, PVC-mount)
- [x] 4.3 `deploy/oauth2-proxy.cfg`: kopie van openwoo's cfg met `client_id:
      iso-audit-portal`, `redirect_url: https://iso.commonground.nu/oauth2/callback`,
      upstream `127.0.0.1:8081`. Cookie-hardening en `whitelist_domains` behouden
- [x] 4.4 `deploy/ingress.yaml`: host + `letsencrypt-prod` + HSTS;
      streaming-annotaties behouden (`/run/progress` en de render duren lang)
- [x] 4.5 `deploy/networkpolicy.yaml`: ingress alléén uit `ingress-nginx`.
      **`networkpolicy-egress.yaml` niet overnemen** — staat in openwoo bewust uit
      sinds 2026-07-13 (DNS-breuk onder Gardener/Calico)
- [x] 4.6 `deploy/kustomization.yaml`: `configMapGenerator` voor de proxy-cfg,
      `images: ghcr.io/conductionnl/iso-audit`
- [x] 4.7 `deploy/secret.example.yaml`: template met placeholders, plus de
      aanmaak-commando's in commentaar
- [x] 4.8 `deploy/README.md`: `owner: info@conduction.nl`-frontmatter,
      architectuurschets, prerequisites, apply, verificatie, én de
      herleidbaarheidstabel credential → systeem → Secret → org-account →
      eigenaar-rol → rotatiemoment. Inclusief de deploy-keten (taak 3.4) en een
      **maximale leeftijd per machine-credential**, ook voor de niet-verlopende
      SA-keyfile (sec-bevinding 5)
- [x] 4.9 Niet klonen: `rbac-argo.yaml`, `rbac-secrets.yaml` (openwoo-specifiek)

## 5. Argo CD (capability: portal-deployment)

- [x] 5.1 `argo/projects/iso-platform.yaml`: AppProject met `sourceRepos`
      beperkt tot `https://github.com/ConductionNL/iso-audit.git` en
      `destinations` beperkt tot namespace `iso-platform`
- [x] 5.2 `argo/applications/iso-audit-portal.yaml`: `path: deploy`, `automated`
      + `CreateNamespace=true`
- [x] 5.3 Bootstrap-sectie in `deploy/README.md` (eenmalig `kubectl apply`, het
      patroon dat `cluster-infra` al gebruikt). Vastleggen dat DNS géén
      handmatige stap is: external-dns leest de Ingress

## 6. Buiten deze repo (aparte PR's, mens-actie)

- [ ] 6.1 Keycloak-client `iso-audit-portal` in
      `KeyCloak/clusters/prod/keycloak/20-keycloak/realm-commonground.yaml`
      (kopie van het `openwoo-provisioner`-blok, regels 244-270). **Prod-pad —
      expliciete confirmatie; eerst de main-staat van die repo verifiëren**
- [ ] 6.2 Client secret + cookie secret als out-of-band Secret aanmaken
- [x] 6.3 Erfelijke afwijking gedocumenteerd in `deploy/README.md` onder "Bekende
      openstaande punten": de Google identity provider is handmatig in de
      Keycloak-UI aangemaakt en staat niet in de realm-import
- [ ] 6.4 Rollout + verificatie: `rollout status`, `/healthz` zonder login,
      `/` geeft de Keycloak-login, trail-persistentie na pod-delete

## 7. Vooruitwijzing — de bron-changes (niet in deze change)

Elk een eigen OpenSpec change, één per keer, op afnemend
persoonlijk-credential-risico. Elke change eindigt met het **intrekken** van het
persoonlijke credential plus een `CHANGELOG.md`-entry.

- [ ] 7.1 `gsuite-service-account-sources` — `drive` + `planning` van
      `clients/gws.py` naar het bestaande `auth.py`-service-account. Eerst, omdat
      de `gws`-sessie toegang geeft tot alles wat de medewerker ziet, niet alleen
      tot de auditmap
- [ ] 7.2 `jira-functional-account` — functioneel Atlassian-account; adaptercode
      ongewijzigd
- [ ] 7.3 `miro-org-token` — org-owned token; READ-only blijft
- [ ] 7.4 `notifier-org-credentials` — Slack + SMTP + Anthropic-workspace-key.
      Vervangt ook de `gmail.send`-scope uit `auth.py`
- [ ] 7.5 Na 7.1: opruimen van `clients/gws.py` als er geen caller meer over is
- [ ] 7.6 **Resterende trust-paths vaststellen** (sec-bevinding 7), per
      bron-change: welke lokale artefacten op het werkstation van de vertrekkende
      beheerder resteren (`.env`, `output/*.db` met echte auditdata,
      credential-caches zoals `~/.config/gws`) en wat daarmee gebeurd is. Plus:
      resterende repository-toegang herzien ná de transfer van taak 0.1 — een
      transfer verwijdert een collaborator niet
