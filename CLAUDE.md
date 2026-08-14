# iso-audit — instructies voor Claude

## Wat deze repo is

Pluggable ISO 9001 + 27001 audit-pipeline. Verhuisd uit `Ops_to_Biz/audit/`
in mei 2026 met als doel: bron-pluggability vóór Jira-ingest, modes-
architectuur vóór de eerste integer-run, eigen audit-trail-context.

**Lees [`docs/explanation/missie.md`](docs/explanation/missie.md) eerst.** Het tool dient drie
capabilities (onafhankelijke bronnen, patroondetectie, auditor-spiegel) en
heeft daardoor andere design-criteria dan een typische pipeline-tool. Elke
substantiële change moet in zijn motivatie aangeven welke capability erdoor
versterkt of geraakt wordt.

## Architectuur in één blik

Drie protocol-lagen, één pipeline:

- **`iso_audit.sources`** — pluggable bron-adapters (Drive, Planning, Jira,
  MCP, REST). Read-only contract; immutable runtime-configuratie.
- **`iso_audit.sinks`** — pluggable schrijf-adapters. Spec-only in
  milestone A; eerste implementatie (DriveSink) komt in milestone C.
- **`iso_audit.notifiers`** — pluggable handoff-kanalen voor integer-modus.
  Slack en Email als eerste adapters in milestone C.

Daarbovenop twee runmodes (`autonoom`, `integer`) die op zeven vooraf-
vastgelegde beslispunten een mens-keuze kunnen vragen via Notifier.

Volledig plaatje: [`ARCHITECTURE.md`](ARCHITECTURE.md). Volledige roadmap:
[`openspec/changes/iso-refactor/`](openspec/changes/iso-refactor/).

## Boring & auditable

Dit tool valt onder ISO 27001-scope bij Conduction. Dat heeft consequenties:

- **Liever well-understood patronen dan elegante.** Drie identieke registries
  met `@register` decorator, niet één meta-class-magie. Drie `available()` /
  `get(naam)` paren, niet één generieke factory.
- **Geen impliciete defaults.** `--source`, `--mode`, `--notifier` zijn
  verplicht. Env-var-fallbacks (`ISO_AUDIT_DEFAULT_*`) bestaan voor cron,
  loggen expliciet dat er fallback wordt gebruikt.
- **Pre-commit hooks gebruiken `--check`, nooit `--write`.** Anders gaan CI
  en lokaal stilletjes uit elkaar lopen.
- **Geen `pip install`.** Dit project gebruikt `uv`. Lock-file (`uv.lock`)
  is gecommit en gerespecteerd; CI gebruikt `uv sync --frozen`.
- **Geheime classificatie-logica bestaat niet.** Alle prompts staan
  versiegestuurd in `src/iso_audit/classification/prompts/<versie>.md`.
- **Append-only audit-trail in DB.** `decisions` en `classifications`
  tabellen worden nooit overschreven na resolved/cancelled.

## OpenSpec-workflow

Dit project gebruikt OpenSpec voor change-management. Werkflow:

1. **Verkenning.** `/opsx:explore <topic>` — denken-modus, geen artefacten.
2. **Voorstel.** `/opsx:propose <change-name>` — genereert proposal.md,
   design.md, specs/, tasks.md in één klap.
3. **Implementatie.** `/opsx:apply <change-name>` — werk taken af, mark
   checkboxes, pauzeer bij blockers.
4. **Archiveren.** `/opsx:archive <change-name>` — na succesvolle
   implementatie en merge.

Specs leven in `openspec/specs/<capability>/spec.md`; changes in
`openspec/changes/<change-name>/`. Een change met `## ADDED Requirements`
voegt toe; `## MODIFIED` past aan; `## REMOVED` deprecates met `**Reason**`
en `**Migration**` velden.

## Werken in deze repo

```bash
uv sync --dev                                    # eerste keer
uv run pytest                                    # tests
uv run ruff check .                              # lint
uv run ruff format --check .                     # format-check
uv run mypy --strict src                         # type-check
uv run bandit -r src                             # security-smells
uv run pre-commit run --all-files                # alles bij elkaar
```

## Wat NIET hier hoort

- **ArgoCD-sync code.** Blijft in `MWest2020/Ops_to_Biz`.
- **Cockpit / business-view-filter werk.** Blijft in `Ops_to_Biz`.
- **Miro write-flow.** Per change `miro-write-trim` (mei 2026) zijn
  `board_setup` en `interview` verwijderd; Miro is binnen iso-audit
  **READ-only**. Boards opzetten doet de auditor via Miro-AI — zie
  `docs/how-to/miro-auditor-bord-prompt.md` en
  `docs/how-to/miro-interview-prompt.md`.
- **Klant-data, echte audit-output.** `examples/` bevat alleen
  geanonimiseerde fixtures. Echte audit-rapporten en `.db`-bestanden zijn
  via `.gitignore` uitgesloten.
- **Externe agent-harnassen.** Geen `.claude/agents/`, geen `.mcp.json`, geen
  `.habitat/`. In juli 2026 seedde een habitat-run ongevraagd drie rol-agents
  plus een `.mcp.json` die via `uvx --from git+…` een MCP-server uit een
  persoonlijke repo haalde — in een org-repo is dat een supply-chain-
  afhankelijkheid aan één persoon. Opgeruimd 2026-08-14. De werkwijze hier is
  de OpenSpec-workflow hierboven; die veranderen is een change met een
  motivatie, geen seed.

## Memory en gedeelde Claude-context

Deze repo erft de globale Claude-instructies (boring & auditable, geen
push zonder confirmatie, etc.) van `~/.claude/CLAUDE.md`. Project-
specifieke memory komt onder `~/.claude/projects/<repo-pad>/memory/`.

Bij twijfel over een wijziging: lees [`docs/explanation/missie.md`](docs/explanation/missie.md)
en stel jezelf de vraag of de wijziging een van de drie capabilities
versterkt of erodeert. Operationele verbeteringen zijn legitiem maar
altijd lager prio dan missie-versterkende werk.
