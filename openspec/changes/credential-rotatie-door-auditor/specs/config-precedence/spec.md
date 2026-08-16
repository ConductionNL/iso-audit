# Spec — config-precedence (gewijzigd)

## MODIFIED Requirements

### Requirement: Eén loader met vastgelegde precedence

Er MUST één functie zijn die alle configuratie oplost, met de volgorde
**expliciete overschrijving > environment > `config.yaml` > UI-store > default**. De eerste
bron die een niet-lege waarde levert wint.

Elke opgeloste waarde MUST zijn herkomst meedragen als een van `ui-override`, `env`,
`yaml`, `ui`, `default` of `leeg`. Herkomst is geen logregel achteraf maar een eigenschap
van de waarde zelf, zodat hij niet kan wegvallen tussen oplossen en gebruiken.

Een waarde uit de UI-store MUST NOT boven de omgeving gaan tenzij hij is opgeslagen als
**expliciete overschrijving**; zie de requirement hieronder.

Rationale: environment boven de gewone UI-invoer betekent dat een deployment nooit *stil*
een via-de-UI ingevulde waarde gebruikt. Wat een beheerder expliciet zette, weegt zwaarder
dan wat iemand ooit invulde. Een overschrijving is geen uitzondering op die rationale maar
een bevestiging ervan: hij is niet stil.

#### Scenario: Environment verslaat gewone UI-invoer

- **WHEN** een veld zowel in de omgeving als in de UI-store staat, zonder overschrijving
- **THEN** wint de omgevingswaarde
- **AND** is de herkomst `env`

#### Scenario: Een expliciete overschrijving verslaat de environment

- **WHEN** een veld in de omgeving staat en er een expliciete overschrijving voor bestaat
- **THEN** wint de overschrijving
- **AND** is de herkomst `ui-override`

#### Scenario: UI vult in wat nergens anders staat

- **WHEN** een veld alleen in de UI-store staat
- **THEN** wordt die waarde gebruikt
- **AND** is de herkomst `ui`

#### Scenario: Niets gezet

- **WHEN** een veld in geen enkele bron staat en geen default heeft
- **THEN** is de waarde leeg
- **AND** is de herkomst `leeg`

## ADDED Requirements

### Requirement: Elk configuratieveld is in te vullen, ook met een beheerderswaarde erachter

Het portaal MUST een auditor in staat stellen elk veld uit de catalogus in te vullen, ook
wanneer er een waarde uit de omgeving of `config.yaml` achter zit, zonder tussenkomst van
een clusterbeheerder en **zonder extra bevestigingsstap**.

Een ingevulde waarde MUST vanaf dat moment gelden. Het portaal MUST NOT een schrijfactie
accepteren en vervolgens negeren, en MUST NOT een veld onbewerkbaar maken.

Elke vervanging van een beheerderswaarde MUST append-only worden vastgelegd met
identiteit, tijdstip, de veldnaam en de aantekening dat het een omgevingswaarde vervangt.
Die regel MUST NOT de waarde bevatten.

Een vervanging MUST terug te draaien zijn door het veld leeg te maken, waarna de
omgevingswaarde weer geldt.

Rationale: een credential die verloopt of wordt ingetrokken moet vervangen kunnen worden
door degene die met het tool werkt. Kan dat niet, dan is de auditcapability opnieuw
gebonden aan één persoon met clustertoegang — precies wat deze migratie wegneemt.

De controle is **registratie**, niet moeilijk maken. Er heeft in een tussenversie een
bevestigingsknop omheen gestaan; die is verwijderd. Hij loste een probleem op dat op dat
moment al verholpen was (een opslag-actie die slaagde en genegeerd werd) en voegde een
handeling toe waar niemand om gevraagd had. Dat is dezelfde afweging als in
`api/bron_config.py`: *"Dat registreren is de controle, niet het moeilijk maken van
configureren."*

#### Scenario: Invullen over een beheerderswaarde heen

- **WHEN** een auditor een veld invult dat door een beheerder in de omgeving is gezet
- **THEN** wordt de nieuwe waarde gebruikt door de adapters
- **AND** is de herkomst `ui-override`
- **AND** staat er een regel in het wijzigingsspoor die benoemt welke velden de omgeving
  vervangen
- **AND** was daar geen extra bevestiging voor nodig

### Requirement: Een koppeling is te testen vanuit het configuratiescherm

Het portaal MUST per bron een test bieden die de koppelstatus van **die ene bron** ophaalt
en het resultaat bij het formulier toont.

Na het opslaan van een bron MUST het portaal die test uitvoeren en het resultaat tonen
zonder dat de auditor ergens anders hoeft te kijken.

Rationale: zonder terugkoppeling vult iemand een token in, krijgt "opgeslagen", en weet
nog steeds niet of de koppeling werkt. Per bron en niet over alle bronnen, omdat een
Jira-token invullen niet hoort te wachten op een Drive-listing.

#### Scenario: Testen na opslaan

- **WHEN** een auditor een bron opslaat
- **THEN** verschijnt bij die bron of hij gekoppeld is
- **AND** bij een fout de genormaliseerde reden

#### Scenario: Terug naar de beheerderswaarde

- **WHEN** een auditor de overschrijving verwijdert
- **THEN** geldt de omgevingswaarde weer
- **AND** is de herkomst weer `env`

### Requirement: Een gewijzigde omgeving achter een overschrijving wordt gemeld

Staat er een overschrijving op een veld en heeft de omgeving sindsdien een **andere**
waarde gekregen, dan MUST het portaal dat tonen bij dat veld.

De vergelijking MUST gaan via een vingerafdruk van de waarde; het portaal MUST NOT de
omgevingswaarde of de overschrijving tonen of loggen.

Rationale: dit is het gevaarlijke geval bij rotatie. Een beheerder vervangt het Secret, de
overschrijving zorgt dat die nieuwe waarde niet wordt gebruikt, en zonder signaal zoekt
diegene in het cluster naar een fout die er niet is.

#### Scenario: Beheerder roteert een overschreven credential

- **WHEN** een veld is overschreven
- **AND** de omgevingswaarde daarna wijzigt
- **THEN** meldt het portaal bij dat veld dat de omgeving een andere waarde heeft
- **AND** blijft de overschrijving in gebruik tot iemand hem verwijdert
