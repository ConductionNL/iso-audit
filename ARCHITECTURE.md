# iso-audit — Architectuur

> Status: milestones A + B + C-§3.1-3.5 gemerged. Resterend werk: eerste
> integer-run als M-C §3.6 acceptatie en `v1.0.0`-tag (§3.8). Dit document
> beschrijft het eindplaatje; de M-A/M-B/M-C labels in de protocol-secties
> hieronder markeren in welke milestone elke module is geland (provenance).

## Drie protocol-lagen, één pipeline

```
                            ┌────────────────────────────────────┐
                            │  iso_audit.pipeline                │
                            │  (orchestrator, milestone B)       │
                            └──┬───────────────────────────────┬─┘
                               │ Decision-events op 7 punten    │
                               ▼                               ▼
   ┌─────────────────────────┐            ┌─────────────────────────┐
   │ iso_audit.modes         │            │ iso_audit.notifiers     │
   │  base   (M-A: Decision) │            │  base   (M-A)           │
   │  autonoom (M-C)         │  vraagt    │  slack    (M-C)         │
   │  integer  (M-C) ────────┼─besluit────►  email    (M-C)         │
   └─────────────────────────┘            └─────────────────────────┘
                               ▲
                               │ list_documents / list_findings
                               │
   ┌─────────────────────────┐ │ ┌─────────────────────────┐
   │ iso_audit.sources       │◄┘ │ iso_audit.sinks         │
   │  base    (M-A)          │   │  base   (M-A spec-only) │
   │  drive   (M-B)          │   │  drive  (M-C)           │
   │  planning(M-B)          │   │                         │
   │  jira    (M-C)          │   │                         │
   └─────────────────────────┘   └─────────────────────────┘
```

(M-A = milestone A; M-B = milestone B; M-C = milestone C.)

Drie protocollen, drie registries, hetzelfde patroon. Dat is met opzet:
**uitlegbaarheid weegt zwaarder dan elegantie**. Een externe code-reviewer
of toekomstige onderhouder begrijpt na één van de drie hoe de andere twee
werken.

## Source Protocol (`iso_audit.sources.base`)

Read-only contract voor bron-adapters. Vier methodes:

```python
class Source(Protocol):
    naam: str

    def list_documents(self, filter=None) -> Iterator[Document]: ...
    def fetch_content(self, doc: Document) -> str: ...
    def list_findings(self, sessie_id: str) -> Iterator[Finding]: ...
    def healthcheck(self) -> dict: ...
```

Twee design-disciplines:

1. **Read-only.** Schrijven naar bron-systemen gaat via `iso_audit.sinks`.
   Een adapter die zowel leest als schrijft registreert twee classes
   (`DriveSource` + `DriveSink`).
2. **Immutable runtime-configuratie.** Source wordt geconfigureerd uit
   env-vars/config bij pipeline-start en daarna niet meer. Zie
   [`docs/explanation/missie.md`](docs/explanation/missie.md) capability 1 voor de motivatie.

Adapters registreren via `@iso_audit.sources.register` op class-level. De
registry werpt `ValueError` bij dubbele namen — dat is een
programmeerfout, geen silent-overschrijving.

## Sink Protocol (`iso_audit.sinks.base`)

`DriveSink` is de eerste implementatie (milestone C §3.3.1). Doorgeleiding
van bestaande reporting-write-paden via `Sink.send()` is DEFERRED tot na
de eerste integer-run (zie CHANGELOG 2026-05-14).

```python
class Sink(Protocol):
    naam: str
    def send(self, payload: SinkPayload) -> SinkResult: ...
    def healthcheck(self) -> dict: ...
```

Payload-hierarchy: `ReportPayload`, `NotificationPayload`, `MirrorPayload`
(placeholder voor capability 3 uit de missie).

Asymmetrie t.o.v. Source is bewust: Source enumereert + fetcht, Sink
levert one-shot. Symmetrie afdwingen voegt complexiteit toe zonder
use-case.

## Notifier Protocol (`iso_audit.notifiers.base`)

Kanaal-agnostische handoff-laag voor integer-modus.

```python
class Notifier(Protocol):
    naam: str
    def vraag_besluit(self, decision: Decision) -> str: ...   # → decision_id
    def healthcheck(self) -> dict: ...

class DecisionResolver(Protocol):
    def resolve(self, decision_id: str, action: str,
                modified_payload: dict | None = None) -> None: ...
```

Reden voor twee Protocols (Notifier + Resolver):

- **Notifier** weet hoe een Decision naar het kanaal gaat (Slack Block Kit,
  Email magic-link, …).
- **Resolver** parseert kanaal-respons naar de pipeline-agnostische shape
  `(decision_id, action, modified_payload)` en updatet de
  `decisions`-tabel.

Daardoor kan dezelfde IntegerMode zonder wijziging met een andere notifier
draaien.

