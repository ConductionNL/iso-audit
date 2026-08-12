# Spec — portal-deployment (nieuw)

## ADDED Requirements

### Requirement: De tool draait als container-image, niet vanaf een werkstation

De repo MUST een `Dockerfile` bevatten dat de auditor-API als container start. De
build MUST `uv sync --frozen` gebruiken tegen de gecommitte `uv.lock`; `pip`
MUST NOT gebruikt worden. Het image MUST als non-root draaien en werken met
`readOnlyRootFilesystem: true`. Systeembibliotheken die de PDF-render nodig heeft
MUST in het image zitten, zodat een render niet pas in productie faalt.

#### Scenario: Image start de API zonder werkstation-afhankelijkheden

- **WHEN** het image wordt gestart zonder enige credential-env-var
- **THEN** luistert de API op `127.0.0.1:8081`
- **AND** antwoordt `/healthz` met een ok-status
- **AND** wordt geen credential uit een gebruikers-home (zoals `~/.config/gws`) gelezen

#### Scenario: PDF-render werkt in het image

- **WHEN** de memo-export in het image wordt aangeroepen op een geldige sessie
- **THEN** levert de render een PDF op
- **AND** faalt de aanroep niet op een ontbrekende systeembibliotheek

### Requirement: Manifests zijn Argo-gesynced en per omgeving parameteriseerbaar

De repo MUST een `deploy/`-directory bevatten met kustomize-manifests voor
namespace, serviceaccount, deployment, service, ingress en NetworkPolicy. De
image-tag MUST via `kustomization.yaml` overschrijfbaar zijn. Secrets MUST NOT in
de manifests staan; `deploy/secret.example.yaml` MUST een template zijn met lege
of placeholder-waarden.

De ServiceAccount MUST token-automount uitgeschakeld hebben: het portaal heeft
geen kube-API-toegang nodig.

#### Scenario: Secret-template bevat geen echte waarde

- **WHEN** `deploy/` op secrets gescand wordt
- **THEN** bevat `secret.example.yaml` alleen placeholders
- **AND** bevat geen ander manifest een credential-waarde

#### Scenario: Tag-bump zonder manifest-edit

- **WHEN** een nieuw image gepubliceerd is
- **THEN** volstaat het zetten van `newTag` in `kustomization.yaml` om de rollout te richten
- **AND** hoeft `deployment.yaml` niet gewijzigd te worden

### Requirement: De audit-trail overleeft een pod-restart

De auditbeslissingen MUST op persistente opslag staan: de sessie-directory
(`findings.json` + append-only `triage_log.jsonl`) en de SQLite-DB
(`AUDIT_DB_PATH`, met de append-only `decisions`- en
`classifications`-tabellen). `emptyDir` MUST NOT gebruikt worden voor deze paden.

Rationale: dit zijn auditbeslissingen, geen cache. De append-only-garantie uit
`CLAUDE.md` is waardeloos als de opslag vluchtig is.

#### Scenario: Triage-beslissingen overleven een herstart

- **GIVEN** een auditor heeft triage-beslissingen vastgelegd
- **WHEN** de pod verwijderd wordt en opnieuw start
- **THEN** levert `GET /trail` dezelfde beslissingen op als voor de herstart

### Requirement: Één auditsessie per deployment in v1

Het portaal MUST expliciet één auditsessie serveren, overeenkomstig
`create_app(session)` dat één `AuditSession` aanneemt. Een tweede gelijktijdige
sessie MUST NOT stilzwijgend gedeelde state krijgen.

De **applicatie** MUST NOT zelf een sessie verzinnen. Het **deployment** MAY een
lege maar geldige sessie provisioneren via een initContainer; dat is een expliciete,
zichtbare deploy-stap en geen stille fallback in de app. Zonder die stap start het
portaal niet op een verse PVC — dat was de eerste rollout.

#### Scenario: Sessie-pad is expliciete configuratie

- **WHEN** het portaal start zonder geconfigureerde sessie-directory
- **THEN** faalt de start met een leesbare fout
- **AND** wordt geen lege sessie aangemaakt en geen fallback-pad gekozen

### Requirement: Deployment-documentatie is onderdeel van de change

`deploy/README.md` MUST beschrijven: de architectuurschets, de prerequisites (de
Keycloak-client, de out-of-band Secrets, het image), de apply-stap en de
verificatiestappen. De README MUST een `owner:`-frontmatter dragen met de
verantwoordelijke rol.

#### Scenario: Een nieuwe beheerder kan het portaal uitrollen zonder de auteur

- **WHEN** iemand die niet aan de change meewerkte `deploy/README.md` volgt
- **THEN** staan alle benodigde stappen en Secret-namen er expliciet in
- **AND** is uit de README duidelijk welke rol eigenaar is

### Requirement: De deploy-keten staat in de herleidbaarheidstabel en is niet ongereviewd te verleggen

De credentials van de build- en deploy-keten MUST in dezelfde
herleidbaarheidstabel staan als de bron-credentials: het registry-push-credential
en het credential waarmee de workflow de image-tag terugcommit. Het verleggen van
de gedeployde image-tag MUST NOT zonder review op de default-branch kunnen landen.

Rationale: de keten is merge-is-deploy — een workflow die `newTag` naar main
commit bepaalt wat er draait. Een compromis daar persisteert over deploys heen en
staat buiten het credential-model als de keten er niet in staat. Dat is in deze
organisatie een reëel scenario, niet een theoretisch.

#### Scenario: Deploy-credentials zijn geïnventariseerd

- **WHEN** de herleidbaarheidstabel gelezen wordt
- **THEN** staan het registry-push-credential en het tag-bump-credential erin
- **AND** staat per credential de eigenaar-rol en het rotatiemoment

#### Scenario: Tag-bump is niet ongereviewd

- **WHEN** een image-tag naar de default-branch gecommit wordt
- **THEN** is die commit onderworpen aan de branch-bescherming van de repo
- **AND** kan een enkele gecompromitteerde workflow-stap de rollout niet stil verleggen
