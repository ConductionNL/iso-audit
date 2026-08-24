# Spec — incrementele-ingest (nieuw)

## ADDED Requirements

### Requirement: Een ongewijzigd document wordt niet opnieuw opgehaald

De ingest MUST de inhoud van een document overslaan wanneer de wijzigingstijd van de bron gelijk
is aan de opgeslagen `documents.modified_at` en er al tekst is opgeslagen.

De listing MUST NOT worden overgeslagen.

Rationale: gemeten op 2026-08-24 kost Drive 2,49 s per document aan inhoud tegen 65 s eenmalig
voor de hele lijst — 1.202 s van de 16 minuten die een herhaalde run duurt. De listing is
bovendien de enige manier om te merken dat een document is verdwenen of bijgekomen.

#### Scenario: Niets veranderd sinds de vorige run

- **WHEN** alle documenten dezelfde wijzigingstijd hebben als in de vorige run
- **THEN** wordt er geen enkele inhoud opgehaald, en levert de run dezelfde bevindingen op

#### Scenario: Eén document gewijzigd

- **WHEN** één document een nieuwere wijzigingstijd heeft
- **THEN** wordt alleen dat document opnieuw opgehaald en opnieuw geclassificeerd

#### Scenario: Document verdwenen uit de bron

- **WHEN** een eerder gelezen document niet meer in de listing staat
- **THEN** wordt dat gemeld — de listing draait immers wel

### Requirement: Een overgeslagen document telt gewoon mee in de dekking

Een overgeslagen document MUST als gezien én gelezen tellen, met de vermelding dat de tekst uit
een eerdere run komt.

Rationale: een dekking die daalt omdat er niets veranderd is, is een verkeerd antwoord op de
vraag "wat heeft dit tool gezien". Dat is dezelfde stille afwijking als de MIME-types die tot
2026-08-18 zonder melding werden overgeslagen.

#### Scenario: Dekkingsmelding na een incrementele run

- **WHEN** 700 van de 709 documenten zijn overgeslagen
- **THEN** meldt de dekking 709 gezien en 709 gelezen, met de aantekening dat 700 uit de vorige
  run komen

### Requirement: Alles opnieuw lezen moet kunnen

Er MUST een expliciete schakelaar zijn die de opgeslagen tekst negeert en elk document opnieuw
ophaalt.

Rationale: na een wijziging in de lezers is de opgeslagen tekst verouderd zonder dat de
wijzigingstijd van de bron verandert. Op 2026-08-24 werden 32 OpenDocument-bestanden voor het
eerst leesbaar; met alleen een tijdstempel-vergelijking zouden die als "ongewijzigd" zijn
overgeslagen en nooit binnengekomen. Een cache zonder uitweg is een val.

#### Scenario: Nieuwe lezer, ongewijzigde bestanden

- **WHEN** de lezers zijn uitgebreid en de auditor draait met `--opnieuw-lezen`
- **THEN** wordt elk document opnieuw opgehaald, ongeacht de wijzigingstijd

### Requirement: Een bron zonder wijzigingstijd wordt volledig gelezen

Wanneer een bron geen wijzigingstijd levert, MUST elk document van die bron opnieuw worden
gelezen.

Er MUST NOT een wijzigingstijd worden verzonnen of afgeleid.

Rationale: Planning levert rijen uit een sheet zonder tijdstempel (150 van de 709 in de meting).
Een geraden tijd zou een document als ongewijzigd markeren terwijl niemand dat weet — een stille
aanname op de plek waar het tool juist zijn dekking verantwoordt.

#### Scenario: Planning naast Drive

- **WHEN** een run beide bronnen leest
- **THEN** worden de Drive-documenten incrementeel gelezen en de Planning-rijen volledig
