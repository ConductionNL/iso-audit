# Spec — triage-agents (nieuw)

## ADDED Requirements

### Requirement: De hub is code, geen model

De orchestratie MUST deterministisch zijn: welke clusters er zijn, welke spoke welk werk krijgt
en in welke volgorde, MUST uit een regel volgen en niet uit een modelbeslissing.

Rationale: "waarom is deze bevinding wel bekeken en die niet" moet met een regel te antwoorden
zijn. Een model als orchestrator maakt twee runs op dezelfde dataset onvergelijkbaar.

#### Scenario: Twee runs op dezelfde werkset

- **WHEN** de hub twee keer op een onveranderde werkset draait
- **THEN** krijgen dezelfde clusters dezelfde opdrachten, in dezelfde ordening

### Requirement: Spokes praten niet met elkaar

Een spoke MUST NOT de uitvoer van een andere spoke als invoer krijgen. Elke spoke MUST zijn
bronnen rechtstreeks uit het corpus krijgen, via de hub.

Rationale: na twee schakels is een bewering niet meer naar een document te herleiden. Dezelfde
reden dat de Bronbevrager geen gesprek voert.

#### Scenario: Synthese na triage

- **WHEN** de Synthesizer een thema samenvat
- **THEN** krijgt hij de bevindingen en hun bronnen, niet de tekst van de Triage-ondersteuner

### Requirement: Elke spoke verwijst naar bronnen die hij heeft gekregen

Elke bewering in het antwoord van een spoke MUST verwijzen met `[bron:<id>]`, en elk id MUST in
het meegegeven corpus voorkomen. Klopt dat niet, dan MUST het een storing zijn en geen antwoord.

Een antwoord zonder énige verwijzing MUST vervangen worden door een vaste tekst; de onbewerkte
modeltekst MUST naar de trail.

Rationale: dit is de bestaande regel van de Bronbevrager en het enige verschil tussen "we hebben
het gevraagd" en "we hebben het gecontroleerd". Bij een hub met tientallen aanroepen per run
weegt dat zwaarder, niet lichter.

#### Scenario: Verzonnen bron-ID

- **WHEN** een spoke verwijst naar een id dat niet in zijn corpus zat
- **THEN** is het een storing, met reden, in de trail

### Requirement: Geen agent velt een triage-oordeel

De Landschapsagent en de Triage-ondersteuner MUST NOT een triage-status, classificatie, advies of
aanbeveling in hun antwoord opnemen. De weigering MUST afgedwongen zijn met een veldcontrole,
niet met een instructie in de prompt.

Geen agent MUST NOT een `triage_status` in de werkset schrijven.

Rationale: `assistent/clausule.py` heeft deze grens al met `VERBODEN_VELDEN` en een test die
faalt als iemand hem oprekt. Een voorgestelde klasse maakt van beoordelen bevestigen, en de
auditor-spiegel is de capability die dit tool draagt.

#### Scenario: Agent stelt toch een status voor

- **WHEN** het antwoord een verboden veld bevat
- **THEN** wordt het geweigerd en gelogd, en ziet de auditor geen voorstel

#### Scenario: Agent schrijft in de werkset

- **WHEN** een agent-pad `apply_triage` probeert aan te roepen
- **THEN** is dat niet mogelijk: agents hebben geen schrijfrecht op de werkset

### Requirement: De Synthesizer levert een concept dat een mens moet aanraken

De synthese-tekst MUST als concept met een eigen status worden opgeslagen, en MUST NOT in de
memo terechtkomen zonder redactie door de auditor.

De onbewerkte modeltekst MUST in de trail blijven, ook nadat de auditor hem heeft herschreven.

Rationale: dit is de enige agent-uitvoer die de deur uit gaat. Zonder de onbewerkte tekst in de
trail is later niet vast te stellen of een zin van de auditor of van het model kwam.

#### Scenario: Concept niet geredigeerd

- **WHEN** de auditor de synthese-alinea niet heeft aangeraakt
- **THEN** blokkeert de memo-generatie op dat thema, met de reden

### Requirement: Modelkeuze en kosten per agent staan in de trail

Elke agent-aanroep MUST met model, kosten, peildatum en prijsgrondslag in `assistent_vragen`
staan. De run-samenvatting MUST de agentkosten optellen.

Een storing MUST óók worden vastgelegd, met de reden en zonder antwoord.

Rationale: agents mogen een zwaarder model gebruiken, en dan moet iemand kunnen besluiten of dat
het waard was. Vandaag laat een 500 op de assistent-route géén spoor — bij tientallen aanroepen
per run is dat het verschil tussen een trail en een gok.

#### Scenario: Storing in een spoke

- **WHEN** een spoke faalt met een exceptie
- **THEN** staat er een rij in de trail met de reden, en gaat de hub verder met de andere spokes

### Requirement: Parallellisme heeft een bovengrens

Het aantal gelijktijdige spoke-aanroepen MUST begrensd zijn, en de grens MUST configureerbaar
zijn.

Rationale: 87 clausules zijn zonder grens 87 gelijktijdige aanroepen. De Planning-bron liep in
juli 2026 tegen 429's op precies dit patroon.

#### Scenario: Meer clusters dan de grens

- **WHEN** er meer clusters zijn dan de bovengrens
- **THEN** worden ze in porties verwerkt, en meldt de voortgang hoeveel er nog wachten
