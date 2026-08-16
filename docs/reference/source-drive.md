---
status: draft
last_reviewed: 2026-07-13
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
| `AUDIT_SOURCE_FOLDER_ID` | ja | Map-ID, of Shared Drive root-ID (begint met `0A`). Een geplakte Drive-URL wordt naar het ID herleid. |

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
