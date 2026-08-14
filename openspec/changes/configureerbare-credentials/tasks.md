# Tasks: configureerbare-credentials

## 1. Settings-laag

- [x] 1.1 `config/settings.py`: `Waarde` (waarde + bron, geen waarde in `__repr__`),
      `Settings`, `load_config()` met precedence env > yaml > ui > default
- [x] 1.2 `config/herkomst.py`: `log_herkomst()` (JSONL, nooit waarden) en `masker()`
- [x] 1.3 Schema-versie: `config_version` lezen, onbekende hogere versie melden en
      dóórstarten
- [x] 1.4 Waarschuwing als een geheim veld uit `config.yaml` komt
- [x] 1.5 `bron_config.py` wordt de UI-laag achter `Settings`; publieke methodes
      ongewijzigd
- [x] 1.6 Precedence-tests: per veld alle combinaties van wel/niet gezet per bron
- [x] 1.7 Lektest: geen enkel API-antwoord of logregel bevat een ingevoerd geheim

## 2. Anthropic-auth

- [x] 2.1 `config/anthropic_auth.py`: login starten, code aanleveren, status, uitloggen
- [x] 2.2 Bij modus `sso` de API-key-variabele uit de omgeving verwijderen — ook leeg
- [x] 2.3 Endpoints voor login/logout/status; UI-toggle tussen de twee modi
- [x] 2.4 CLI in het image en profielmap op de persistente volume
- [x] 2.5 Test: lege API-key naast `sso` is na laden verdwenen

## 3. Modelkeuze en prijzen

- [x] 3.1 Prijzentabel corrigeren; peildatum-constante toevoegen
- [x] 3.2 Model als configureerbaar veld met keuzelijst, default Haiku 4.5
- [x] 3.3 Test: elk kiesbaar model heeft een prijsregel

## 4. Bronvelden en verbindingstest

- [x] 4.1 GWS-impersonate-veld (optioneel) en `with_subject` in `auth.py`
- [x] 4.2 Jira-label naar service-account; env-naam ongewijzigd
- [x] 4.3 `config/verbinding.py`: normalisatie van leveranciersfouten + Anthropic-check.
      GEEN parallelle healthcheck: `bron_health` blijft de enige bron van waarheid
      voor koppelstatus — een tweede administratie zou uit de pas lopen
- [x] 4.4 Test: een faalpad geeft geen ruwe leveranciersrespons terug

## 5. Documentatie

- [x] 5.1 `config.example.yaml` en `env.example` met alle sleutels en placeholders
      (bewust geen `.env.example`: de werkstation-policy verbiedt tooling het lezen
      en schrijven van `.env*`)
- [x] 5.2 `docs/reference/configuratie.md`: de precedence-tabel en waar wat hoort
- [x] 5.3 CHANGELOG-entry met de prijscorrectie expliciet benoemd
