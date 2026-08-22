# Spec — interview-planning (nieuw)

## ADDED Requirements

### Requirement: Een interviewvoorstel komt uit de norm-catalogus

De voorgestelde vragen MUST afgeleid zijn van de `bewijslast` per clausule in
`data/normteksten`.

Het tool MUST NOT vragen toevoegen die niet op een bewijslast-item terug te voeren zijn.

Rationale: een agent die vrije interviewvragen bedenkt, verzint eisen die niet in de norm staan.
In een auditdossier staat dan een vraag die niemand kan herleiden, en dat is precies het soort
onnatrekbaarheid dat de rest van dit tool weert.

#### Scenario: Ongedekte clausule met bewijslast

- **WHEN** een clausule geen documentbewijs heeft
- **THEN** bevat het voorstel per open bewijslast-item een vraag
- **AND** is elke vraag te herleiden naar dat item

### Requirement: Het voorstel noemt een rol en geen persoon

Een interviewvoorstel MUST de rol noemen die over het onderwerp gaat.

Het MUST NOT een persoonsnaam of e-mailadres invullen dat niet door een mens is opgegeven.

Rationale: de norm-catalogus kent geen personen, en het tool weet niet wie bij Conduction over
toegangsrechten gaat. Een verzonnen naam in een auditplanning is erger dan een lege — hij ziet
uit als een afspraak die iemand heeft gemaakt.

#### Scenario: Voorstel voor een clausule over toegangsbeheer

- **WHEN** het tool een interview voorstelt
- **THEN** staat er een rol in het voorstel
- **AND** staat er geen naam die het tool zelf heeft bedacht

### Requirement: Een interview wijst naar bewijs en vervangt het niet

Een interviewvraag MUST vragen waar een ontbrekend artefact is vastgelegd, of waarom het niet
bestaat.

Een gesproken antwoord MUST NOT als bewijs voor een clausule gelden waar de norm een artefact
verwacht.

Rationale: voor "de Verklaring van Toepasselijkheid is vastgesteld" is een document het enige
geldige bewijs; een interview dat dat vervangt laat de bewijsstandaard zakken zonder dat iemand
dat besloot. Maar de vraag "waar staat de VvT?" is juist wat een auditor stelt — en het antwoord
is een aanwijzing, of de constatering dat het artefact ontbreekt.

Gemeten op 2026-08-22: van de 481 bewijslast-items in `data/normteksten` beschrijven er ongeveer
drie een waarneming. De catalogus is artefact-gericht, dus "welk bewijs kan een mens bevestigen"
levert vrijwel niets op; "waar is dit artefact" levert per ongedekte clausule een bruikbare
vraag.

#### Scenario: Clausule zonder documentbewijs

- **WHEN** een clausule geen gekoppeld document heeft
- **THEN** vraagt het voorstel per ontbrekend artefact waar het is vastgelegd

#### Scenario: Antwoord vastgelegd

- **WHEN** een geïnterviewde antwoordt dat het artefact niet bestaat
- **THEN** staat dat als aanwijzing in de trail
- **AND** velt het tool daarover geen classificatie

### Requirement: Inplannen is een aparte handeling met een spoor

Een agenda-uitnodiging MUST NOT als onderdeel van een run worden verstuurd.

Wie inplant MUST dat als expliciete handeling doen, en die handeling MUST append-only in de
trail staan met de clausule, de rol en de uitkomst.

Rationale: dit is de eerste keer dat dit tool iets naar buiten schrijft dat een mens verplicht.
Een run die ongevraagd agenda's vult is een run die niemand meer durft te starten. En het spoor
is zelf auditbewijs: het toont aan dat een gat is opgevolgd.

#### Scenario: Auditor plant een voorgesteld interview in

- **WHEN** de auditor het inplannen bevestigt
- **THEN** staat de handeling in de trail met clausule, rol en uitkomst

#### Scenario: Twee keer inplannen voor dezelfde clausule

- **WHEN** hetzelfde interview nog een keer wordt ingepland
- **THEN** komt er geen tweede uitnodiging

### Requirement: Het antwoord van de mens gaat ongewijzigd in de trail

Wat een geïnterviewde heeft geantwoord MUST ongewijzigd worden vastgelegd.

Het MUST NOT door een model worden samengevat of geherformuleerd voordat het wordt opgeslagen.

Rationale: wat iemand in een audit heeft gezegd, is bewijs. Een geparafraseerde versie is dat
niet — en het verschil valt achteraf niet meer vast te stellen.

#### Scenario: Auditor legt een antwoord vast

- **WHEN** het antwoord wordt opgeslagen
- **THEN** staat de tekst er zoals hij is ingevoerd
