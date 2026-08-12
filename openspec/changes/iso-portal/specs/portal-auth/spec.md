# Spec — portal-auth (nieuw)

## ADDED Requirements

### Requirement: Authenticatie via het bestaande Keycloak-patroon

Toegang tot het portaal MUST verlopen via oauth2-proxy met Keycloak (realm
`commonground`, issuer `https://iam.commonground.nu/realms/commonground`) als
OIDC-provider. Google MUST binnen Keycloak gebrokerd worden, niet als tweede
integratie in de app.

De app MUST NOT een eigen login, sessiebeheer, wachtwoordopslag of
token-uitwisseling implementeren.

#### Scenario: Ongeauthenticeerde bezoeker krijgt de Keycloak-login

- **WHEN** een bezoeker zonder sessie het portaal opvraagt
- **THEN** wordt de bezoeker via oauth2-proxy naar Keycloak geleid
- **AND** krijgt de app het request niet te zien

#### Scenario: Alleen toegestane domeinen komen binnen

- **WHEN** iemand met een e-mailadres buiten de geconfigureerde `email_domains` inlogt
- **THEN** weigert oauth2-proxy de sessie
- **AND** bereikt het request de app niet

### Requirement: De app faalt gesloten zonder geverifieerde identiteit

De app MUST de identity-header lezen die oauth2-proxy zet (`X-Forwarded-Email`,
met `X-Forwarded-User` als aanvulling). `REQUIRE_AUTH` MUST default `true` zijn.
Een request zonder identity-header MUST met HTTP 403 geweigerd worden, met
uitzondering van het probe-endpoint `/healthz`.

`REQUIRE_AUTH=false` MAY gebruikt worden voor lokale ontwikkeling; die stand
MUST NOT de default zijn.

Rationale: een verkeerd geconfigureerde ingress moet naar "op slot" degraderen,
niet naar "open".

#### Scenario: Request zonder identity-header

- **WHEN** een request de app bereikt zonder identity-header en `REQUIRE_AUTH` staat aan
- **THEN** antwoordt de app met 403
- **AND** wordt geen auditdata gelezen of gewijzigd

#### Scenario: Probe-endpoint blijft bereikbaar

- **WHEN** de liveness/readiness-probe `/healthz` opvraagt zonder identity-header
- **THEN** antwoordt de app met een ok-status

#### Scenario: Request met identity-header

- **WHEN** een request arriveert met een identity-header uit een toegestaan domein
- **THEN** verwerkt de app het request normaal

### Requirement: De proxy is de enige netwerk-listener

De app MUST op `127.0.0.1` binden. oauth2-proxy MUST de enige container in de pod
zijn die op het pod-netwerk luistert. Een NetworkPolicy MUST pod-ingress beperken
tot de `ingress-nginx`-namespace op de proxy-poort.

Rationale: dit is het trust-anker onder de identity-header. Zonder deze twee
maatregelen is de header spoofbaar en is de fail-closed-check schijnzekerheid.

#### Scenario: De app is niet direct bereikbaar vanaf het pod-netwerk

- **WHEN** een andere pod in het cluster de app-poort direct probeert te bereiken
- **THEN** slaagt de verbinding niet

#### Scenario: Alleen de ingress-controller mag de proxy bereiken

- **WHEN** een pod buiten `ingress-nginx` de proxy-poort probeert te bereiken
- **THEN** blokkeert de NetworkPolicy de verbinding

### Requirement: Het trust-model is nagelezen kunnen worden

De repo MUST documenteren waarom de identity-header te vertrouwen is: de
topologie (localhost-bind + NetworkPolicy) en de fail-closed-stand, met de
lokale smoke-test die het aantoont zonder cluster.

Rationale: het auditbewijs is niet dat de code klopt, maar dat een reviewer kan
nalezen waaróm hij klopt.

#### Scenario: Fail-closed is lokaal aantoonbaar

- **WHEN** de app lokaal draait zonder proxy en zonder identity-header
- **THEN** antwoordt zij met 403
- **AND** antwoordt zij met 200 wanneer de header handmatig wordt meegegeven

### Requirement: De geverifieerde identiteit landt in de append-only trail

