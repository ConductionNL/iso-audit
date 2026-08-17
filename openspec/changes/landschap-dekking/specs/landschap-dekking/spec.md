# Spec — landschap-dekking (nieuw)

## ADDED Requirements

### Requirement: Wat niet gelezen wordt, wordt gemeld

Elk bestand dat niet als document in het landschap belandt MUST in een melding terechtkomen,
met de reden en op een niveau dat de auditor ziet.

Er MUST NOT een categorie zijn die stil wordt overgeslagen.

Rationale: gemeten op 2026-08-17 verdwenen 92 van de 512 bestanden via
`logger.debug("Skip (onbekend MIME)")` — 29 snelkoppelingen, 44 spreadsheets, 6 forms, en zes
bestanden die pure tekst zijn. Ze zaten niet in het aantal van 119 dat als "handmatige review"
werd gemeld, en op INFO-niveau was er geen enkele regel. Het tool liet ze liggen zonder dat
te zeggen.

#### Scenario: Bestandstype dat niet gelezen kan worden

- **WHEN** een bestand een type heeft dat de adapter niet leest
- **THEN** staat dat in een melding met de reden
- **AND** telt het mee in de dekking van de run

#### Scenario: Onbekend type

- **WHEN** een bestandstype in geen enkele lijst voorkomt
- **THEN** wordt het gemeld als onbekend en niet stil overgeslagen

### Requirement: De dekking staat in het run-record

Het run-record MUST per run vastleggen hoeveel bestanden zijn gezien, hoeveel er als document
zijn opgenomen, en per reden hoeveel er zijn overgeslagen.

Het MUST NOT een lijst van bestandsnamen bevatten.

Rationale: een auditor die 299 documenten ziet, ziet niet dat er 213 buiten stonden. "Welk
deel van de bron heeft het tool gezien" is precies wat een certificerende instantie vraagt, en
dat antwoord staat nu alleen in een logregel die een podherstart niet overleeft — dezelfde
reden waarom de kosten op 2026-08-17 van het log naar het run-record zijn verhuisd. Namen per
bestand horen er niet in: 213 namen per record maakt de trail onleesbaar, en ze staan al in
het handmatige-review-spoor.

#### Scenario: Run over een bron met onleesbare bestanden

- **WHEN** een ingest-run bestanden tegenkomt die niet gelezen kunnen worden
- **THEN** staat in het run-record hoeveel er gezien, gelezen en per reden overgeslagen zijn

### Requirement: Een leeg extractieresultaat is geen leeg document

Levert een bestand dat wél gelezen kon worden nul tekst op, dan MUST dat als onleesbaar worden
gemeld en MUST NOT als document met lege inhoud in het landschap komen.

Rationale: een gescande PDF levert nul tekens op. Als document opgenomen classificeert de
pipeline hem als "geen bewijs" — een oordeel over iets wat niemand heeft gelezen, op een
clausule waar het bewijs gewoon bestaat. Dezelfde regel als bij de classificatie, waar een
afgekapt antwoord sinds 2026-08-17 ook geen leeg oordeel meer is.

#### Scenario: Gescande PDF

- **WHEN** de tekstextractie van een bestand nul tekens oplevert
- **THEN** komt het niet als document in het landschap
- **AND** wordt het gemeld als onleesbaar met de vermoedelijke reden

### Requirement: Snelkoppelingen worden gevolgd en één keer geteld

Een Drive-snelkoppeling MUST worden gevolgd naar het doelbestand, dat vervolgens dezelfde
behandeling krijgt als elk ander bestand.

Een doel dat ook rechtstreeks in scope zit MUST NOT twee keer als document meetellen.

Rationale: 29 snelkoppelingen werden overgeslagen. Ze wijzen naar echte documenten, mogelijk
precies het bewijs dat de auditor bedoelde binnen te halen — en ze maken de voor de hand
liggende workaround, een map met snelkoppelingen naar de relevante stukken, stil onbruikbaar.

#### Scenario: Snelkoppeling naar een leesbaar document

- **WHEN** een gekoppelde locatie een snelkoppeling bevat
- **THEN** wordt het doelbestand gelezen

#### Scenario: Snelkoppeling naar een document dat al in scope zit

- **WHEN** het doel ook rechtstreeks in een gekoppelde locatie staat
- **THEN** telt het één keer mee

### Requirement: Tekstformaten worden gelezen als tekst

Bestanden die pure tekst zijn MUST worden gelezen, ongeacht of hun MIME-type toevallig in de
lijst stond.

Rationale: `text/markdown`, `text/html` en `text/csv` werden overgeslagen terwijl `text/plain`
wel werd gelezen. Daar zat `Auditrapport_beide_v3.3_2026-05-05.md` bij — een auditrapport dat
buiten het landschap bleef omdat het een andere tekst-MIME had.

#### Scenario: Markdown-document in de auditmap

- **WHEN** een gekoppelde locatie een markdown-, HTML- of CSV-bestand bevat
- **THEN** komt de tekst in het landschap
