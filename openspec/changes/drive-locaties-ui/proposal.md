# Drive-locaties als lijst in de UI, met eerlijke status per locatie

## Waarom

### 1. De mogelijkheid bestaat, maar is onvindbaar

`DriveSource` leest al uit meerdere locaties: `_split_ids` splitst een komma-gescheiden
waarde, elk ID dat met `0A` begint wordt als Shared Drive behandeld, en `list_documents`
dedupliceert op file-id zodat overlappende scopes geen dubbelingen geven.

In het configuratiescherm is daar niets van te zien. Het veld heet "Map-ID van de auditmap",
enkelvoud, met de hint "Het laatste deel van de Drive-URL van de map". Niemand raadt dat
daar een komma in mag. Een auditor die twee Drives wil koppelen concludeert dat het niet kan.

Komma-gescheiden invoer is bovendien de verkeerde vorm voor deze gebruiker. Het is een
opslagformaat dat naar de UI is gelekt: je moet zelf scheidingstekens plaatsen, je ziet niet
waar de ene locatie ophoudt en de volgende begint, en één typefout maakt stilletjes twee
onbruikbare ID's van één goede.

### 2. Een niet-map meldt zich groen

`probe()` roept `drive_bereikbaar()` aan, en die doet één `files.list` met `pageSize=1` en
kijkt alléén of de aanroep slaagt. De query is `'<id>' in parents`. Vul je een bestand-ID in
plaats van een map-ID in, dan matcht die query niets — geen fout, een lege lijst. De probe
slaagt, de UI meldt **gekoppeld**, en elke run leest vervolgens stil nul documenten uit die
locatie.

Dat is dezelfde vorm als de hardcoded planning-sheet die op 2026-08-16 is weggehaald: groen
melden op een scope die niets oplevert. Voor een audittool is dat het ergste geval, want de
auditor concludeert dat de bron gedekt is.

Gemeten op 2026-08-17 in het cluster: `AUDIT_SOURCE_FOLDER_ID=0AAPHjn2R39GWUk9PVA` levert
`● gekoppeld — 1 map(pen)`, zonder dat ergens blijkt wélke map dat is of wat erin zit.

## Wat er verandert

Het Drive-formulier wordt een **lijst van gekoppelde locaties**. Per locatie: de naam zoals
Drive die kent, of het een Shared Drive of een gewone map is, en een status die zegt wat er
werkelijk bereikbaar is. Toevoegen gaat met één veld waarin een URL of ID mag; verwijderen
met een knop per rij. De auditor typt nooit een komma.

Een locatie die bereikbaar is maar niets oplevert, meldt dat als waarschuwing met de
waarschijnlijke oorzaak ("is dit wel een map?") in plaats van als groen.

## Wat er niet verandert

**Losse bestanden worden niet ondersteund.** Dat zou een tweede leespad vragen (`files.get`
naast `'<id>' in parents`) plus onderscheid in de configuratie tussen map en bestand.
Expliciet buiten scope; de waarschuwing hierboven maakt zichtbaar wanneer iemand het tóch
probeert, in plaats van het stil te laten mislukken.

**Het opslagformaat blijft één env-var**, komma-gescheiden. Geen migratie, geen tweede
configuratiepad, en `DriveSource` hoeft niet te wijzigen. De komma wordt een
implementatiedetail dat de UI opbouwt en uit elkaar haalt — precies waar het thuishoort.

## Capability-impact

Versterkt **onafhankelijke bronnen**: meerdere Drives koppelen is de praktijksituatie
(organisatiedrive plus een projectdrive), en die was tot nu toe onbereikbaar via de UI.

Versterkt de **auditor-spiegel**: de auditor ziet wélke locaties in scope zijn en of daar
werkelijk iets in zit. Een dekkingsclaim die niet klopt is erger dan een zichtbaar gat, en
de huidige groene melding op een lege locatie is precies zo'n claim.

Raakt **patroondetectie** niet.
