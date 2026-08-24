# Spec — voortgangsbewaking (nieuw)

## ADDED Requirements

### Requirement: Een actie heeft een eigenaar, een termijn en een status

Elke actie MUST de velden `wat`, `wie`, `waar` en `uiterlijk` hebben, plus een status uit: open,
in uitvoering, aangetoond, vervallen.

Elke statuswisseling MUST met identiteit, tijdstip en reden in de append-only trail komen.

Rationale: dezelfde discipline als triage. Een status die verandert zonder spoor maakt niet
navolgbaar wie besloot dat een maatregel klaar was.

#### Scenario: Actie zonder eigenaar

- **WHEN** een actie geen `wie` heeft
- **THEN** blijft hij zichtbaar als onvolledig en telt hij mee als openstaand — niet verbergen

### Requirement: "Aangetoond" kan niet zonder verwijzing naar bewijs

Een actie MUST NOT de status `aangetoond` krijgen zonder verwijzing naar bewijs: een
Jira-issue, een document uit het landschap, of een bevinding uit een latere run.

Rationale: ISO 9001 §10.2 vraagt om vaststelling van de **doeltreffendheid**, niet om een
afvinkje. Een bewering zonder bron is voor een audit waardeloos — dezelfde regel als bij de
Bronbevrager.

#### Scenario: Sluiten zonder bewijs

- **WHEN** iemand een actie op `aangetoond` zet zonder verwijzing
- **THEN** wordt dat geweigerd, met de reden

#### Scenario: Sluiten met een Jira-issue

- **WHEN** de verwijzing een opvolgpunt met herkomst `<bron>-opvolging` is
- **THEN** wordt de status geaccepteerd en staat de verwijzing in de trail

### Requirement: Het overzicht kijkt over audits heen

Het scherm MUST alle openstaande acties tonen, ongeacht in welke audit of run ze zijn ontstaan,
gesorteerd op termijn met verlopen acties bovenaan.

Het scherm MUST NOT alleen de acties van de laatste run tonen.

Rationale: een audit is een moment, opvolging is een lijn. Een openstaande actie uit Q1 die in Q3
nog leeft, is precies de bevinding die een auditor zoekt — en die verdwijnt uit beeld als het
overzicht per run is.

#### Scenario: Actie uit een eerdere audit

- **WHEN** een actie uit Q1 nog open is tijdens de Q3-audit
- **THEN** staat hij in het overzicht, met de audit waaruit hij komt

### Requirement: De planning laat zien of een clausule opnieuw wordt getoetst

Het overzicht MUST per openstaande actie tonen wanneer de bijbehorende clausule volgens de
auditplanning weer aan de beurt is, als die planning gekoppeld is.

Rationale: dit is de vraag bij het plannen — wordt deze clausule opnieuw getoetst voordat de
actie erop verloopt? Zonder dat naast elkaar is het antwoord handwerk.

#### Scenario: Planning niet gekoppeld

- **WHEN** de Planning-bron niet gekoppeld is
- **THEN** toont het overzicht de acties zonder planningkolom, met de melding waarom — niet een
  lege kolom die als "niet gepland" leest

### Requirement: Een bewakende agent draagt bewijs aan en zet geen status

Een agent MAY per actie zoeken of er bewijs van opvolging in het corpus is bijgekomen, en MUST
dat met bronverwijzing voorstellen.

Een agent MUST NOT een actiestatus wijzigen.

Rationale: "aangetoond" is een oordeel over doeltreffendheid. Zelfde grens als in
`triage-agents`: voorbereiden mag, oordelen niet.

#### Scenario: Agent vindt een gesloten Jira-issue

- **WHEN** een opvolgpunt op dezelfde clausule is gesloten sinds de actie ontstond
- **THEN** stelt de agent dat voor als kandidaat-bewijs, met verwijzing, en beslist de auditor

### Requirement: Dit is geen tweede taakbeheer

Het tool MUST NOT de uitvoering van een actie beheren (toewijzen, herinneren, doorzetten).

Rationale: de actie leeft hier omdat hij uit een auditbevinding komt. Wordt dit een
takenlijst-applicatie, dan concurreert het met het systeem waar de organisatie het al bijhoudt,
en dan lopen twee administraties uiteen — dezelfde reden dat er geen embeddings-index komt.

#### Scenario: Uitvoering elders

- **WHEN** een actie in Jira wordt uitgevoerd
- **THEN** verwijst het tool ernaar en bewaart het de verwijzing, zonder de Jira-status te
  spiegelen of te overschrijven
