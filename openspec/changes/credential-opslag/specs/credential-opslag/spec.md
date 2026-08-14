# Spec — credential-opslag (nieuw)

## ADDED Requirements

### Requirement: Configuratie kan in een Secret staan, met de PVC als terugval

Het portaal MUST UI-configuratie in een Kubernetes-Secret kunnen bewaren wanneer dat is
geconfigureerd en er een serviceaccount-token beschikbaar is. Is de kube-API onbereikbaar,
dan MUST het portaal terugvallen op de bestaande opslag op het volume, met een waarschuwing.

Het portaal MUST NOT weigeren te starten of te configureren omdat de Secret-backend
onbereikbaar is.

Rationale: zonder terugval is het tool niet buiten dit cluster te draaien, en dat was juist
de reden om configuratie uit het cluster te halen.

#### Scenario: Secret beschikbaar

- **WHEN** de Secret-backend geconfigureerd is en de kube-API werkt
- **THEN** komt een wijziging in het Secret terecht

#### Scenario: kube-API onbereikbaar

- **WHEN** de kube-API niet bereikbaar is
- **THEN** wordt de wijziging op het volume bewaard
- **AND** staat er een waarschuwing in de log

#### Scenario: Geen cluster

- **WHEN** het portaal buiten Kubernetes draait
- **THEN** werkt configureren als voorheen

### Requirement: De rechten zijn beperkt tot één Secret

De rechten van het portaal op de kube-API MUST beperkt zijn tot `get` en `patch` op precies
het configuratie-Secret. Er MUST NOT een recht zijn om Secrets op te sommen, en de rechten
MUST namespace-scoped zijn.

Rationale: zonder beperking op naam mag de pod élk Secret in de namespace lezen, inclusief
de bron-credentials en het oauth2-secret. Een recht om op te sommen maakt de
naambeperking in de praktijk zinloos.

#### Scenario: Ander Secret

- **WHEN** het portaal een ander Secret in de namespace probeert te lezen
- **THEN** weigert de kube-API dat

### Requirement: De token wordt niet aan andere containers gegeven

Het serviceaccount-token MUST alleen beschikbaar zijn in de container die de kube-API nodig
heeft, en MUST kortlevend zijn.

#### Scenario: Sidecar

- **WHEN** de pod draait
- **THEN** heeft de auth-proxy-container geen serviceaccount-token

### Requirement: Een kube-API-fout geeft geen responsbody terug

Een fout van de kube-API MUST omgezet worden naar een melding zonder de responsbody, omdat
die het meegestuurde token kan echoën.

#### Scenario: Geweigerd verzoek

- **WHEN** de kube-API een verzoek weigert
- **THEN** bevat de foutmelding de statuscode
- **AND** bevat hij niet de responsbody
