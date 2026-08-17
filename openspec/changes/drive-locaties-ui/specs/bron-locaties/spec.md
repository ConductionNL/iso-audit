# Spec — bron-locaties (nieuw)

## ADDED Requirements

### Requirement: Drive-locaties worden als lijst beheerd, niet als tekstregel

Het configuratiescherm MUST de gekoppelde Drive-locaties als afzonderlijke rijen tonen, met
per rij een verwijderactie, en één invoerveld om een locatie toe te voegen.

De auditor MUST NOT zelf scheidingstekens hoeven typen. Het toevoegveld MUST zowel een
geplakte Drive-URL als een kaal ID accepteren.

Het opslagformaat blijft één komma-gescheiden waarde; dat MUST een implementatiedetail
blijven dat de UI opbouwt en uit elkaar haalt.

Rationale: de adapter leest al uit meerdere locaties, maar het veld heet "Map-ID van de
auditmap" en niemand raadt dat er een komma in mag. Een opslagformaat dat naar de UI lekt
maakt van één typefout stilletjes twee onbruikbare ID's.

#### Scenario: Tweede locatie toevoegen

- **WHEN** de auditor een Drive-URL in het toevoegveld plakt en op toevoegen drukt
- **THEN** verschijnt er een rij bij, blijft de bestaande locatie staan
- **AND** leest een volgende run uit beide locaties

#### Scenario: Locatie verwijderen

- **WHEN** de auditor een rij verwijdert
- **THEN** verdwijnt die locatie uit de configuratie
- **AND** blijven de overige locaties ongewijzigd

#### Scenario: Dezelfde locatie twee keer

- **WHEN** een locatie wordt toegevoegd die al in de lijst staat
- **THEN** wordt er geen tweede rij toegevoegd en verschijnt een melding dat hij er al is

### Requirement: Elke locatie toont wat het is

Per gekoppelde locatie MUST de UI tonen: de naam zoals Drive die kent, en of het een Shared
Drive of een gewone map betreft.

Is de naam niet op te halen, dan MUST de UI het ID tonen met een expliciete markering dat de
naam onbekend is. Het ontbreken van een naam MUST NOT de locatie als onbruikbaar melden.

Rationale: een auditor die zijn scope verantwoordt, moet kunnen zien wélke mappen in scope
zijn. Een rij met alleen een ID van 44 tekens is geen verantwoording.

#### Scenario: Naam bekend

- **WHEN** de locatie een Shared Drive of map is die het service-account mag lezen
- **THEN** toont de rij de naam en het soort

#### Scenario: Naam niet op te halen

- **WHEN** de naam niet opgehaald kan worden maar de locatie wel bestanden oplevert
- **THEN** toont de rij het ID met de markering onbekend
- **AND** blijft de status van die locatie positief

### Requirement: Een locatie zonder inhoud meldt zich niet als gekoppeld

Een locatie die bereikbaar is maar geen bestanden en geen submappen oplevert, MUST als
waarschuwing worden getoond, niet als groen.

Is vastgesteld dat het opgegeven ID geen map en geen Shared Drive is, dan MUST de melding
dat als waarschijnlijke oorzaak benoemen. Kan dat niet worden vastgesteld, dan MUST de
melding beperkt blijven tot de waarneming, zonder een oorzaak te beweren.

De bron als geheel MUST als gekoppeld gelden zodra minstens één locatie bestanden oplevert.

Rationale: de Drive-query is `'<id>' in parents`. Een bestand-ID matcht daar niets — geen
fout, een lege lijst — waardoor de probe slaagt en de UI gekoppeld meldt terwijl elke run
nul documenten uit die locatie leest. Dit is dezelfde valse groen als de hardcoded
planning-sheet die op 2026-08-16 is verwijderd.

#### Scenario: Bestand-ID in plaats van map-ID

- **WHEN** een locatie is ingevuld die naar een bestand verwijst
- **THEN** meldt die rij een waarschuwing met de oorzaak dat het geen map is
- **AND** wordt die locatie niet als gekoppeld geteld

#### Scenario: Werkelijk lege map

- **WHEN** een locatie een bestaande maar lege map is
- **THEN** meldt die rij een waarschuwing zonder een oorzaak te beweren

#### Scenario: Eén goede en één lege locatie

- **WHEN** één locatie bestanden oplevert en een tweede niets
- **THEN** blijft de bron als geheel gekoppeld
- **AND** blijft de waarschuwing bij de tweede locatie zichtbaar

### Requirement: Aantallen zijn begrensd en als zodanig benoemd

Het getoonde aantal per locatie MUST uit een niet-recursieve telling komen, en de UI MUST
duidelijk maken dat het gaat om wat er direct in de locatie staat.

De statusweergave MUST NOT een recursieve enumeratie uitvoeren.

Rationale: een recursieve telling over een Shared Drive kost minuten — gemeten 2,5 minuut
voor 409 documenten — en het configuratiescherm opent bij elke pageload.

#### Scenario: Grote Shared Drive

- **WHEN** het configuratiescherm wordt geopend met een grote Shared Drive gekoppeld
- **THEN** verschijnt de status zonder merkbare vertraging
- **AND** is het getoonde aantal niet-recursief
