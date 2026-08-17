---
status: draft
last_reviewed: 2026-08-17
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
