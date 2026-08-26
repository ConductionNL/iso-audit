# Spec — code-en-website-bronnen (nieuw)

## ADDED Requirements

### Requirement: Een `repo`-bron leest repositories van meerdere forges

De adapter `repo` MUST repositories kunnen lezen van zowel GitHub als Codeberg, in dezelfde run
en met dezelfde uitkomstvorm.

Elke repository in de configuratie MUST expliciet zijn forge benoemen. Er MUST NOT uit de URL
worden afgeleid welke forge het is.

Rationale: de website-code van Conduction staat op Codeberg en de rest op GitHub, dus één forge
is niet genoeg voor het eerste echte gebruik. Afleiden uit de URL is de soort stille aanname die
pas opvalt als er een derde forge bijkomt of iemand een spiegel gebruikt.

#### Scenario: Twee repositories op twee forges

- **WHEN** de configuratie één GitHub- en één Codeberg-repository bevat
- **THEN** levert de run documenten uit beide, elk met de forge in de bronvermelding

#### Scenario: Onbekende forge

- **WHEN** een repository een forge noemt die de adapter niet kent
- **THEN** stopt de configuratie-validatie met een melding die de naam noemt, en draait de run
  niet met die repository stilzwijgend overgeslagen

### Requirement: De `repo`-bron leest een expliciete lijst bewijsdragende paden

De adapter MUST alleen paden ophalen die in een vastgelegde lijst staan, en MUST NOT de
volledige source-tree inlezen.

De lijst MUST in de repository zelf staan (versiebeheerd, leesbaar) en niet in de code verspreid.

Rationale: een repository is geen documentmap. Zevenhonderd bestanden inlezen levert ruis, een
run van uren en een dekking die niets zegt. Wat bewijs draagt is kort en bekend.

#### Scenario: Repository met veel bestanden

- **WHEN** een repository duizend bestanden bevat waarvan zes op de lijst staan
- **THEN** worden er zes opgehaald, en meldt de dekking dat de rest bewust niet is gelezen

#### Scenario: Pad staat op de lijst maar bestaat niet

- **WHEN** een repository geen `SECURITY.md` heeft
- **THEN** is dat een vastgelegde waarneming ("ontbreekt") en geen fout

### Requirement: Repository-metadata is bewijs en wordt vastgelegd

De adapter MUST per repository zichtbaarheid, archiefstatus, branch-protectie en de
review-eis op de hoofdbranch vastleggen.

Rationale: §8.4 (toegang tot broncode) en §8.32 (wijzigingsbeheer) gaan over instellingen, niet
over bestanden. Het vier-ogen-principe is geen belofte in een handboek maar een schakelaar op een
branch.

#### Scenario: Hoofdbranch zonder review-eis

- **WHEN** de hoofdbranch geen verplichte review kent
- **THEN** is dat een waarneming op §8.32 met de repositorynaam als bron

### Requirement: Uitspraken over wijzigingen zijn aggregaten, nooit personen

De adapter MUST wijzigingen samenvatten als aantallen (hoeveel pull requests, welk aandeel met
review, welk aandeel zelf-gemerged) en MUST NOT individuele auteurs, reviewers of
commit-auteurs vastleggen.

Rationale: een NC gaat over een proces dat niet werkt, niet over een collega. Dezelfde regel
geldt al voor de review-prompt, waar `wie` een rol is en nooit een persoon.

#### Scenario: Twintig pull requests, vier zonder review

- **WHEN** vier van de twintig laatste pull requests zonder tweede beoordelaar zijn gemerged
- **THEN** legt het tool "4 van 20 zonder review" vast, zonder namen

### Requirement: Een `website`-bron leest gepubliceerde pagina's

De adapter `website` MUST pagina's ophalen via de sitemap van de site, of via een expliciet
opgegeven lijst URL's wanneer er geen sitemap is.

De adapter MUST NOT links volgen om nieuwe pagina's te ontdekken.

