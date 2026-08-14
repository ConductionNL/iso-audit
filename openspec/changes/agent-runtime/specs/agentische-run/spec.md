# Spec — agentische-run (nieuw)

## ADDED Requirements

### Requirement: De lus stopt gegarandeerd

Een agentische run MUST twee afdwingbare bovengrenzen hebben: een maximum aantal rondes en
een maximum aan kosten. Bij het bereiken van een grens MUST de lus stoppen en MUST de reden
in de trail staan.

Er MUST NOT vertrouwd worden op een adviserend budget dat het model geacht wordt te
respecteren.

Rationale: een auditor moet kunnen zeggen dat een run begrensd was. "Het model wist van een
budget" is geen begrenzing.

#### Scenario: Model blijft doorgaan

- **WHEN** het model meer rondes wil dan de limiet
- **THEN** stopt de lus op de limiet
- **AND** staat `rondelimiet` als reden in de trail

#### Scenario: Kosten lopen op

- **WHEN** de opgetelde kosten het plafond overschrijden
- **THEN** stopt de lus
- **AND** staat `kostenplafond` als reden in de trail

#### Scenario: Model zonder bekende prijs

- **WHEN** een run draait op een model zonder prijsregel
- **THEN** wordt dat gemeld
- **AND** rapporteert de run geen kosten van nul zonder waarschuwing

### Requirement: Geen tool schrijft in de audit-trail

Elke tool die aan een agent wordt aangeboden MUST read-only zijn. Een tool MUST NOT
schrijven naar de bevindingen, de run-historie of de database. Eén uitzondering: een
voorstel-kanaal, en dat MUST zelf niets opslaan.

Rationale: kan een bevinding de trail bereiken zonder door de deterministische join, dan is
de trail geen bewijs meer maar een verzameling losse beweringen.

#### Scenario: Een tool die zou schrijven

- **WHEN** een tool een schrijf-operatie bevat
- **THEN** faalt de testsuite

### Requirement: De deterministische join bepaalt wat één bevinding is

Voorstellen van een agent MUST door dezelfde deterministische dedup gaan als elke andere
bevinding. Een agent MUST NOT zelf besluiten dat twee bevindingen dezelfde zijn.

#### Scenario: Twee bijna-identieke voorstellen

- **WHEN** een agent twee voorstellen doet die alleen in schrijfwijze verschillen
- **THEN** levert de join één bevinding op

### Requirement: Elke bevinding verwijst naar bewijs

Een voorstel zonder document- of ticket-id MUST geweigerd worden, met een melding dat het
een vraag is en geen bevinding.

#### Scenario: Voorstel zonder bewijs

- **WHEN** een agent een bevinding voorstelt zonder bewijs-id
- **THEN** wordt het voorstel geweigerd
- **AND** staat het niet tussen de kandidaten

### Requirement: Een run is reproduceerbaar uit de trail

Elke tool-aanroep MUST een trail-regel opleveren met het tool, de bron, het model en de
prompt-versie.

Rationale: zonder die vier velden kun je niet nagaan wélke bronnen tot een bevinding hebben
geleid, en is een agentische run een zwarte doos.

#### Scenario: Trail na een run

- **WHEN** een run is afgerond
- **THEN** heeft elke tool-aanroep een regel met tool, audit, agent, model en prompt-versie
