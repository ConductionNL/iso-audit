# Spec — landschap (nieuw)

## ADDED Requirements

### Requirement: Het documentenlandschap staat los van een audit

Het portaal MUST het inlezen van bronnen aanbieden als een handeling op tool-niveau, niet
onder één audit. Er MUST één voorraad ingelezen documenten zijn die alle audits gebruiken.

Het portaal MUST NOT dezelfde inleesactie ook onder een audit aanbieden: twee ingangen naar
dezelfde opslag laten een auditor geloven dat hij iets eigens heeft.

Bij het inlezen MUST worden vastgelegd wat er gelezen is, vóór en los van enige
classificatie. Documenten MUST idempotent worden opgeslagen, zodat opnieuw inlezen niets
dupliceert.

Rationale: de opslag was al gedeeld (één `AUDIT_DB_PATH`), de handeling niet. Het landschap
is van de organisatie; een audit kijkt ernaar. En een Drive-lezing kost minuten — die per
audit herhalen is verspilling zonder tegenprestatie.

#### Scenario: Landschap inlezen

- **WHEN** een auditor het landschap laat inlezen met een of meer bronnen
- **THEN** worden de documenten van die bronnen opgeslagen met hun clausule-koppelingen
- **AND** raakt die handeling de classificatie-API niet
- **AND** is het resultaat zichtbaar zonder een audit te openen

#### Scenario: Opnieuw inlezen dupliceert niet

- **WHEN** het landschap twee keer achter elkaar wordt ingelezen
- **THEN** staat elk document één keer in de voorraad

### Requirement: De staat van het landschap is opvraagbaar

Het portaal MUST tonen hoeveel documenten er in de voorraad zitten, per bron, en wanneer er
voor het laatst is ingelezen.

Een bron die tijdens het inlezen faalt MUST worden benoemd met een genormaliseerde reden.
Het portaal MUST NOT een inleesactie als geslaagd melden wanneer een gekozen bron niets
opleverde.

Rationale: zonder deze twee is "hebben we alles gezien?" niet te beantwoorden, en dat is
precies de vraag die een auditor over zijn eigen dossier moet kunnen stellen. Een stil
overgeslagen bron is gemeten: Jira gaf HTTP 400 en leverde nul documenten terwijl de run
`klaar` meldde.

#### Scenario: Een bron faalt tijdens het inlezen

- **WHEN** één van de gekozen bronnen een fout geeft
- **THEN** blijven de documenten van de andere bronnen bewaard
- **AND** benoemt het portaal welke bron niets opleverde, met een genormaliseerde reden
- **AND** meldt het de handeling niet als volledig geslaagd

### Requirement: Bronnen leveren opvolgpunten in plaats van documenten waar dat past

Een bron die openstaande punten kent MUST die als zodanig leveren, en MUST NOT als
bewijsmateriaal tegen clausules worden geclassificeerd.

Opvolgpunten MUST zonder classificatie in de triage terechtkomen: ze zijn al beoordeeld
door degene die ze aanmaakte.

Rationale: Jira-tickets zijn afgesproken verbeteracties, geen bewijs. Ze tegen elke clausule
classificeren levert bevindingen als *"dit ticket bewijst §4.1 niet"* — gemeten in de
referentie-output — plus LLM-kosten per ticket. Het `Source`-protocol modelleerde dit al
met `list_findings`; dat was alleen nooit aangesloten.

#### Scenario: Jira levert openstaande punten

- **WHEN** een run Jira als bron gebruikt
- **THEN** verschijnen de openstaande, gelabelde issues als opvolgpunten in de triage
- **AND** wordt er geen classificatie-aanroep voor gedaan
- **AND** ontstaan er geen bevindingen die een ticket afrekenen op een clausule

#### Scenario: Een bron zonder opvolgpunten blijft documenten leveren

- **WHEN** een bron `list_findings` niet ondersteunt
- **THEN** levert hij documenten, zoals voorheen