De adapter MUST `robots.txt` respecteren.

Rationale: een crawler is niet te begrenzen, niet te herhalen en niet uit te leggen aan wie
vraagt wat het tool heeft gezien. Een sitemap is een lijst die de site zelf publiceert.

#### Scenario: Site met sitemap

- **WHEN** de site een `sitemap.xml` heeft
- **THEN** worden de pagina's daaruit gelezen, tot het ingestelde maximum

#### Scenario: Site zonder sitemap en zonder URL-lijst

- **WHEN** er geen sitemap is en geen URL's zijn opgegeven
- **THEN** meldt de bron dat er niets te lezen valt, en telt hij niet als gelezen bron

#### Scenario: robots.txt sluit een pad uit

- **WHEN** `robots.txt` een pad uitsluit dat in de sitemap staat
- **THEN** wordt dat pad niet opgehaald, en staat het als overgeslagen in de dekking

### Requirement: Beide bronnen zijn read-only

Beide adapters MUST NOT schrijven naar de forge of de website: geen issues, geen commits, geen
pull requests, geen formulierverzendingen.

Rationale: het Source-protocol is read-only en schrijven gaat via een Sink. Een adapter die
onder de motorkap ook schrijft, breekt de belofte waarop de auditor vertrouwt.

#### Scenario: Alleen leesrechten beschikbaar

- **WHEN** het token alleen leesrechten heeft
- **THEN** draait de bron volledig, zonder gedegradeerde modus

### Requirement: Configuratie staat op één plek en is in de UI te bewerken

De live bronconfiguratie MUST in één YAML-bestand op het datavolume staan. De UI MUST dat
bestand kunnen bewerken via de API. Elke wijziging MUST in dezelfde append-only trail terechtkomen
als de bestaande bronconfiguratie.

De repository MUST een sjabloon met commentaar leveren. Dat sjabloon MUST NOT door de run worden
gelezen.

Rationale: twee bewerkbare plekken betekent dat niemand meer weet welke gold. Het sjabloon legt
het formaat vast; het datavolume draagt de waarheid.

#### Scenario: Auditor voegt een repository toe in de UI

- **WHEN** de auditor een repository toevoegt
- **THEN** staat die in het YAML-bestand, staat de wijziging met actor en tijd in de trail, en
  leest de volgende run hem mee

#### Scenario: Sjabloon en live-bestand lopen uiteen

- **WHEN** het sjabloon in de repository andere repositories noemt dan het live-bestand
- **THEN** verandert dat niets aan de run — het sjabloon wordt niet gelezen

### Requirement: Geheimen staan niet in de bronconfiguratie

Tokens voor forge en website MUST via de bestaande instellingen lopen (`config/settings.py`, veld
gemarkeerd als geheim) en MUST NOT in het YAML-bestand staan.

#### Scenario: Token ontbreekt

- **WHEN** er repositories zijn geconfigureerd maar geen token
- **THEN** meldt de bron-health dat expliciet, en draait de run niet met een stil overgeslagen bron

### Requirement: Elke limiet is instelbaar en overschrijding wordt gemeld

Het maximum aantal repositories, pagina's, pull requests en de maximale bestandsgrootte MUST
instelbaar zijn. Overschrijding MUST als melding in de dekking terechtkomen.

Er MUST NOT stil worden afgekapt.

Rationale: de stille afkapping is de fout die dit project het vaakst heeft gemaakt —
MIME-types die zonder melding werden overgeslagen, een afgekapt review-antwoord dat "onleesbaar"
heette, 18 ISO 9001-clausules die nooit werden getoetst. Een hardgecodeerde grens is bovendien
niet te testen.

#### Scenario: Site heeft meer pagina's dan het maximum

- **WHEN** de sitemap 500 pagina's noemt en het maximum staat op 200
- **THEN** worden er 200 gelezen en meldt de dekking dat er 300 niet zijn gelezen, met de reden
