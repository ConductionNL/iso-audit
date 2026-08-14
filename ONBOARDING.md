# ONBOARDING — iso-audit

> Voor **iedereen die deze repo oppakt**. Doel: van nul naar productief,
> en weten waar je iets vindt of toevoegt zonder de hele codebase te lezen.
> Dit document hoort **strak en actueel** te blijven — zie
> [§10 Docs strak houden](#10-docs-strak-houden).

Lees ook, in deze volgorde:

1. [`docs/explanation/missie.md`](docs/explanation/missie.md) — *waarom* dit tool bestaat (drie capabilities).
2. [`ARCHITECTURE.md`](ARCHITECTURE.md) — protocol-lagen, registries, pipeline-flow.
3. [`CLAUDE.md`](CLAUDE.md) — werkafspraken (boring & auditable, OpenSpec, geen `pip`).

---

## 1. Wat dit tool is — en wat het niet is

Een **pluggable ISO 9001 + 27001 audit-pipeline**. Het leest bronnen
(Drive, Planning, Jira), classificeert documenten tegen ISO-clausules met
een LLM, en produceert auditrapporten.

Belangrijk mentaal model: **dit is auditor-*ondersteuning*, geen pure
automation.** De drie capabilities uit `docs/explanation/missie.md` zijn onafhankelijke
bronnen, patroondetectie, en de *auditor-spiegel*. Die laatste betekent dat
een mens op vaste punten het oordeel houdt — de pipeline rapporteert nooit
blind een non-conformiteit waar alleen "niet gedocumenteerd" geldt
(zie [§7](#7-de-auditor-interview-interviewpy)).

## 2. Snel aan de slag

Dit project gebruikt **`uv`**, geen `pip` (lockfile `uv.lock` is gecommit).

```
uv sync --dev            # eerste keer: installeer deps + dev-tools
uv run iso-audit --help  # zie de subcommands
uv run iso-audit doctor  # check je omgeving en config
```

`doctor` is je eerste stop: het toont of de `gws` CLI in PATH staat, welke
env-vars gezet zijn, en welke sources/notifiers geregistreerd zijn (met een
healthcheck per notifier). Begin daar als er iets niet werkt.

## 3. Het mentale model — drie lagen, twee modes, één audit-trail

```
sources/  →  pipeline  →  modes  →  notifiers (alleen in integer-modus)
                 ↓
               sinks   (publicatie van output)
                 ↓
            store.py  (SQLite — append-only audit-trail)
```

- **`sources/`** — pluggable, **read-only** bron-adapters. Leveren documenten.
- **`sinks/`** — pluggable schrijf-adapters (eerste: `DriveSink`).
- **`notifiers/`** — pluggable handoff-kanalen (Slack, Email) voor de
  *integer*-modus, waar een mens hoog-risico beslissingen bevestigt.
- **modes** — `autonoom` (cron-vriendelijk, geen mens-in-de-lus) en
  `integer` (escaleert beslissingen via een Notifier).
- **`store.py`** — SQLite. De tabellen `decisions` en `classifications`
  zijn **append-only**: nooit overschrijven na resolved/cancelled.

De drie lagen volgen alle drie **hetzelfde registry-patroon** — zie
[§6](#6-een-adapter-toevoegen).

## 4. Waar staat wat

| Pad | Wat |
|---|---|
| `src/iso_audit/cli.py` | Console-script `iso-audit`: subcommands + flag-resolutie |
| `src/iso_audit/pipeline.py` | Orchestrator — bindt sources → classificatie → modes → rapport |
| `src/iso_audit/sources/` | Bron-adapters (Drive, Planning, Jira) + registry |
| `src/iso_audit/sinks/` | Schrijf-adapters (DriveSink) + registry |
| `src/iso_audit/notifiers/` | Slack/Email + `resolver.py` (zie gotcha §6) + registry |
| `src/iso_audit/modes/` | `autonoom` / `integer` + `base.Decision` |
| `src/iso_audit/classification/` | LLM-classificatie + clause-mapping; **prompts in `prompts/<versie>.md`** |
| `src/iso_audit/reporting/` | `report_generation.py`, `local_report.py`, `landscape` |
| `src/iso_audit/reporting/prompts/` | **Versie-prompts** (`*_v1.md`): redactionele regels voor rapport-taal; pas hier de toon aan, niet in Python |
| `src/iso_audit/miro/` | Miro-ingest — **READ-only** (write-flow verwijderd, zie CLAUDE.md) |
| `src/iso_audit/store.py` | SQLite-laag: `verbinding()`, `initialiseer()`, `upsert_*` |
| `src/iso_audit/interview.py` | Interactieve auditor-interview (§7) |
| `src/iso_audit/memo/` | `iso-audit memo` + `profile` — management-auditmemo (HTML+PDF) uit findings; profielen + user-pointed norm-DB. Zie `docs/explanation/memo-architecture.md` |
| `openspec/` | Specs + changes; werkwijze in CLAUDE.md |

## 5. Veelgebruikte commando's

```
# Volledige pipeline (--source en --mode verplicht):
uv run iso-audit pipeline --source drive --mode autonoom --norm beide

# Integer-modus vereist ook --notifier:
uv run iso-audit pipeline --source drive --mode integer --notifier slack

# Kostenschatting zonder LLM-calls:
uv run iso-audit pipeline --source drive --mode autonoom --dry-run-cost

# Alleen rapport regenereren uit bestaande DB (near-idempotent, geen LLM-
# classificatie/Drive/Miro) — voor iteratie op rapporttaal:
uv run iso-audit pipeline --report-only --norm beide

# Eenmalig Drive-template aanmaken:
uv run iso-audit setup-template

# Auditor-interview over ongedekte clausules (§7):
uv run python -m iso_audit.interview --norm beide

# Landschap (her)genereren na een interview:
uv run python -m iso_audit.reporting.landscape --norm beide
```

Geen impliciete defaults: `--source`, `--mode` (en bij integer `--notifier`)
zijn **verplicht**. Voor cron bestaat env-var-fallback
(`ISO_AUDIT_DEFAULT_SOURCE` / `_MODE` / `_NOTIFIER`); de CLI **logt expliciet**
wanneer fallback wordt gebruikt.

## 6. Een adapter toevoegen

Alle drie de lagen werken identiek — bewust, voor uitlegbaarheid aan
auditors. Voorbeeld voor een Source (Sink/Notifier analoog):

1. Erf van de base-class (`iso_audit.sources.base.Source`).
2. Geef een **class-level `naam`-attribute** (lowercase, niet-leeg) — dat is
   de sleutel waarop je 'm aanroept (`--source <naam>`).
3. Decoreer de class met `@register`.
4. **Zorg dat de module geïmporteerd wordt**, anders draait de
   `@register`-decorator nooit. Zie hoe `cli.py` `notifiers.slack`/`email`
   importeert om hun registratie te triggeren.

Controleren: `iso-audit doctor` toont de geregistreerde sources/notifiers.

**Gotcha:** `notifiers/resolver.py` (`SqliteDecisionResolver`) is **géén**
Notifier — het is een utility voor de modes-laag en is *niet* geregistreerd.
`notifiers.get("resolver")` geeft dus een `KeyError`. Verwar de naam niet.

## 7. De auditor-interview (`interview.py`)

De automatisering ziet alléén wat gedocumenteerd is. Clausules zonder
document-match zijn "gaps" — maar een gap is **niet** automatisch een
non-conformiteit; de praktijk kan bestaan zonder op papier te staan.

`interview.py` loopt de auditor interactief door precies die ongedekte
clausules en vraagt per clausule: *"bestaat deze praktijk, ook al is het niet
gedocumenteerd?"* → `positief` / `OFI` / `NC` / overslaan. Antwoorden gaan
direct (append) naar de `interviews`-tabel; hervatbaar, `--herinterviewen`
om opnieuw te doen. **Geen LLM** — puur menselijk oordeel in de audit-trail.

Dit is de *auditor-spiegel*-capability in code. Het is bewust ondersteunde
functionaliteit, geen legacy — ook al wordt er nu relatief weinig mee gedaan.

## 8. Configuratie & secrets

Config gaat nu via `.env` (env-vars; zie `iso-audit doctor` voor de lijst:
`AUDIT_NORM`, `AUDIT_DB_PATH`, `AUDIT_DRIVE_FOLDER_ID`, `ANTHROPIC_API_KEY`,
`MIRO_BOARD_ID`, Slack/SMTP, …). **Nooit** secrets committen — `.env`,
`*.pem`, `*.key` e.d. staan in `.gitignore`.

> **Richting (geen geplande change):** dit tool wil op termijn uit de
> CLI-hoek richting een **UI** voor auditors, met **DB-gedreven config** in
> plaats van `.env`/tokens. Persistentie is nu SQLite; mogelijk later
> Postgres. Houd daar rekening mee: vermijd nieuwe harde CLI-only- of
> `.env`-only-aannames, en houd de storage-laag (`store.py`) afgeschermd zodat
> een SQLite→Postgres-overgang lokaal blijft.

## 9. Kwaliteitspoort (vóór elke commit)

```
uv run pytest                 # tests
uv run ruff check .           # lint
uv run ruff format --check .  # format-check (--check, nooit --write)
uv run mypy --strict src      # type-check
uv run bandit -r src          # security-smells
uv run pre-commit run --all-files
```

Pre-commit hooks draaien in **gate-modus** (`--check`), nooit auto-fix — fix
lokaal en re-stage, anders lopen CI en lokaal uiteen.

## 10. Docs strak houden

Documentatie is een **doorlopende verplichting**, geen snapshot. De regel
(uit de globale werkafspraken):

- Wijzig je gedrag/scope van de code, **werk README + ARCHITECTURE + dit
  document bij in dezelfde commit.**
- Stale docstrings zijn een audit-liability — een lezer moet de docs kunnen
  vertrouwen. Bij twijfel: lees de openingsalinea van README en deze §1 en
  vraag je af of een nieuwe collega het nog snapt.
- Werk de `CHANGELOG.md` elke sessie bij (datum, wat, waarom, welke files).

## 11. OpenSpec-workflow (kort)

Changes leven in `openspec/changes/<naam>/`, specs in
`openspec/specs/<capability>/`. Volgorde: `/opsx:explore` → `/opsx:propose`
→ `/opsx:apply` → `/opsx:archive`. Details in [`CLAUDE.md`](CLAUDE.md).

## 12. Bekende open punten

- **Eerste end-to-end integer-run** als acceptatie (M-C §3.6) staat nog open;
  daarna `v1.0.0`-tag.
- **gsuite e2e-test** (`gsuite-iso-audit-automation` task 10.1) vereist live
  Drive + Miro — handmatig, met `gws auth login`.
- **`audit-rapport-management-taal`** (open change): herschrijft de
  management-summary-prompts naar auditor-frame + SMART; gated op akkoord van
  kwaliteitsmanagement vóór archivering.
- **Richting UI + DB-config** (zie §8) — meewegen bij architectuurkeuzes.
