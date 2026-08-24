# Spec — clausule-per-norm (nieuw)

## ADDED Requirements

### Requirement: Een clausule wordt geïdentificeerd door norm én nummer

Elke verwijzing naar een clausule MUST de norm meedragen. Een clausulenummer alleen MUST NOT
volstaan als sleutel in opslag, koppeling, classificatie of werkset.

Rationale: achttien nummers bestaan in beide normen. Zolang het nummer de sleutel is, is §5.1
dubbelzinnig, en elke laag die dat probeert op te lossen doet het met een gok.

#### Scenario: Hetzelfde nummer in beide normen

- **WHEN** een document zowel ISO 9001 §7.5 als ISO 27001 §7.5 raakt
- **THEN** levert dat twee koppelingen op, elk met hun eigen norm, en twee te onderscheiden
  bevindingen

### Requirement: Een gecombineerde audit toetst beide normen volledig

Een run over `beide` MUST elke clausule van elke gekozen norm toetsen.

De clause-maps MUST NOT worden samengevoegd op een manier waarbij een ingang van de ene norm die
van de andere overschrijft.

Rationale: `{**map_9001, **map_27001}` liet 27001 winnen bij een botsing, waardoor 18 van de 28
ISO 9001-clausules — leiderschap, beleid, rollen, risico's, doelstellingen, middelen,
competentie, communicatie, gedocumenteerde informatie, operationele planning, klanteisen,
ontwerp, uitbesteding, productie, vrijgave en afwijkende output — in een gecombineerde audit
nooit werden getoetst. De samengevoegde map had 103 ingangen waar er 121 horen.

#### Scenario: Dekkingstelling van een gecombineerde run

- **WHEN** een run over beide normen draait
- **THEN** zijn alle 121 clausules kandidaat voor koppeling, en meldt de dekking dat aantal

#### Scenario: Een 9001-clausule met een botsend nummer

- **WHEN** een document ISO 9001 §8.4 (beheersing van extern geleverde processen) raakt
- **THEN** wordt dat als 9001 §8.4 gekoppeld en niet als 27001 §8.4 (scheiding van omgevingen)

### Requirement: De opslag kan twee normen op hetzelfde document en nummer bewaren

De primaire sleutel van `clause_matches` MUST de norm bevatten.

Rationale: de sleutel is nu `(doc_id, herkomst, clausule_id, sub_punt)`. Zelfs met een correcte
koppeling per norm zou de tweede match op hetzelfde nummer door `INSERT OR IGNORE` stil worden
weggegooid — een verlies zonder foutmelding.

#### Scenario: Migratie van een bestaande database

- **WHEN** de migratie draait op een database met bestaande koppelingen
- **THEN** blijven die koppelingen bestaan, met de norm die erbij is vastgelegd, en gaat er geen
  rij verloren

### Requirement: De norm van een bevinding wordt vastgelegd, niet afgeleid

`bevindingen.norm` MUST de norm van de match bevatten (`9001` of `27001`) en MUST NOT `beide`
zijn.

Het achteraf afleiden van de norm uit clausule-lidmaatschap MUST verdwijnen.

Rationale: `run_job._resolve_standard()` moest raden omdat de match zijn norm niet had bewaard.
Met een half gevulde norm-DB raadde hij 448 van de 903 bevindingen verkeerd — clausule 8.24
(cryptografie, Annex A van 27001) stond als ISO 9001:2015 in de werkset. Een afleiding die van
een tweede administratie afhangt, is fout zodra die administratie achterloopt.

#### Scenario: Bevinding op een uniek nummer

- **WHEN** een bevinding op 27001 §8.24 wordt vastgelegd
- **THEN** staat `27001` in de rij, ongeacht wat een norm-DB zegt

### Requirement: De classificatie krijgt de normtekst van de juiste norm

Het model MUST de normtekst, interpretatie en bewijslast van de norm van de match krijgen.

Rationale: bij een botsend nummer kreeg het model de tekst van de norm die de merge won. Een
document werd dan beoordeeld tegen "Beveiligd ontwikkelen" terwijl §7.5 in de audit
"Gedocumenteerde informatie" is. Dat is geen dekkingsgat maar een verkeerd oordeel, en aan de
uitkomst niet te zien.

#### Scenario: Classificatie op een botsend nummer

- **WHEN** een document tegen 9001 §7.5 wordt geclassificeerd
- **THEN** bevat de prompt de 9001-tekst van §7.5 en niet die van 27001

### Requirement: Bevinding-id's botsen niet tussen normen

Het id van een bevinding MUST uniek zijn over normen heen.

Rationale: `nc-<clausule>` botst zodra beide normen hetzelfde nummer opleveren. Een dubbel id
maakte op 2026-08-24 al een bevinding ontriageerbaar: `apply_triage` zoekt met `next(...)` en
muteerde altijd de eerste.

#### Scenario: Twee bevindingen op §5.1

- **WHEN** zowel 9001 §5.1 als 27001 §5.1 een bevinding oplevert
- **THEN** hebben die twee verschillende id's, en is elk apart te triageren
