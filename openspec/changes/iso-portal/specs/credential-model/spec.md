# Spec — credential-model (nieuw)

## ADDED Requirements

### Requirement: Geen credential is persoonsgebonden

Elk credential waarmee de tool een extern systeem bevraagt MUST toebehoren aan
een organisatie-account: een Workspace service account, een functioneel
gebruikersaccount, een org-owned API-token of een org-owned app-registratie.

Een credential dat gebonden is aan een natuurlijk persoon — een persoonlijke
OAuth-sessie, een API-token op een persoonlijk account, een persoonlijke
subscription-token — MUST NOT gebruikt worden in het portaal.

Rationale: het vertrek van één medewerker mag de auditcapability niet stoppen, en
in een ISO 27001-audit moet toegang aan een rol hangen.

#### Scenario: Portaalrun gebruikt geen persoonlijk credential

- **WHEN** het portaal een bron bevraagt
- **THEN** gebeurt dat op een organisatie-account
- **AND** is er geen persoonlijke OAuth-sessie of persoonlijk token in de omgeving nodig

#### Scenario: Persoonlijk credential wordt bij migratie ingetrokken

- **WHEN** een bron naar een org-credential is gemigreerd
- **THEN** is het persoonlijke credential voor die bron ingetrokken
- **AND** staat in `CHANGELOG.md` welk credential is ingetrokken en op welke datum

### Requirement: Credentials staan buiten Git, in één mechanisme

Credentials MUST als cluster-Secret in de portaal-namespace bestaan, out-of-band
aangemaakt. Een credential-waarde MUST NOT in de repository voorkomen — ook niet
versleuteld, tenzij via het één gekozen mechanisme.

Er MUST precies één mechanisme voor versleutelde-in-Git-opslag gekozen worden
(SOPS/age óf External Secrets); beide naast elkaar MUST NOT.

#### Scenario: Repo bevat geen credential-waarden

- **WHEN** de repo op secrets gescand wordt
- **THEN** worden alleen placeholders en env-var-namen gevonden

### Requirement: Eigenaarschap is een rol, niet een persoon

Elk credential MUST een gedocumenteerde eigenaar hebben, uitgedrukt als
functioneel account of rol. Een natuurlijke persoon MUST NOT als enige eigenaar
vastgelegd worden.

#### Scenario: Eigenaar is uit de documentatie af te lezen

- **WHEN** een auditor vraagt wie verantwoordelijk is voor een credential
- **THEN** wijst de documentatie een rol of functioneel account aan
- **AND** is die vermelding niet afhankelijk van wie de change heeft geschreven

### Requirement: De koppeling credential → systeem → eigenaar is herleidbaar

De repo MUST één tabel bevatten die per credential vastlegt: het externe systeem,
de Secret-naam, het organisatie-account, de eigenaar-rol en het rotatiemoment.

Rationale: dit is de vraag die een auditor stelt. Een verspreide verzameling
env-var-namen is geen antwoord.

#### Scenario: Rotatie is planbaar

- **WHEN** een credential aan rotatie toe is
- **THEN** blijkt uit de tabel welk Secret, welk account en welke rol daarvoor nodig zijn

### Requirement: Bronnen zonder passende MCP zijn een vastgelegde uitzondering

Voor elke bron MUST vastliggen of een MCP-server functioneel dekkend is en, zo
niet, waarom niet. Een bron die op een eigen adapter blijft draaien MUST als
bewuste uitzondering met reden gedocumenteerd zijn.

Een stille custom-adapter — een bron die op eigen code blijft zonder dat de
afweging is opgeschreven — MUST NOT bestaan.

Rationale: "we hebben geen MCP gebruikt" is een besluit dat verantwoord moet
worden, geen omissie die stil mag blijven.

#### Scenario: Elke bron heeft een MCP-besluit

- **WHEN** de migratiedocumentatie per bron gelezen wordt
- **THEN** staat er per bron of een MCP passend is
- **AND** staat bij een negatief besluit de reden erbij (functieverlies, geen server beschikbaar, of geen code-winst)

#### Scenario: Per-gebruiker-OAuth telt niet als org-owned

- **WHEN** een MCP-server alleen per-gebruiker-OAuth ondersteunt
- **THEN** geldt hij niet als org-owned alternatief
- **AND** wordt hij niet ingezet als vervanging van een persoonlijk credential

### Requirement: Machine-credentials hebben een maximale leeftijd en zijn los intrekbaar

Elk machine-credential MUST een vastgelegde maximale leeftijd hebben, ook wanneer
het technisch niet verloopt. Elk credential MUST onafhankelijk van de andere
credentials intrekbaar zijn.

Rationale: een Google-service-account-keyfile verloopt niet uit zichzelf. Zonder
een vastgelegd plafond is "rotatiemoment" in de tabel een intentie zonder
vervaldatum. Losse intrekbaarheid zorgt dat één gecompromitteerde bron niet de
hele auditcapability plat legt.

#### Scenario: Maximale leeftijd is vastgelegd

- **WHEN** de herleidbaarheidstabel gelezen wordt
- **THEN** heeft elk machine-credential een maximale leeftijd, ook de niet-verlopende

#### Scenario: Eén credential intrekken raakt de andere niet

- **WHEN** één bron-credential ingetrokken wordt
- **THEN** blijven de overige bronnen werken
- **AND** meldt de bron-healthcheck de ingetrokken bron als niet-gekoppeld

### Requirement: Na migratie is vastgesteld welke trust-paths resteren

Na elke bron-migratie MUST vastgesteld en vastgelegd zijn welke toegangspaden
overleven: lokale artefacten op het werkstation van de vertrekkende beheerder
(`.env`, lokale audit-databases, credential-caches) en resterende
repository-toegang na de eigendomsoverdracht.

Rationale: credential-rotatie is containment, niet eradicatie. Een repo-transfer
verwijdert een collaborator niet, en een ingetrokken token laat een lokale
werkkopie met echte auditdata onaangetast. Wat niet is vastgesteld, is niet weg.

#### Scenario: Lokale artefacten zijn verantwoord

- **WHEN** een bron-migratie afgerond is
- **THEN** is vastgelegd welke lokale credential- en databestanden resteerden
- **AND** wat daarmee gebeurd is

#### Scenario: Repository-toegang is herzien na overdracht

- **WHEN** de eigendom van de repository is overgedragen
- **THEN** is de resterende toegang van de vorige eigenaar expliciet herzien
