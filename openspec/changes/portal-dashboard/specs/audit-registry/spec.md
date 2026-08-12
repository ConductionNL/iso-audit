# Spec — audit-registry (nieuw)

## ADDED Requirements

### Requirement: Een audit is een eerste-klas object met een manifest

Het portaal MUST audits kennen als losse objecten, elk met een eigen directory en een
`audit.json`-manifest met norm, periode, aanmaakmoment en de identiteit van wie hem
aanmaakte. De identiteit MUST de geverifieerde identiteit uit de auth-gate zijn.

Het audit-id MUST afgeleid worden van norm en periode. Bestaat het id al, dan MUST de
aanmaakactie falen met een leesbare fout; er MUST NOT een suffix bijverzonnen worden.

Rationale: twee audits met dezelfde norm én periode is bijna altijd een vergissing,
en stil `-2` erachter zetten maakt van die vergissing een blijvende dubbele
administratie.

#### Scenario: Audit aanmaken

- **WHEN** een auditor een audit aanmaakt met norm en periode
- **THEN** bestaat er een audit-directory met een manifest
- **AND** vermeldt het manifest de identiteit van de aanmaker

#### Scenario: Dubbel id wordt geweigerd

- **WHEN** een audit wordt aangemaakt met een norm en periode die al bestaan
- **THEN** faalt de actie met een leesbare fout
- **AND** wordt de bestaande audit niet gewijzigd

### Requirement: Runs worden append-only geregistreerd

Elke pipeline-run binnen een audit MUST een regel toevoegen aan een append-only
`runs.jsonl` in die audit, met minimaal: run-id, starttijd, de geverifieerde
identiteit, modus, norm, geraadpleegde bronnen, en het aantal toegevoegde
kandidaten. Bestaande regels MUST NOT gewijzigd of verwijderd worden.

Een run die faalt MUST ook geregistreerd worden, met zijn fout.

Rationale: een mislukte run is auditinformatie. Weglaten maakt het overzicht
schoner en het dossier onvolledig.

#### Scenario: Run laat een spoor

- **WHEN** een run wordt gestart en afgerond
- **THEN** staat er een regel in `runs.jsonl` met identiteit, bronnen en aantal kandidaten

#### Scenario: Mislukte run blijft zichtbaar

- **WHEN** een run faalt
- **THEN** staat de run met zijn fout in `runs.jsonl`

### Requirement: Een volgende run vult aan en gooit geen triage weg

Een tweede of latere run binnen dezelfde audit MUST nieuwe kandidaten toevoegen aan
de bestaande werkset. Reeds getrieerde bevindingen MUST hun `triage_status` en hun
plaats in de trail behouden. Een run MUST NOT bestaande bevindingen wijzigen of
verwijderen.

#### Scenario: Bron erbij zetten behoudt eerder werk

- **GIVEN** een audit waarin al getrieerd is op basis van Drive
- **WHEN** een tweede run met Jira erbij draait
- **THEN** zijn de nieuwe Jira-kandidaten toegevoegd
- **AND** hebben de eerder getrieerde bevindingen hun status behouden

### Requirement: Deduplicatie is deterministisch en overgeslagen duplicaten zijn zichtbaar

Deduplicatie tussen runs MUST deterministisch in code gebeuren, op de sleutel
norm + clausule + bron + genormaliseerde titel. Er MUST NOT een LLM of een
niet-uitlegbare gelijkenis-drempel aan te pas komen.

Overgeslagen duplicaten MUST geregistreerd worden bij het run-record, met hun aantal.
Ze MUST NOT stil verdwijnen.

Rationale: dezelfde discipline als het `dropped`-spoor bij curate. Een auditor moet
kunnen zien dat een run dertig kandidaten opleverde waarvan achttien al bekend waren
— anders lijkt de run niets te hebben gedaan.

#### Scenario: Duplicaat wordt overgeslagen en geteld

- **WHEN** een run een kandidaat oplevert die op de dedup-sleutel al bestaat
- **THEN** wordt hij niet toegevoegd
- **AND** staat hij geteld bij het run-record

#### Scenario: Dedup is reproduceerbaar

- **WHEN** dezelfde run twee keer op dezelfde werkset draait
- **THEN** is de uitkomst identiek

### Requirement: Eén schrijver per audit, zichtbaar gemaakt in plaats van vergrendeld

Het portaal MUST bijhouden wie als laatste een mutatie deed in een audit, en MUST
zichtbaar waarschuwen wanneer een andere identiteit recent actief was in dezelfde
audit. Het portaal MUST NOT gelijktijdige toegang blokkeren met een slot.

**Bewuste risico-acceptatie:** twee auditors kunnen dezelfde bevinding triëren, en de
uitkomst in de werkset is dan de laatste schrijver. Beide beslissingen blijven in de
append-only trail staan, dus het is herleidbaar. Een slot is afgewezen omdat een
blijven-hangen slot een audit onbruikbaar maakt en dat een grotere faalmodus is dan
het probleem dat het oplost.

#### Scenario: Andere auditor is actief

- **WHEN** een auditor een audit opent waarin een andere identiteit recent muteerde
- **THEN** toont de UI een zichtbare waarschuwing met wie dat was
- **AND** blijft de audit bewerkbaar
