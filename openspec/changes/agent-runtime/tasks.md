# Tasks: agent-runtime

## 1. Tools

- [x] 1.1 `agent/tools.py`: read-only tools rond `sources.get()`; plafonds op aantal
      documenten en inhoudslengte
- [x] 1.2 `stel_bevinding_voor` als voorstel-kanaal dat niets opslaat en bewijs eist
- [x] 1.3 Run-context per run, expliciet gezet — geen impliciete globale state
- [x] 1.4 Tests: geen tool schrijft, geen tool raakt trail of database

## 2. Lus

- [x] 2.1 `agent/runner.py`: `tool_runner` met rondelimiet
- [x] 2.2 Kostenplafond op de gecorrigeerde prijzentabel, met peildatum in de log
- [x] 2.3 Context wordt ook bij een exception opgeruimd
- [x] 2.4 Tests: beide grenzen stoppen de lus en de reden staat in de trail

## 3. Join en trail

- [x] 3.1 `voeg_toe_via_join` als aparte stap, zodat de scheiding in de code zichtbaar is
- [x] 3.2 `trail_regels` met tool, audit, agent, model, prompt-versie
- [x] 3.3 Test: twee bijna-identieke voorstellen worden één bevinding

## 4. Volgende increment (niet in deze change)

- [ ] 4.1 Aansluiten als runmodus op `pipeline.py` en in de UI
- [ ] 4.2 Beoordelen of Managed Agents met self-hosted sandbox iets oplevert dat deze
      opzet niet dekt (geplande runs, sessie-historie)
