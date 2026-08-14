# Change: agent-runtime

## Why

De pipeline is een **vaste keten**: alle bronnen, dan classificeren, dan memo. Wat hij
niet kan is dóórvragen. Een auditor die ziet dat een beleidsdocument verwijst naar een
procedure die niet in de auditmap staat, gaat die procedure zoeken. De vaste keten
classificeert wat er is en stopt.

Capability-raakvlak (`docs/explanation/missie.md`): dit versterkt **capability 2**
(patroondetectie). Een verwijzing naar iets dat ontbreekt, is een patroon.

## What Changes

- `iso_audit.agent`: read-only tools rond de bestaande `Source`-adapters, plus een lus met
  **afdwingbare** grenzen (rondelimiet én kostenplafond).
- Elke tool-aanroep levert een trail-regel met tool, bron, model en prompt-versie.
- De agent stelt bevindingen voor; de bestaande deterministische join bepaalt wat één
  bevinding is.

## Scope-grens

- **Geen** wijziging aan het Source-protocol, de registries, of de dedup.
- **Geen** tool die schrijft. Niet naar `findings.json`, niet naar `runs.jsonl`, niet naar
  de database. Een test faalt zodra dat verandert.
- **Nog niet** aangesloten op de UI of op `pipeline.py` als runmodus. Dat is een volgende
  increment; half aansluiten is erger dan niet aansluiten, want dan bestaat er een pad dat
  niemand kent.
- **Geen** `task_budget`. Dat is adviserend — het model ziet een aftelling maar wordt niet
  gestopt. Hier staan twee harde grenzen; zie `design.md`.
- **Geen** Managed Agents en geen self-hosted sandbox. Beoordeeld en afgewezen voor nu;
  zie `design.md`.
