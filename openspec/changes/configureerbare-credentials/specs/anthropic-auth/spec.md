# Spec — anthropic-auth (nieuw)

## ADDED Requirements

### Requirement: Twee auth-modi, expliciet gekozen

Het portaal MUST twee Anthropic-auth-modi ondersteunen: `api_key` en `sso`. De modus MUST
een expliciet veld zijn; er MUST NOT geraden worden op basis van wat er toevallig gezet is.

Bij `sso` MUST de authenticatie via het profiel van de Anthropic-CLI lopen, dat de SDK
zelf al als credential-bron kent. Er MUST NOT een tweede aanroeppad voor de classifier
gebouwd worden.

Rationale: de SDK lost credentials al op in de volgorde API-key, auth-token, CLI-profiel.
Een subscription werkt daardoor zonder codewijziging in de classifier.

#### Scenario: Modus api_key

- **WHEN** de modus `api_key` is en er een key is ingesteld
- **THEN** draait een classificatie op die key

#### Scenario: Modus sso zonder login

- **WHEN** de modus `sso` is en er nog geen profiel bestaat
- **THEN** meldt de statuscheck dat er geen actieve credential is
- **AND** wijst hij de auditor naar de loginactie

### Requirement: Bij sso mag geen API-key in de omgeving overblijven

Wanneer de modus `sso` is, MUST de loader een aanwezige API-key-variabele **verwijderen**
uit de omgeving — ook als die leeg is.

Rationale: de SDK laat een gezette API-key-variabele voorgaan op het profiel, óók een lege
string. Alleen "niet zetten" is dus niet genoeg: een key die van elders in de omgeving komt
zou het profiel stil overrulen en de run laten falen op een credential die de auditor niet
gekozen heeft.

#### Scenario: Lege key naast sso

- **WHEN** de modus `sso` is en er een lege API-key-variabele in de omgeving staat
- **THEN** is die variabele na het laden van de configuratie verdwenen

### Requirement: Uitloggen wist de sessie

Er MUST een actie zijn die het opgeslagen profiel wist, zodat een auditor zijn
Anthropic-sessie kan beëindigen zonder het portaal te herstarten.

#### Scenario: Uitloggen

- **WHEN** een auditor uitlogt bij Anthropic
- **THEN** is er geen actief profiel meer
- **AND** meldt de statuscheck dat er geen credential is

### Requirement: Het model is kiesbaar en heeft een bekende prijs

Het te gebruiken model MUST configureerbaar zijn, met een expliciete default. Elk model
dat gekozen kan worden MUST een prijsregel hebben, zodat kostenrapportage niet stil
onvolledig wordt.

Kostenbedragen MUST een peildatum dragen, want prijzen veranderen buiten deze repo om.

Rationale: een model zonder prijsregel levert een auditrapport met een kostenpost die te
laag is. Dat is erger dan geen kostenpost, want het ziet er compleet uit.

#### Scenario: Model zonder prijsregel

- **WHEN** een model kiesbaar is zonder prijsregel
- **THEN** faalt de testsuite

#### Scenario: Kosten in een rapport

- **WHEN** een run kosten rapporteert
- **THEN** staat er een peildatum bij de gebruikte tarieven

### Requirement: Een verbinding is te testen zonder de fout te laten lekken

Per integratie MUST er een read-only verbindingstest zijn die slagen of falen meldt. De
foutmelding MUST genormaliseerd zijn en MUST NOT de ruwe respons van de leverancier
doorgeven.

Rationale: ruwe foutmeldingen bevatten soms het meegestuurde token of een volledige URL
met credential.

#### Scenario: Verkeerde credential

- **WHEN** een verbindingstest faalt op authenticatie
- **THEN** meldt het portaal dat de credential geweigerd is
- **AND** staat de ruwe leveranciersrespons niet in het antwoord
