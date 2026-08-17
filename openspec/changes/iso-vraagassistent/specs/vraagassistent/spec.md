# Spec — vraagassistent (nieuw)

## ADDED Requirements

### Requirement: Antwoorden komen uitsluitend uit het corpus

De assistent MUST zijn antwoord baseren op de vier bronnen van de organisatie: normteksten,
het documentenlandschap, bevindingen en audithistorie, en Jira-opvolgpunten.

Staat het antwoord niet in die bronnen, dan MUST de assistent dat zeggen. Hij MUST NOT
antwoorden uit modelkennis, ook niet gemarkeerd als algemene kennis.

Rationale: het model kent ISO 27001 en 9001 uit zijn training. Een antwoord zonder bron van
Conduction is voor een audit waardeloos — niet natrekbaar, terwijl het op bewijs lijkt. Een
markering die vandaag klopt, klopt over een jaar niet meer, en dan staat er onnatrekbare tekst
in een audittool.

#### Scenario: Vraag met dekking in het corpus

- **WHEN** de auditor vraagt welk bewijs er is voor een clausule waar documenten aan gekoppeld zijn
- **THEN** verwijst het antwoord naar die documenten

#### Scenario: Vraag zonder dekking in het corpus

- **WHEN** de vraag niet uit de bronnen te beantwoorden is
- **THEN** zegt de assistent dat het er niet in staat
- **AND** geeft hij geen antwoord uit algemene ISO-kennis

### Requirement: Elk antwoord verwijst en citeert niet

Een antwoord MUST verwijzen met clausule-ID, documentnaam en een link naar het document in het
landschapsscherm.

De assistent MUST NOT normtekst citeren, en MUST NOT letterlijk uit documenten citeren — hij
parafraseert.

Rationale: `data/normteksten/` bevat bewust verkorte eisen; letterlijke ISO-tekst doorgeven aan
een gebruiker is een andere handeling dan die tekst intern gebruiken om te classificeren. Eén
regel voor alle bronnen in plaats van per bron een andere, omdat een regel die per bron
verschilt op den duur verkeerd wordt toegepast.

#### Scenario: Antwoord over een clausule

- **WHEN** de assistent een clausule-eis uitlegt
- **THEN** parafraseert hij de eis en noemt hij het clausule-ID
- **AND** staat er geen letterlijke normtekst in het antwoord

#### Scenario: Antwoord dat naar bewijs wijst

- **WHEN** het antwoord naar een document verwijst
- **THEN** staat er een naam en een link waarmee de auditor het document zelf opent

### Requirement: Verwijzingen worden nagelopen vóór het antwoord de auditor bereikt

Elke clausule-ID en elk document-ID in een antwoord MUST voorkomen in de bronnen die aan het
model zijn meegegeven.

Klopt dat niet, dan MUST dat als storing gelden en MUST NOT het antwoord als geldig worden
getoond.

Rationale: "antwoord alleen uit de meegegeven bronnen" is een instructie in een prompt, geen
garantie. Het verschil tussen gevraagd hebben en gecontroleerd hebben is deze controle. Dezelfde
discipline als bij de classificatie: een onleesbaar of onverifieerbaar antwoord is een storing,
geen uitkomst.

#### Scenario: Antwoord verwijst naar een bron die niet is meegegeven

- **WHEN** het antwoord een document of clausule noemt die niet in de meegegeven bronnen zit
- **THEN** wordt het antwoord niet als geldig getoond
- **AND** telt het als storing in de trail

### Requirement: Tegenspraak wordt benoemd, niet opgelost

Spreken bronnen elkaar tegen, dan MUST de assistent beide tonen met hun herkomst en
constateren dat ze niet overeenkomen.

Hij MUST NOT één bron laten winnen op grond van datum, soort of volgorde.

Rationale: een document dat dekking claimt terwijl een eerdere bevinding NC zegt, is vaak zelf
de interessantste bevinding. Een regel als "nieuwste wint" verbergt precies die spanning: een
oud NC dat nooit is afgesloten verdwijnt dan achter een nieuw document.

#### Scenario: Document claimt dekking, bevinding zegt NC

- **WHEN** de bronnen elkaar tegenspreken over dezelfde clausule
- **THEN** toont het antwoord beide met hun bron
- **AND** benoemt het dat ze niet overeenkomen
- **AND** kiest het niet

### Requirement: De assistent leest en schrijft niet

De assistent MUST NOT bevindingen aanmaken of wijzigen, triage-oordelen voorstellen, of de
werkset van een audit aanraken.

Rationale: de auditor-spiegel is de capability die dit tool draagt — op vaste punten houdt een
mens het oordeel. Een assistent die een concept-NC oppert schuift dat oordeel richting het
model, en een concept dat er al staat wordt bevestigd in plaats van gevormd.

#### Scenario: Vraag die om een oordeel vraagt

- **WHEN** de auditor vraagt of iets een NC is
- **THEN** toont de assistent het bewijs en de eerdere oordelen met hun bron
- **AND** legt hij zelf geen classificatie vast

### Requirement: Vraag en antwoord staan append-only in de trail

Elke vraag MUST met haar antwoord worden vastgelegd, samen met de bron-ID's die aan het model
zijn meegegeven, welke daarvan in het antwoord terugkomen, het model, en de kosten met peildatum
en prijsgrondslag.

Vastgelegde vragen en antwoorden MUST NOT worden overschreven.

Rationale: wat de auditor het tool vroeg is onderdeel van hoe het oordeel tot stand kwam, en dat
mag een certificerende instantie navragen. De meegegeven bron-ID's zijn het punt waarop een
antwoord later na te trekken is: een antwoord dat achteraf verkeerd blijkt, is alleen te
begrijpen als je weet wat de assistent op dat moment kon zien.

#### Scenario: Vraag gesteld

- **WHEN** de auditor een vraag stelt
- **THEN** staan vraag, antwoord, meegegeven bronnen, model en kosten in de trail

#### Scenario: Antwoord blijkt later verkeerd

- **WHEN** een eerder antwoord wordt nagetrokken
- **THEN** is uit de trail op te maken welke bronnen de assistent toen kon zien

### Requirement: Alleen de auditor kan vragen stellen

Het scherm MUST achter dezelfde auth-gate zitten als de rest van het portaal.

Rationale: het corpus bevat auditbevindingen en interne memo's. Openstellen voor medewerkers of
externen is een publicatiebesluit met een eigen afweging, geen bijproduct van deze change.

#### Scenario: Onbevoegd verzoek

- **WHEN** een verzoek zonder geldige sessie binnenkomt
- **THEN** wordt het geweigerd zoals elk ander portaalpad
