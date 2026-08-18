---
status: draft
last_reviewed: 2026-08-18
---

# Source: Drive

> **Status:** spec klaar; implementatie in milestone B (verhuisd uit
> `Ops_to_Biz/audit/drive_ingest.py` + `gws_client.py`).

Google Drive als bron voor ISO-bewijsmateriaal. Read-only access via een
Google Workspace service-account met domain-wide delegation.

## Configuratie

| Env-var | Verplicht | Beschrijving |
|---|---|---|
| `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE` | ja | Pad naar de service-account JSON-key. Deployment-breed; niet in de UI. |
| `GWS_IMPERSONATE_EMAIL` | **nee** | Namens welke *gebruiker* het account leest. Leeg laten tenzij een bron zonder impersonation onbereikbaar is. |
| `AUDIT_SOURCE_FOLDER_ID` | ja | Eén of meer map-ID's en/of Shared Drive root-ID's (die beginnen met `0A`), komma-gescheiden. Een geplakte Drive-URL wordt naar het ID herleid. |

### Meerdere locaties

Meerdere Drives of mappen naast elkaar koppelen kan: in het portaal staan ze als losse
rijen met een toevoeg- en verwijderactie, en de auditor typt nooit een scheidingsteken. De
komma is het opslagformaat van de env-var, niet iets dat je invult.

Bestanden die in twee gekoppelde locaties voorkomen worden op file-id ontdubbeld, dus
overlappende scopes leveren geen dubbele documenten op.

**Losse bestanden worden niet ondersteund.** De Drive-query is `'<id>' in parents`; een
bestand-ID matcht daar niets. Tot 2026-08-17 leverde dat een groen bolletje op met nul
gelezen documenten — de probe keek alleen of de API-aanroep slaagde, niet of er iets
terugkwam. Nu meldt zo'n locatie zichzelf als waarschuwing, met de oorzaak erbij wanneer
die is vast te stellen.

**Het getal per locatie is niet-recursief.** Het zegt hoeveel bestanden er *direct* in die
locatie staan, niet wat een run in totaal ophaalt. Een recursieve telling kost minuten
(gemeten: 2,5 minuut voor 409 documenten) en het configuratiescherm opent bij elke
pageload. Een map met alleen submappen toont daarom `0` en is toch bruikbaar; de
statusregel meldt dan dat er submappen zijn.

## Wat er gelezen wordt

| Formaat | Hoe |
|---|---|
| Google Doc | export naar `text/plain` |
| Google Sheet | export naar `.xlsx`, daarna alle bladen (een CSV-export geeft alleen het **eerste** blad) |
| Google Slides | export naar `text/plain` |
| `.docx` | `python-docx`, alinea's |
| `.xlsx` | `openpyxl`, celtekst per blad met de bladnaam als kop, formules als laatst berekende waarde |
| `.pptx` | `python-pptx`, tekst per dia |
| PDF | `pypdf`, doorlopende tekst per pagina — **geen OCR** |
| `text/plain`, markdown, HTML, CSV | als tekst gedecodeerd |

**Snelkoppelingen worden gevolgd.** Naam, MIME-type en `modifiedTime` komen van het
doelbestand en niet van de snelkoppeling: het leeftijdsfilter in de pipeline (2 jaar)
beslist op `modifiedTime`. Zit het doel ook rechtstreeks in een gekoppelde locatie, dan
telt het één keer — dedup op file-id.

## Wat er niet gelezen wordt

Afbeeldingen (jpeg, png, gif, tiff, svg), video, en Google Forms. Deze komen in de lijst
voor **handmatige review**, met de reden erbij, en worden meegeteld in de dekking.

Een bestand dat wél gelezen kon worden maar nul tekens oplevert — de gescande PDF — komt
niet als document met lege inhoud in het landschap. Dat zou de pipeline "geen bewijs" laten
concluderen over een document dat niemand heeft gelezen. Het gaat naar handmatige review
met de reden "mogelijk een scan".

## Dekking van een run

Elke ingest meldt op INFO-niveau hoeveel bestanden er zijn gezien, hoeveel er zijn gelezen,
en per reden hoeveel niet. Diezelfde telling staat in het `dekking`-blok van het
afsluitrecord in `runs.jsonl`:

    "dekking": {"gezien": 512, "gelezen": 480, "niet_gelezen": 32,
                "overgeslagen": {"image/png: afbeelding…": 21, …}}

Aantallen per reden, geen bestandsnamen — die staan in het handmatige-reviewspoor.

Waarom in het run-record en niet alleen in het log: het log verdwijnt bij een podherstart,
en "welk deel van de bron heeft het tool gezien" is precies wat een certificerende instantie
vraagt. Tot 2026-08-18 bleef 42% van 512 bestanden ongelezen, waarvan 92 zonder enige
melding — het aantal ingelezen documenten was daarmee een dekkingsclaim die niemand kon
nagaan.

> De namen `GOOGLE_SERVICE_ACCOUNT_FILE` en `GOOGLE_IMPERSONATE_USER` stonden hier eerder;
> die worden nergens in `src/` gelezen. `auth.py` leest de twee namen hierboven.

**Toegang regelen.** De echte toegangsmuur is het deelbeleid van Drive, niet een scope:
deel de auditmap met het `client_email` uit het keyfile. Staat de map in een **Shared
Drive**, dan is delen op mapniveau niet genoeg — het account moet lid van de Shared Drive
zijn. Zonder dat lidmaatschap authenticeert het account wél en ziet het nul bestanden.

Domain-wide delegation is bij deze opzet niet nodig. Vul je `GWS_IMPERSONATE_EMAIL` toch,
dan moet een Workspace-super-admin de client-ID van het service-account eenmalig
autoriseren voor precies de scopes hieronder; ontbreekt die autorisatie, dan faalt élke
call met `unauthorized_client`. Zet er nooit het service-account zelf in.

## Scopes

- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/documents.readonly`

Schrijven naar Drive (rapport-publicatie) gebruikt een aparte `DriveSink`
in milestone C met andere scopes.

## Audit-trail

`healthcheck()` retourneert het `tenant`-veld als de Folder-ID. Externe
verifieerbaarheid: het ID is in elke Google Drive URL terug te vinden.

## Aanroep

```bash
iso-audit pipeline --source drive --norm 27001 --mode autonoom
```

Multi-source: `--source drive --source planning --source jira`.
