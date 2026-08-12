# Spec — portal-config-view (nieuw)

## ADDED Requirements

### Requirement: Configuratie is een eigen taak, los van triage

Het portaal MUST een apart configuratiescherm hebben dat per bron toont of die
gekoppeld is, en zo niet, wat er ontbreekt. Dat scherm MUST los staan van de
triage-flow.

Rationale: "staan de bronnen goed?" is een andere vraag, op een ander moment, dan
"is deze bevinding valide?". Ze in één scherm proppen betekent dat de auditor
configuratie tegenkomt terwijl hij audit, en dat is precies het moment waarop hij er
niet aan moet zitten.

#### Scenario: Ontbrekende koppeling is te zien zonder audit

- **WHEN** een auditor het configuratiescherm opent zonder audit te openen
- **THEN** ziet die per bron de koppelstatus
- **AND** bij een niet-gekoppelde bron welke env-var of Secret-key ontbreekt

### Requirement: Het configuratiescherm is alleen-lezend

Het configuratiescherm MUST NOT bron-configuratie of credentials kunnen wijzigen.
Wijzigen MUST via cluster-Secrets en het deployment-manifest gaan.

Rationale: `sources/base.py` schrijft voor dat een Source zijn configuratie immutable
houdt na `__init__`, als directe vertaling van missie-capability 1 — *"toegang van
tevoren ingericht en daarna onveranderlijk binnen een auditperiode"*. Een auditor die
de Drive-map of de JQL kan verzetten terwijl hij audit, kan zijn eigen bewijsbasis
kiezen. Dat moet het tool onmogelijk maken, niet vergemakkelijken.

De praktische pijn is echt — een bron koppelen vraagt een beheerder. Het antwoord
daarop is een duidelijke foutmelding en een scherm dat precies zegt wat ontbreekt,
niet het weghalen van de garantie die het tool zijn waarde geeft.

#### Scenario: Geen schrijfroute naar bron-configuratie

- **WHEN** het configuratiescherm en zijn API worden bekeken
- **THEN** bestaat er geen endpoint dat bron-configuratie of credentials wijzigt

#### Scenario: Ontbrekende credential blijft een harde fout bij gebruik

- **WHEN** een run start met een bron die niet gekoppeld is
- **THEN** faalt dat met een leesbare fout
- **AND** wordt er geen lege of verzonnen findings-set geproduceerd

### Requirement: De koppelstatus komt uit één bron van waarheid

Het configuratiescherm MUST de bestaande per-bron healthcheck gebruiken. Er MUST NOT
een tweede, eigen koppel-administratie naast bestaan.

Rationale: twee plekken die zeggen of een bron werkt, lopen uiteen. De healthcheck
bevraagt het echte systeem; een opgeslagen vlaggetje vertelt wat iemand ooit dacht.

#### Scenario: Scherm en run zijn het eens

- **WHEN** het scherm een bron als gekoppeld toont
- **THEN** gebruikt een run diezelfde configuratie zonder een aparte controle
