# iso-audit

> **Status:** milestone A + B + grootste deel C gemerged. Vier sources
> (Drive, **Nextcloud**, Planning, Jira), één Sink (Drive), twee Notifiers
> (Slack, Email) en beide modes (autonoom, integer) draaien. Het portaal
> draait in productie en heeft volledige runs afgemaakt. Resterend werk:
> eerste end-to-end integer-run als M-C §3.6 acceptatie, daarna `v1.0.0`-tag.

Pluggable ISO 9001 + 27001 audit-pipeline met drie protocol-lagen
(sources, sinks, notifiers) en twee runmodes (autonoom, integer).

## Wat het doet

**Bewijs verzamelen.** Documenten uit Google Drive of Nextcloud (PDF, Office, OpenDocument,
tekstformaten — met de dekking per run in de audit-trail: gezien, gelezen, en per reden
overgeslagen), planning uit Sheets, opvolgpunten uit Jira.

**Classificeren tegen de norm.** Per document en clausule een oordeel met onderbouwing,
kosten en modelversie in de trail. De auditor triageert; het tool beslist niet.

**Bevragen zonder oordeel.** De vraagassistent antwoordt uitsluitend uit wat er is ingelezen,
met een verwijzing per bewering — en toont niets dat niet na te trekken is. De clausule-agent
legt per clausule het verwachte bewijs naast het gevondene, en stelt géén triage-status voor.

**Gaten benoemen.** Waar geen documentbewijs is, stelt het tool een interview voor: per
ontbrekend artefact één vraag naar de vindplaats.

Wat het **niet** doet: oordelen namens de auditor, zijn eigen output als bewijs tellen, of
iets tonen dat niet naar een bron te herleiden is.

## Vóór een build: preflight

```bash
uv run python scripts/preflight.py --config-root <audits-map>   # elke component
uv run python scripts/preflight.py --component drive            # één component
uv run python scripts/preflight.py --met-api                    # inclusief de betaalde checks
```

Per component één keer het echte pad aflopen, tegen de echte bronnen. Dat vult een gat dat de
testsuite niet kan vullen: op 21 augustus 2026 zijn vijf defecten in productie gevonden die
alle 1159 tests groen lieten, omdat ze pas optreden tegen echte data of in de echte procesvorm.

## Gegenereerde bestanden

De norm-DB die de memo-bouwer leest is een **export** uit `iso_audit.data.normteksten` en wordt
niet met de hand bijgehouden:

```bash
uv run python scripts/genereer-norm-db.py            # schrijf examples/norms/*.yaml
uv run python scripts/genereer-norm-db.py --check    # faal als de export achterloopt
```

De `--check`-variant staat in de testsuite. Tot 24 augustus 2026 werd deze export met de hand
overgetypt en bevatte hij 13 van de 121 clausules — zonder foutmelding, met twee verkeerde
antwoorden tot gevolg: de memo weigerde, en de norm van bijna de helft van de bevindingen werd
verkeerd afgeleid.

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
  nextcloud, planning, jira, mcp, rest), `sinks.md` voor schrijf-adapters, `notifier-*.md` per
  handoff-kanaal (slack, email, teams, mattermost)
- **[`docs/reference/vraagassistent.md`](docs/reference/vraagassistent.md)** — de Bronbevrager: corpus, verwijzingscontrole, waarom er niet geciteerd wordt
- **[`docs/reference/run-historie.md`](docs/reference/run-historie.md)** — wat er in een run-record staat, en waarom verbergen geen verwijderen is
- **[`docs/reference/modelkeuze.md`](docs/reference/modelkeuze.md)** — welk model waar wordt gebruikt, en op welke prijsgrondslag
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