Elke auditor-beslissing MUST de geverifieerde identiteit als `actor` vastleggen.
De app MUST de identiteit uit de identity-header doorgeven aan
`AuditSession.apply_triage()`; de default-waarde `"auditor"` MUST NOT in een
portaalrun in de trail terechtkomen.

Rationale: `apply_triage()` schrijft al een `actor`-veld, maar de API geeft het
niet mee — dus staat er nu in élke regel dezelfde placeholder. Een append-only
trail zonder toewijsbare actor beantwoordt de eerste vraag van een auditor niet:
wie heeft deze bevinding gevalideerd of verworpen.

#### Scenario: Triage-regel is toewijsbaar

- **WHEN** een geauthenticeerde auditor een bevinding triëert
- **THEN** bevat de trail-regel de identiteit van die auditor als `actor`
- **AND** staat er niet de placeholder-waarde

#### Scenario: Geen beslissing zonder identiteit

- **WHEN** een triage-request de app bereikt zonder identity-header en `REQUIRE_AUTH` staat aan
- **THEN** wordt de beslissing niet vastgelegd

### Requirement: Toegang eindigt binnen een begrensd en gedocumenteerd venster

De sessieduur MUST begrensd zijn en de restduur na intrekking MUST gedocumenteerd
zijn als geaccepteerd risico. Bij offboarding MUST er een beschreven handeling
zijn waarmee toegang direct eindigt en niet pas bij cookie-verval.

Rationale: de proxy-cookie draagt de identiteit zelf (`session_cookie_minimal`),
dus het uitzetten van een Keycloak-account maakt een al uitgegeven cookie niet
ongeldig. Zonder deze eis houdt een offboarde auditor tot de cookie-levensduur
toegang — precies het gat dat deze change zegt te dichten. Rotatie is
containment, niet eradicatie.

#### Scenario: Offboarding heeft een directe handeling

- **WHEN** een auditor de organisatie verlaat
- **THEN** beschrijft de documentatie de handeling waarmee toegang onmiddellijk eindigt
- **AND** is de maximale restduur bij alleen accountuitzetting expliciet vastgelegd

#### Scenario: Sessieduur is begrensd

- **WHEN** een sessie de geconfigureerde levensduur bereikt
- **THEN** moet de auditor opnieuw authenticeren

### Requirement: Toegang en beslissingen zijn gelogd, credentials niet

Authenticatie-events en verzoeken die auditdata wijzigen MUST gelogd worden met
de identiteit van de aanvrager. Credential-waarden, tokens en cookie-inhoud
MUST NOT in logs voorkomen.

#### Scenario: Mutatie is te herleiden in de logs

- **WHEN** een auditor auditdata wijzigt
- **THEN** bevat het log de identiteit en het tijdstip

#### Scenario: Logs bevatten geen geheimen

- **WHEN** de logs op secrets gescand worden
- **THEN** komen er geen credential-waarden, tokens of cookie-inhoud in voor

### Requirement: Kosten-dragende runs zijn herleidbaar naar een mens

Elke run die de organisatie-LLM-key uitgeeft MUST gelogd worden met de identiteit
van wie hem startte, en het token-verbruik MUST bijgehouden worden.

**Besluit 2026-08-12 — loggen, niet begrenzen.** Er komt géén rate limit, in
afwijking van het openwoo-patroon (`ASSISTANT_RATE_LIMIT`). Bewust, met een
benoemd restrisico: een ingelogde auditor kan onbeperkt runs starten op de org-key.
Aanvaard omdat de gebruikersgroep klein en geverifieerd is (`email_domains`) en
omdat kosten-logging de misbruikvraag beantwoordbaar maakt. Knijpt het in de
praktijk, dan is een limiet een eigen change — geen stille toevoeging.

Rationale voor de herleidbaarheid: `Kostenteller` in
`iso_audit.classification.findings` hield token-verbruik en kosten al bij, maar
niet wie de run startte. Zonder die koppeling is een kostenpiek niet te adresseren.

#### Scenario: Run is toewijsbaar

- **WHEN** een auditor een run start
- **THEN** bevat het audit-log een regel met de identiteit en de run-configuratie

#### Scenario: Geen stille begrenzing

- **WHEN** een auditor veel runs achter elkaar start
- **THEN** worden ze uitgevoerd en gelogd
- **AND** wordt geen verzoek geweigerd op een niet-gedocumenteerde limiet
