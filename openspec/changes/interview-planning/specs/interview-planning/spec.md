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

### Requirement: Niet elk gat vraagt een interview

Een interview MUST alleen worden voorgesteld voor bewijslast die een mens kan bevestigen.

Voor bewijslast die om een artefact vraagt MUST NOT een interview in de plaats komen.

Rationale: voor "de Verklaring van Toepasselijkheid is vastgesteld" is een document het enige
geldige bewijs. Een interview zou daar bewijs vervangen door een bewering, en dan zakt de
bewijsstandaard zonder dat iemand dat besloot.

#### Scenario: Clausule die om een document vraagt

- **WHEN** de bewijslast uitsluitend uit artefacten bestaat
- **THEN** stelt het tool geen interview voor
- **AND** blijft het gat als ontbrekend document staan

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