## Modes Protocol (`iso_audit.modes.base`)

`AutonoomMode` en `IntegerMode` zijn beide gerealiseerd in milestone C
met zeven beslispunten:

| Punt | Risico | Autonoom | Integer |
|---|---|---|---|
| `ingest_scope` | laag | accepteer geconfigureerde scope | tonen bij flag, bevestigen |
| `merge_drive_miro` | laag | auto | auto |
| `classify_finding` | midden | LLM-output accepteren | escaleer bij confidence < 0.7 |
| `assign_clausule` | midden | regel-based | escaleer bij confidence < 0.7 |
| `generate_report_section` | hoog | LLM-output direct | concept naar mens, review verplicht |
| `send_report` | hoog | direct verzenden via Sink | sign-off vereist via Notifier |
| `delete_data` | hoog | nooit autonoom | mens-bevestigd via Notifier |

Volledige uitwerking per beslispunt: zie [`docs/reference/modes.md`](docs/reference/modes.md).

## Gegevensopslag

Eén SQLite-database (`iso_audit.db`), drie thema-tabellen die in elkaar
grijpen:

- **`documents`** + bestaande tabellen — uit `Ops_to_Biz/audit/store.py`
  gemigreerd in milestone B, schema ongewijzigd.
- **`classifications`** (milestone B) — input-hash, prompt-versie,
  model-versie, raw LLM-output. Reproduceerbaarheid + capability-2-data.
- **`decisions`** (milestone C) — geescaleerde beslissingen met `notifier_naam`,
  `classificatie_id` FK, indexen `(audit_id, status)` en
  `(punt, resolved_at)`. Append-only — pipeline overschrijft nooit
  resolved/cancelled rijen. Capability-3-data.

## Pipeline-orchestratie

```
1. CLI arg-parse        →   --source <verplicht>, --mode <verplicht>,
                            --notifier <verplicht bij --mode integer>
2. Source-registry       →   resolve adapters voor elke --source
3. Document-ingest       →   list_documents() + fetch_content() per adapter
                            → emit Decision("ingest_scope", risico="laag")
4. Finding-ingest        →   list_findings() per adapter
                            → emit Decision("merge_drive_miro", risico="laag")
5. Classificatie         →   per finding: LLM-call + persist `classifications`-rij
                            → emit Decision("classify_finding", risico="midden")
                            → emit Decision("assign_clausule", risico="midden")
6. Rapport-generatie     →   per sectie: LLM-output naar concept
                            → emit Decision("generate_report_section", risico="hoog")
7. Sink-publicatie       →   DriveSink.send(ReportPayload)
                            → emit Decision("send_report", risico="hoog")
```

Decision-events worden door de actieve Mode opgevangen. AutonoomMode
accepteert voorstel direct (behalve `delete_data`). IntegerMode escaleert
naar de geconfigureerde Notifier en blokkeert tot de DecisionResolver de
rij in `decisions` updatet naar `resolved`.

## Configuratie

Drie verplichte CLI-flags, met env-var-fallback voor cron-context:

| Flag | Env-var | Verplicht | Multi-value |
|---|---|---|---|
| `--source` | `ISO_AUDIT_DEFAULT_SOURCE` | altijd | ja |
| `--mode` | `ISO_AUDIT_DEFAULT_MODE` | altijd | nee |
| `--notifier` | `ISO_AUDIT_DEFAULT_NOTIFIER` | bij `--mode integer` | nee |

Wanneer een flag ontbreekt én env-var is gezet, gebruikt de CLI die waarde
maar logt expliciet (INFO) dat het via fallback ging — env-vars in cron-
unit-files zijn auditable.

## Wat niet in deze repo zit

- **MCP- en REST-source-adapters.** Eigen change-proposals na milestone C.
- **Teams- en Mattermost-notifiers.** Eigen change-proposals zodra een
  afnemer het vraagt.
- **Spiegel-laag-implementatie (capability 3).** Eigen change-proposal
  `iso-audit-mirror-foundation` na minimaal vier integer-runs.
- **Recidive-tracking, trend-grafiek, HR-event-koppeling.** Backlog in
  `openspec/changes/` na milestone C.
- **Migratie van `~/projects/miro-incident-board` en
  `~/projects/miro-desired-state`.** Eigen change-proposal als deze
  consumers actief raken op de geconsolideerde Miro-laag.

## Verder lezen

- **[`docs/explanation/missie.md`](docs/explanation/missie.md)** — waarom dit tool
  bestaat en welke design-criteria daaruit voortkomen.
- **[`MEMORY.md`](MEMORY.md)** — handoff-snapshot: huidige milestone-
  status, resterend werk, blocked items.
- **[`docs/reference/`](docs/reference/)** — per-laag uitwerking en setup-instructies:
  `source-*.md` per bron, `notifier-*.md` per kanaal, `sinks.md`, `modes.md`.
