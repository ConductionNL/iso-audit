# iso-audit

> **Status:** milestone A + B + grootste deel C gemerged. Drie sources
> (Drive, Planning, Jira), één Sink (Drive), twee Notifiers (Slack, Email)
> en beide modes (autonoom, integer) draaien. Resterend werk: eerste
> end-to-end integer-run als M-C §3.6 acceptatie, daarna `v1.0.0`-tag.

Pluggable ISO 9001 + 27001 audit-pipeline met drie protocol-lagen
(sources, sinks, notifiers) en twee runmodes (autonoom, integer).

## Quick start

```bash
git clone https://github.com/MWest2020/iso-audit.git
cd iso-audit
uv sync --dev
uv run iso-audit --help
```

De CLI biedt `pipeline`, `doctor` en `setup-template` subcommands. Drie
verplichte flags: `--source`, `--mode`, en (bij `--mode integer`)
`--notifier`. Env-var-fallback voor cron — zie ARCHITECTURE.md
§"Configuratie".

## Architectuur

```
sources/  →  pipeline  →  modes  →  notifiers (integer)
                  ↓
                sinks  (publicatie)
```

Volledig plaatje in **[`ARCHITECTURE.md`](ARCHITECTURE.md)**. Het waarom
in **[`docs/explanation/missie.md`](docs/explanation/missie.md)**. Sessie-status en volgende-
stap in **[`MEMORY.md`](MEMORY.md)**.

## Documentatie

- **[`ONBOARDING.md`](ONBOARDING.md)** — van nul naar productief; waar staat wat, hoe voeg je een adapter toe
- **[`docs/explanation/missie.md`](docs/explanation/missie.md)** — drie capabilities en het rolconflict-frame
- **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — protocol-lagen, registries, pipeline-flow
- **[`docs/reference/`](docs/reference/)** — `source-*.md` per bron-adapter (drive,
  planning, jira, mcp, rest), `sinks.md` voor schrijf-adapters, `notifier-*.md` per
  handoff-kanaal (slack, email, teams, mattermost)
- **[`docs/reference/modes.md`](docs/reference/modes.md)** — autonoom vs integer en de zeven beslispunten
- **[`docs/explanation/memo-architecture.md`](docs/explanation/memo-architecture.md)** — auditmemo-feature + uitbreidings-hooks

## Management-auditmemo

`iso-audit memo` genereert de **management-one-pager** (HTML + PDF) uit de
findings-dataset: alleen de NC's en verbeterpunten die een managementbesluit
vragen, met genormeerde citaten, voorbehouden, action-tables en de status van
eerder geconstateerde NC's. Multi-tenant via **profielen**; normen als
**user-pointed plug-in** (de repo bevat geen norm-content).

```bash
# Profiel aanmaken (interactief) of een bestaande YAML gebruiken:
uv run iso-audit profile new
uv run iso-audit profile validate <slug>

# Memo genereren uit de findings-dataset:
uv run iso-audit memo \
  --profile <slug-of-pad> \
  --findings findings.json \
  --memo-input memo-input.yaml \
  --historical-ncs historical_ncs.yaml \
  --norms <pad-naar-norm-DB> \
  --output output/memo
```

Werkend voorbeeld in [`examples/auditmemo/`](examples/auditmemo/) (+ NL-
voorbeeld-norm-DB in [`examples/norms/`](examples/norms/)). De officiële (en
Engelstalige) norm-teksten levert de gebruiker zelf aan — de tool verzint nooit
een norm-citaat.

## Ontwikkeling

```bash
uv run pytest                        # tests
uv run ruff check .                  # lint
uv run ruff format --check .         # format-check
uv run mypy --strict src             # type-check
uv run bandit -r src                 # security
uv run pre-commit run --all-files    # alles
```

CI draait dezelfde vijf jobs parallel op elke PR.

## Bijdragen

PRs zijn welkom. Voor nieuwe Source- of Notifier-adapters: gebruik de
respectievelijke issue-templates onder
[`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) — die forceren de
protocol-conformance-checklist.

OpenSpec-workflow voor substantiële wijzigingen: zie
[`CLAUDE.md`](CLAUDE.md).

## Licentie

[EUPL-1.2](LICENSE) (European Union Public Licence) — een copyleft
open-source-licentie, sterk verankerd in de Europese publieke sector. Zie
[`LICENSE`](LICENSE) voor de volledige tekst.
