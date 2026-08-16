# Landschap los van audits, en Jira als opvolgpunten

## Waarom

Twee modelleerfouten die pas zichtbaar werden toen de keten voor het eerst echt liep
(2026-08-15, een ingest-run over Drive en Jira).

### 1. Het documentenlandschap hoort niet bij één audit

De opslag is al gedeeld: er is **één** `AUDIT_DB_PATH` met `documents` en
`clause_matches` voor de hele tool, terwijl `findings.json` en `runs.jsonl` per audit
zijn. Het inlezen hing er als runmodus ónder een audit, en dat schuurt: het landschap is
van de organisatie, niet van audit 2026-Q3. Twee audits zouden hetzelfde werk twee keer
doen, tegen dezelfde opslag.

Praktisch gevolg dat we maten: een Drive-lezing kost tweeënhalve minuut en 409 documenten.
Dat per audit herhalen is verspilling, en het maakt "welk landschap heeft deze audit
gezien" onbeantwoordbaar — beide audits kijken toch naar dezelfde tabel.

### 2. Jira levert geen bewijsmateriaal maar openstaande punten

Jira ging via `list_documents`, waarna elk ticket tegen elke clausule werd geclassificeerd.
In de referentie-output van juni staat het resultaat:

> `9001, 4.1, …, NC, …, "Houden aan de afspraak", Jira, "Document behandelt
> procesuitvoering via Jira, niet inzicht in organisatiecontext…"`

Een ticket krijgt een NC omdat het geen bewijs is voor een clausule waarvoor het nooit
bedoeld was. Dat is ruis, en het kost LLM-tokens per ticket.

Jira hoort bij de **P-D-C-A-opvolging**: welke afgesproken verbeteracties staan nog open.
Het `Source`-protocol modelleert dat al met `list_findings` — en `JiraSource` implementeert
het (issues met label `iso27001`/`iso9001`/`compliance` die niet Done zijn). Gemeten:
`list_findings` heeft **nul aanroepers**. De juiste weg bestaat en is nooit aangesloten.

## Wat er verandert

**Landschap wordt een eigen ding, naast de audits.** Eén voorraad documenten, één
inleesactie, eigen historie (wanneer, welke bronnen, hoeveel). Audits gebruiken hem; ze
bezitten hem niet. Daarmee vervalt `mode: "ingest"` op de audit-run — één plek, niet twee.

**Jira levert opvolgpunten in plaats van documenten.** Bronnen die `list_findings`
implementeren leveren hun punten rechtstreeks aan de triage, zonder classificatie en
zonder LLM-kosten. Een bron die géén `list_findings` heeft, blijft documenten leveren.

## Capability-raakvlak

Versterkt **capability 1 (onafhankelijke bronnen)**: een bron mag leveren wat hij ís, in
plaats van geperst te worden in de documentvorm van de eerste bron die er was.

Versterkt **capability 3 (auditor-spiegel)**: openstaande verbeteracties naast bevindingen
is de PDCA-cyclus zichtbaar maken. Een NC op een ticket dat geen bewijs wilde zijn, is het
tegenovergestelde — die vervuilt de spiegel.

## Wat hier niet in zit

- **Geen tweede opslag.** Het landschap gebruikt de bestaande `documents`-tabel.
- **Geen automatische verversing.** Inlezen blijft een handeling, geen achtergrondtaak.
- **Geen wijziging aan de classificatie zelf.** Alleen wát er geclassificeerd wordt.
