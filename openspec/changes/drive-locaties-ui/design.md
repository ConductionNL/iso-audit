# Design — drive-locaties-ui

## Opslag blijft één env-var

`AUDIT_SOURCE_FOLDER_ID` blijft een komma-gescheiden string. De UI bouwt hem op uit de
lijst en haalt hem uit elkaar bij het tonen.

Overwogen en verworpen: een gestructureerd veld (JSON-lijst) in de configuratie. Dat vraagt
een migratie van bestaande waarden, een tweede vorm naast alle andere `Veld`-definities in
`bron_catalogus.py`, en het raakt `BronConfig`, de Secret-opslag én `DriveSource`. De winst
is nul, want de adapter splitst toch al op komma's. Eén opslagvorm die iedereen al kent is
hier de saaie keuze, en de komma is een implementatiedetail zodra de UI hem opbouwt.

Gevolg: `_split_ids`, `_resolve_folder_ids` en `AUDIT_DRIVE_FOLDER_ID` (de legacy-fallback)
blijven ongewijzigd. Deze change raakt `sources/drive.py` alleen voor de statusrapportage.

## Eén veldsoort erbij, geen generieke lijst-editor

`bron_catalogus.Veld` krijgt een soort — `lijst` naast het huidige tekstveld — zodat de
frontend weet dat hij rijen moet renderen. Bewust géén generiek "herhaalbaar veld"-mechaniek
voor alle bronnen: alleen Drive heeft dit nodig, en drie bronnen die het niet gebruiken
mogen niet meebetalen aan de abstractie. Blijkt later dat Jira hetzelfde wil, dan is dat het
moment om te generaliseren — niet nu.

## Naam per locatie kost één extra aanroep

`files.get(fileId, fields="id,name,mimeType,driveId", supportsAllDrives=True)` per locatie.
Voor een Shared Drive-root levert dat de naam van de drive, voor een map de mapnaam.

Dat is één bounded call per locatie, alleen bij het tonen van het configuratiescherm en bij
"Testen" — niet in de pipeline. Bij de huidige praktijk (één tot een handvol locaties) is
dat verwaarloosbaar naast de `files.list` die er al is.

Faalt die `files.get`, dan tonen we het ID zelf met `(onbekend)` erachter en gaat de
statusregel gewoon door. De naam is comfort, geen voorwaarde: een locatie waarvan we de naam
niet kunnen ophalen maar die wel bestanden oplevert, is bruikbaar.

## Onderscheid tussen "leeg" en "geen map"

De Drive-API geeft op `'<bestand-id>' in parents` hetzelfde antwoord als op een echt lege
map: een lege lijst, status 200. Er is geen manier om die twee uit één `files.list` te
onderscheiden.

Met de `mimeType` uit de `files.get` hierboven kan het wél:
`application/vnd.google-apps.folder` is een map, een Shared Drive-root herkennen we aan het
`0A`-prefix zoals nu. Alles daarbuiten is een bestand en krijgt een expliciete melding.

Blijft `files.get` onbeantwoord, dan valt de melding terug op de voorzichtige formulering
("bereikbaar, maar geen bestanden gevonden") zonder de oorzaak te beweren. Liever geen
oorzaak dan een verzonnen oorzaak.

## Status per locatie, niet één samengevatte status

De kaart houdt één bolletje voor de bron als geheel — dat is wat de grey-out in het
landschapsscherm gebruikt en dat contract blijft. Daaronder staat per locatie een eigen
regel.

De bron geldt als gekoppeld zodra **minstens één** locatie bestanden oplevert. Een tweede
locatie die leeg is, maakt de bron niet rood maar krijgt wel een zichtbare waarschuwing.
Anders zou één verkeerd geplakt ID een werkende configuratie als kapot laten ogen, en dat
nodigt uit tot wegklikken.

## Aantallen: bounded, niet exact

De rij toont het aantal bestanden uit een niet-recursieve `files.list`. Een recursieve
telling over een Shared Drive duurt minuten (gemeten: 2,5 minuut voor 409 documenten) en
hoort niet in een scherm dat bij elke pageload opent.

Consequentie die in de UI benoemd moet worden: het getal is wat er direct in de locatie
staat, niet de volledige recursieve inhoud. Een map met alleen submappen toont dan `0` —
daarom is de drempel voor de waarschuwing "geen bestanden én geen submappen", niet
"geen bestanden".
