# Spec — config-precedence (nieuw)

## ADDED Requirements

### Requirement: Eén loader met vastgelegde precedence

Er MUST één functie zijn die alle configuratie oplost, met de volgorde
**environment > `config.yaml` > UI-store > default**. De eerste bron die een niet-lege
waarde levert wint.

Elke opgeloste waarde MUST zijn herkomst meedragen als een van `env`, `yaml`, `ui`,
`default` of `leeg`. Herkomst is geen logregel achteraf maar een eigenschap van de waarde
zelf, zodat hij niet kan wegvallen tussen oplossen en gebruiken.

Rationale: environment bovenaan betekent dat een deployment nooit stil een via-de-UI
ingevulde waarde gebruikt. Wat een beheerder expliciet zette, weegt zwaarder.

#### Scenario: Environment verslaat de UI

- **WHEN** een veld zowel in de omgeving als in de UI-store staat
- **THEN** wint de omgevingswaarde
- **AND** is de herkomst `env`

#### Scenario: UI vult in wat nergens anders staat

- **WHEN** een veld alleen in de UI-store staat
- **THEN** wordt die waarde gebruikt
- **AND** is de herkomst `ui`

#### Scenario: Niets gezet

- **WHEN** een veld in geen enkele bron staat en geen default heeft
- **THEN** is de waarde leeg
- **AND** is de herkomst `leeg`

### Requirement: Herkomst is opvraagbaar en wordt vastgelegd

Het portaal MUST bij het starten per veld één regel in de audit-log schrijven met de
veldnaam, de herkomst en of het veld is ingesteld. Die regel MUST NOT de waarde bevatten.

De herkomst MUST ook via de API opvraagbaar zijn, zodat een auditor kan zien waar zijn
configuratie vandaan komt zonder in een cluster te kijken.

#### Scenario: Herkomst opvragen

- **WHEN** een auditor de herkomst opvraagt
- **THEN** krijgt hij per veld de bron en of het is ingesteld
- **AND** bevat het antwoord geen enkele geheime waarde

### Requirement: Geheime waarden komen er nooit uit

Een geheim veld MUST NOT zijn waarde teruggeven via de API, in een logregel, of in de
tekstweergave van het object waarin het zit. De tekstweergave MUST de herkomst tonen en de
waarde vervangen door een vaste aanduiding.

Waar de UI een bestaande geheime waarde toont, MUST dat een maskering zijn die de lengte
niet verraadt.

Rationale: een waarde die niet uit te lezen is, kan ook niet lekken via een stacktrace,
een f-string of een foutmelding. Dit is een structurele bescherming, geen discipline.

#### Scenario: Geheim in een stacktrace

- **WHEN** een object met een geheim veld in een foutmelding belandt
- **THEN** staat de waarde er niet in
- **AND** staat de herkomst er wel in

#### Scenario: Secret in config.yaml

- **WHEN** een geheim veld in `config.yaml` staat
- **THEN** wordt de waarde gebruikt
- **AND** wordt gewaarschuwd dat dit niet de aangeraden plek is

### Requirement: Schema-versie is traceerbaar

De configuratie MUST een expliciete schema-versie dragen, zodat een latere migratie
herleidbaar is en een oud bestand niet stil verkeerd gelezen wordt.

#### Scenario: Onbekende schema-versie

- **WHEN** een configuratiebestand een hogere schema-versie draagt dan de code kent
- **THEN** wordt dat gemeld in de log
- **AND** start het portaal alsnog, zodat configuratie zichtbaar blijft
