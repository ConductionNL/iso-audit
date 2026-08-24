# Spec — managementmemo-1a4 (nieuw)

## ADDED Requirements

### Requirement: De memo past op één tot drie A4

De gegenereerde memo MUST binnen drie A4-pagina's blijven, en de generatie MUST melden wanneer
dat niet lukt — met het aantal pagina's en wat er is weggelaten.

De memo MUST NOT stil afkappen en MUST NOT stil doorlopen naar een vierde pagina.

Rationale: de klant stelt "1 tot 3 A4" als expliciete eis. Een memo die stil op vier pagina's
uitkomt breekt die eis zonder dat iemand het merkt — hetzelfde patroon als de PDF die maandenlang
ontbrak omdat de melding een `logger.warning` was.

#### Scenario: Memo past

- **WHEN** de gecureerde bevindingen in drie pagina's passen
- **THEN** wordt de memo geschreven en meldt de generatie het aantal pagina's

#### Scenario: Memo past niet

- **WHEN** de inhoud meer dan drie pagina's zou vullen
- **THEN** wordt de memo geschreven **en** volgt een expliciete melding met het aantal pagina's
  en welke onderdelen niet passen, zodat de auditor kan comprimeren of splitsen

### Requirement: Elke NC beantwoordt vier vragen

Elk NC-blok MUST bevatten: wat de non-conformiteit is, waarom het er een is (de onderliggende
bevindingen met bronverwijzing en clausule, plus één synthese-alinea), en een actietabel met de
kolommen **Wat**, **Wie**, **Waar** en **Uiterlijk**.

Elk NC-blok MUST afsluiten met de norm-regel: de norm en de betrokken clausules.

Rationale: dit zijn de vier vragen die het management stelt, en het is de vorm van
`Auditmemo_management_2026-06-23.pdf` — de memo die met de hand is gemaakt en die werkt.

#### Scenario: NC met drie onderliggende bevindingen

- **WHEN** drie bevindingen op drie clausules één gebrek beschrijven
- **THEN** staan ze als bullets onder één genummerde NC, met een synthese-alinea die het
  gemeenschappelijke gebrek benoemt, en één actietabel

#### Scenario: Actie zonder eigenaar of datum

- **WHEN** een actie geen `Wie` of geen `Uiterlijk` heeft
- **THEN** blijft het veld zichtbaar leeg in de tabel en meldt de generatie hoeveel acties
  onvolledig zijn — een lege cel is een openstaande beslissing en geen opmaakdetail

### Requirement: Alleen gecureerde bevindingen komen in de memo

De memo MUST alleen bevindingen met `triage_status == "valide"` opnemen.

De aanhef MUST zowel de ruwe telling als de gecureerde telling noemen.

Rationale: het verschil tussen "61 NC ongecureerd" en "2 NC na curatie" is precies wat de memo
verantwoordt. Alleen het gecureerde getal tonen verbergt hoeveel er is afgevallen; alleen het
ruwe getal tonen suggereert 61 managementbesluiten.

#### Scenario: Aanhef

- **WHEN** de run 61 NC's opleverde en er 2 valide zijn
- **THEN** noemt de aanhef beide getallen en verwijst hij naar de detailrapportage

### Requirement: Verbeterpunten staan apart en zonder besluit

Verbeterpunten (OFI's) MUST in een eigen tabel staan met de kolommen Onderwerp, Actie en Norm,
onder de vaststelling dat er geen managementbesluit nodig is maar wel opvolging.

Rationale: OFI's tussen de NC's zetten maakt van een verbeterpunt een besluitpunt. De scheiding
is wat de memo kort houdt.

#### Scenario: OFI-cluster

- **WHEN** meerdere OFI's op één clausule clusteren
- **THEN** staan ze als één regel in de verbeterpunten-tabel

### Requirement: Ontbrekende normtekst blijft een weigering, met een bruikbare melding

De generatie MUST weigeren wanneer een clausule in de memo niet in de norm-DB staat, en MUST
daarbij **alle** ontbrekende clausules noemen plus hun aantal.

Rationale: de weigering bestaat al en is juist — een memo mag geen verzonnen citaat bevatten.
Wat niet werkt is de melding: die noemt één clausule (`10.3`), terwijl er op de dataset van
2026-08-24 **75 van de 87** ontbraken. Eén clausule per poging aanvullen is geen werkbare weg.

#### Scenario: Meerdere clausules ontbreken

- **WHEN** 75 van de 87 gebruikte clausules niet in de norm-DB staan
- **THEN** weigert de generatie en noemt zij alle 75 met het totaal, niet alleen de eerste

### Requirement: De memo verwijst naar de verantwoording

De memo MUST in aanhef en voetregel verwijzen naar de detailrapportage.

De memo MUST NOT de verantwoording vervangen.

Rationale: de memo bevat enkel de acties. Zonder verwijzing is niet na te trekken waar een NC op
gebaseerd is, en dan is het een managementstuk zonder audit-waarde.

#### Scenario: Voetregel

- **WHEN** de memo wordt gegenereerd
- **THEN** staat in de voetregel de auditor, de datum en de vindplaats van de detailrapportage
