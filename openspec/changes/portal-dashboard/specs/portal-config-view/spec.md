# Spec — portal-config-view (nieuw)

## ADDED Requirements

### Requirement: Configuratie is een eigen taak, los van triage

Het portaal MUST een apart configuratiescherm hebben dat per bron toont of die
gekoppeld is, en zo niet, wat er ontbreekt. Dat scherm MUST los staan van de
triage-flow.

Rationale: "staan de bronnen goed?" is een andere vraag, op een ander moment, dan
"is deze bevinding valide?".

#### Scenario: Koppelstatus is te zien zonder audit

- **WHEN** een auditor het configuratiescherm opent zonder audit te openen
- **THEN** ziet die per bron de koppelstatus
- **AND** bij een niet-gekoppelde bron wat er ontbreekt

### Requirement: De auditor koppelt bronnen zelf, in de UI

Een auditor MUST bronnen kunnen koppelen en de bron-scope kunnen instellen via het
portaal, zonder tussenkomst van een clusterbeheerder en zonder wijziging aan een
manifest of Secret.

Rationale — en dit corrigeert een eerdere, verkeerde eis in deze spec: een auditor
heeft geen boodschap aan een cluster, en het tool moet aan derden uit te leveren zijn.
Configuratie die alleen via cluster-Secrets kan, maakt het tool onleverbaar en
verplaatst auditwerk naar een beheerder.

De eerdere onderbouwing ("anders kiest een auditor zijn eigen bewijsbasis") berustte
op twee fouten. `sources/base.py` eist immutability **na `__init__`** — een
object-lifecycle-regel, geen autorisatiebeleid over wie mag configureren. En de
dreiging bestaat niet: bewijs bestaat of het bestaat niet. Een auditor kiest bronnen,
die bronnen worden vastgelegd, en een ontbrekende bron valt een laag hoger op — een
interne auditor wordt door een externe gecontroleerd, en die staat onder toezicht.

#### Scenario: Bron koppelen zonder beheerder

- **WHEN** een auditor in het configuratiescherm de gegevens van een bron invult
- **THEN** is die bron daarna gekoppeld volgens de healthcheck
- **AND** was daar geen manifest- of Secret-wijziging voor nodig

#### Scenario: Scope instellen

- **WHEN** een auditor de scope van een bron aanpast (bv. Drive-map of JQL)
- **THEN** gebruikt een volgende run die scope

### Requirement: Wat de auditor configureert wordt vastgelegd, niet bewaakt

Elke wijziging in bron-configuratie MUST append-only vastgelegd worden met de
geverifieerde identiteit en het tijdstip. Elke run MUST blijven vastleggen welke
bronnen geraadpleegd zijn.

Dat vastleggen **is** de controle. Het portaal MUST NOT proberen te voorkomen dat een
auditor bronnen kiest.

#### Scenario: Configuratiewijziging is herleidbaar

- **WHEN** een auditor een bron koppelt of de scope wijzigt
- **THEN** staat die wijziging met identiteit en tijdstip in een append-only log

#### Scenario: Geraadpleegde bronnen blijven in het run-record

- **WHEN** een run draait
- **THEN** vermeldt het run-record welke bronnen zijn geraadpleegd

### Requirement: Configuratie wijzigt niet onder een lopende run

Het portaal MUST een configuratiewijziging weigeren zolang er in die audit een run
loopt.

Rationale: dit is het deel van de immutability-regel dat wél klopt en dat een
technische reden heeft — een Source wordt bij run-start geconfigureerd en leest zijn
config daarna niet opnieuw. Halverwege wisselen levert een run waarvan de helft een
andere scope had. Dat is geen beleid over vertrouwen maar een correctheidseis.

#### Scenario: Wijziging tijdens een run wordt geweigerd

- **WHEN** een auditor de scope wijzigt terwijl er een run loopt
- **THEN** wordt de wijziging geweigerd met een leesbare melding
- **AND** blijft de lopende run op zijn oorspronkelijke scope draaien

### Requirement: Credentials zijn schrijfbaar maar niet uitleesbaar

Het portaal MAY credentials ontvangen en opslaan. Het MUST NOT een opgeslagen
credential terug tonen of via de API teruggeven; het scherm MUST volstaan met
"ingesteld" of "niet ingesteld".

Rationale: invoeren moet kunnen, want anders is het tool niet leverbaar. Teruglezen
hoeft nooit, en een credential die niet uitleesbaar is kan ook niet uit het portaal
lekken.

#### Scenario: Credential wordt niet teruggegeven

- **WHEN** een credential is ingesteld en het configuratiescherm wordt opgevraagd
- **THEN** meldt de API dat het is ingesteld
- **AND** bevat het antwoord de waarde niet

### Requirement: De koppelstatus komt uit één bron van waarheid

Het configuratiescherm MUST de bestaande per-bron healthcheck gebruiken. Er MUST NOT
een tweede, eigen koppel-administratie naast bestaan.

Rationale: twee plekken die zeggen of een bron werkt, lopen uiteen. De healthcheck
bevraagt het echte systeem; een opgeslagen vlaggetje vertelt wat iemand ooit dacht.

#### Scenario: Scherm en run zijn het eens

- **WHEN** het scherm een bron als gekoppeld toont
- **THEN** gebruikt een run diezelfde configuratie zonder een aparte controle
