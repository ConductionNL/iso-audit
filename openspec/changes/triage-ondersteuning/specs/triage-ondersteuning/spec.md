# Spec — triage-ondersteuning (nieuw)

## ADDED Requirements

### Requirement: Eigen output telt niet als bewijs

Een document dat door dit tool is voortgebracht MUST NOT als bewijs worden geclassificeerd.

De herkenning MUST op een merkteken in het document zelf berusten en MUST NOT op de
bestandsnaam.

Rationale: gemeten op 2026-08-22 kwamen 462 van 1241 bevindingen (37%) uit twaalf bestanden die
dit tool zelf schreef — vier formaten van hetzelfde auditrapport, twee van dezelfde
bevindingenlijst, en drie managementmemo's. Een bevinding die als bewijs een eerder eigen
rapport aanwijst is geen onafhankelijke observatie maar een echo, en voor ISO 27001 raakt dat de
onafhankelijkheid van de interne auditfunctie. Op naam filteren faalt twee kanten op: een
gewijzigde naam telt stil weer mee, en `Auditrapport 2022.docx` is van de certificerende
instantie en is juist bewijs.

#### Scenario: Eigen auditrapport in een gekoppelde locatie

- **WHEN** een run een document tegenkomt met het merkteken van dit tool
- **THEN** wordt het niet geclassificeerd
- **AND** blijft het wel in het landschap staan met de reden

#### Scenario: Auditrapport van de certificerende instantie

- **WHEN** een extern auditrapport zonder merkteken wordt gelezen
- **THEN** telt het gewoon als bewijs

### Requirement: Exacte duplicaten worden samengevouwen met hun aantal

Bevindingen met dezelfde clausule, norm en genormaliseerde beschrijving MUST als één regel in
de werklijst staan, met het aantal en de brondocumenten erbij.

De vergelijking MUST exact zijn na lowercasing en whitespace-collaps, en MUST NOT een
gelijkenis-drempel gebruiken.

Rationale: 264 regels waren een exact duplicaat van een eerdere. Samenvouwen kan dus zonder
drempel — dezelfde weigering als in `runs.dedup_sleutel`, want "0,83 leek genoeg" is geen
antwoord aan een auditor. Het aantal hoort erbij: een bevinding uit vier documenten weegt
anders dan een uit één.

#### Scenario: Dezelfde bevinding uit vier documenten

- **WHEN** vier documenten dezelfde beschrijving op dezelfde clausule opleveren
- **THEN** staat er één regel in de werklijst met het aantal vier en de vier bronnen

#### Scenario: Bijna-gelijke beschrijvingen

- **WHEN** twee beschrijvingen op één clausule verschillen in meer dan witruimte
- **THEN** blijven het twee regels

### Requirement: De triage-agent bereidt voor en oordeelt niet

De agent MUST per clausule opleveren welk verwacht bewijs gedekt is, welk niet, en welke
bronnen elkaar tegenspreken — elk met verwijzing naar de bron.

Hij MUST NOT een triage-status, classificatie of oordeel voorstellen.

Rationale: de auditor-spiegel is de capability die dit tool draagt. Een voorgestelde klasse
maakt van beoordelen bevestigen, en dan is de onafhankelijkheid van de auditor een formaliteit.
De Gap-analist uit `iso-agents` heeft dezelfde grens; die twee moeten gelijk blijven, anders is
er een tweede oordeelspad met een ander antwoord op dezelfde vraag.

#### Scenario: Clausule met deels aanwezig bewijs

- **WHEN** de agent een clausule voorbereidt
- **THEN** noemt hij per verwacht bewijsstuk of het gedekt is, met verwijzing
- **AND** staat er geen voorgestelde classificatie in het resultaat

#### Scenario: Auditor vraagt om een oordeel

- **WHEN** de vraag om een classificatie vraagt
- **THEN** komt het bewijs en de eerdere oordelen terug, zonder nieuw oordeel

### Requirement: De ordening van de werklijst is zichtbaar en omkeerbaar

Staat de werklijst in een andere orde dan de clausule-orde, dan MUST per regel te zien zijn
waarom, en MUST de auditor terug kunnen naar clausule-orde.

Rationale: "waar valt de meeste onduidelijkheid weg" is een agent-uitspraak en niet
controleerbaar zoals een bronverwijzing. Een onzichtbare ordening is een oordeel dat zich
voordoet als een lijst.

#### Scenario: Werklijst op aandacht geordend

- **WHEN** de agent de werklijst ordent
- **THEN** staat per regel de reden erbij
- **AND** kan de auditor terug naar clausule-orde

### Requirement: Uitsluiten is niet verwijderen

Eigen output en samengevouwen duplicaten MUST in het landschap en in de trail blijven staan.

Rationale: dezelfde regel als bij het verbergen van runs. Wat uit een werklijst verdwijnt moet
vindbaar blijven voor wie ernaar zoekt; een certificerende instantie mag navragen wat er is
ingezien en waarom het niet is gewogen.

#### Scenario: Uitgesloten document navragen

- **WHEN** een auditor vraagt waarom een document niet is geclassificeerd
- **THEN** is uit het landschap op te maken dat het eigen output is
