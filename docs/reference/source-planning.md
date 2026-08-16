---
status: draft
last_reviewed: 2026-07-13
---

# Source: Planning

> **Status:** spec klaar; implementatie in milestone B (verhuisd uit
> `Ops_to_Biz/audit/planning_ingest.py` + `gsa_client.py`).

Google Sheets-gebaseerde audit-planning als aparte bron. Conceptueel
losgekoppeld van Drive: planning is een operationeel document waar
auditor-besluiten in worden bijgehouden, niet een bewijsmateriaal-bron.

## Configuratie

| Env-var | Verplicht | Beschrijving |
|---|---|---|
| `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE` | ja | Pad naar de service-account JSON-key (gedeeld met DriveSource). Deployment-breed; niet in de UI. |
| `GWS_IMPERSONATE_EMAIL` | **nee** | Zie [`source-drive.md`](source-drive.md); leeg laten tenzij nodig. |
| `AUDIT_PLANNING_SHEETS_ID` | ja | Spreadsheet-ID van de auditplanning. Een geplakte Sheets-URL wordt naar het ID herleid. |

> De namen `GOOGLE_SERVICE_ACCOUNT_FILE` en `GOOGLE_IMPERSONATE_USER` stonden hier eerder;
> die worden nergens in `src/` gelezen.

De spreadsheet moet gedeeld zijn met het `client_email` uit het keyfile — leesrecht is
genoeg. Sheets gebruikt een eigen alleen-lezen scope
(`auth.sheets_read_service()`), los van de Drive-leesscope.

## Scopes

- `https://www.googleapis.com/auth/spreadsheets.readonly`

## Aanroep

```bash
iso-audit pipeline --source planning --norm 27001 --mode autonoom
```
