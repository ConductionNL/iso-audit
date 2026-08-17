# Spec — iso-agents (nieuw)

## ADDED Requirements

### Requirement: Elke agent heeft één bronregel, en die is zichtbaar

Elke agent MUST precies één bronregel hebben: alleen ons corpus, alleen de normteksten, beide,
of modelkennis. Het antwoord MUST tonen welke agent het gaf en daarmee waar het vandaan komt.

Een agent MUST NOT putten uit een bron die buiten zijn regel valt.

Rationale: de vier vragen die een auditor stelt verschillen fundamenteel in wat een geldig
antwoord is. "Welk bewijs hebben wij voor 8.24" is alleen uit onze documenten te beantwoorden;
"wat eist 8.24" alleen uit de norm; "schrijf een cryptografiebeleid" uit geen enkele bron. Eén
regel voor alles betekent ofwel onnatrekbare tekst in een audittool, ofwel een assistent die
niet kan uitleggen wat een clausule eist.

#### Scenario: Vraag om bewijs

- **WHEN** de auditor vraagt welk bewijs er is voor een clausule
- **THEN** antwoordt de Bronbevrager uit het corpus
- **AND** blijkt uit het antwoord dat het uit onze documenten komt

#### Scenario: Vraag om normuitleg

- **WHEN** de auditor vraagt wat een clausule eist
- **THEN** antwoordt de Normuitlegger uit `data/normteksten`
- **AND** beweert het antwoord niets over Conduction

### Requirement: Wat het tool opstelt telt nooit als bewijs

Door de Opsteller gegenereerde documenten MUST een merkteken dragen dat met het document
meereist.

De classificatie MUST zulke documenten negeren als bewijs, totdat een mens aantoonbaar heeft
vastgelegd dat de organisatie ze heeft overgenomen.

Rationale: zonder deze regel schrijft de Opsteller een beleidsstuk, belandt dat in Drive, en
leest de classificatiepipeline het als bewijs voor de clausule waar het op is gemapt. Het tool
auditeert dan zijn eigen output. Voor ISO 27001 raakt dat de onafhankelijkheid van de interne
auditfunctie, en dat is bij een gecertificeerde organisatie een vraag die gesteld wordt.

#### Scenario: Opgesteld document belandt in het landschap

- **WHEN** een door de Opsteller gegenereerd document in een gekoppelde Drive-locatie staat
- **THEN** telt het niet mee als bewijs bij de classificatie
- **AND** is aan het document te zien dat het door het tool is opgesteld

#### Scenario: Organisatie neemt het document over

- **WHEN** een mens heeft vastgelegd dat de organisatie het document heeft overgenomen
- **THEN** telt het vanaf dat moment als gewoon bewijs
- **AND** staat die overname in de trail

### Requirement: De Gap-analist velt geen eigen oordeel

De Gap-analist MUST de bestaande classificatie hergebruiken en MUST NOT zelf clausules
classificeren.

Hij MUST zijn constatering baseren op het `bewijslast`-veld per clausule naast wat er gekoppeld
is.

Rationale: de classificatiepipeline doet document × clausule → NC/OFI/positief al. Een agent
die dat via een vraagvenster overdoet, levert een tweede antwoord op dezelfde vraag met een
ander oordeel erin — en dan is niet meer te zeggen welk van de twee in het auditrapport hoort.

#### Scenario: Vraag naar wat ontbreekt

- **WHEN** de auditor vraagt wat er nog ontbreekt voor een hoofdstuk
- **THEN** toont de Gap-analist per clausule de verwachte bewijslast naast wat er gekoppeld is
- **AND** komt het oordeel uit de bestaande classificatie, niet uit deze agent

### Requirement: Geen agent schrijft in de audit

Geen enkele agent MUST bevindingen aanmaken of wijzigen, triage-oordelen vastleggen, of de
werkset van een audit aanraken.

Rationale: de auditor-spiegel is de capability die dit tool draagt — op vaste punten houdt een
mens het oordeel. Een agent die een concept-NC oppert schuift dat oordeel richting het model, en
een concept dat er al staat wordt bevestigd in plaats van gevormd.

#### Scenario: Vraag die om een oordeel vraagt

- **WHEN** de auditor vraagt of iets een NC is
- **THEN** toont de agent het bewijs en de eerdere oordelen met hun bron
- **AND** legt hij zelf geen classificatie vast

### Requirement: De catalogus komt uit de repo

De normkennis van de agents MUST uit `data/normteksten` komen.

Er MUST NOT een controlecatalogus van buiten worden ingevoerd met beschrijvende normtekst.

Rationale: `data/normteksten` heeft 93 clausules voor 27001 — het aantal Annex A-controls van
2022 — en 28 voor 9001, met per clausule `normtekst` (verkort), `interpretatie` en `bewijslast`.
Dat laatste veld heeft geen enkele externe catalogus, en het is precies wat de Gap-analist
nodig heeft. Daarnaast houdt de repo bewust verkorte eisen aan; een geleende catalogus met
beschrijvingen leunt tegen ISO/IEC 27002-materiaal aan.

#### Scenario: Agent heeft normkennis nodig

- **WHEN** een agent moet weten wat een clausule eist
- **THEN** komt dat uit `data/normteksten`

### Requirement: Elke vraag en elk antwoord staat append-only in de trail

Elke vraag MUST met haar antwoord worden vastgelegd, samen met de agent die antwoordde, de
bron-ID's die zijn meegegeven, welke daarvan in het antwoord terugkomen, het model, en de kosten
met peildatum en prijsgrondslag.

Vastgelegde vragen en antwoorden MUST NOT worden overschreven.

Rationale: wat de auditor het tool vroeg is onderdeel van hoe het oordeel tot stand kwam, en dat
mag een certificerende instantie navragen. Welke agent antwoordde is daarbij net zo belangrijk
als het antwoord: het bepaalt of er een bron achter zat of modelkennis.

#### Scenario: Antwoord blijkt later verkeerd

- **WHEN** een eerder antwoord wordt nagetrokken
- **THEN** is uit de trail op te maken welke agent antwoordde en welke bronnen die kon zien
