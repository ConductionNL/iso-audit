# Tasks — portal-dashboard

> Stack: Python 3.12, `uv`, FastAPI + pydantic, één `ui.html` zonder build-stap.
> Geen nieuwe dependencies. Max 200 regels per file — de registry wordt
> `api/registry.py`, geen extra laag in `api/session.py`.
> Volgorde is bindend: 1 blokkeert 2, 2 blokkeert 3.
>
> Testbaar zonder bron-credentials: de sim-modus en de lege sessie werken al.
> Dat is bewust de volgorde — dit werk hoeft niet op vrijdag te wachten.

## 1. Audit-registry (capability: audit-registry)

- [x] 1.1 `api/registry.py`: audits opsommen, aanmaken en openen. Een audit is een
      directory met `audit.json` (norm, periode, aangemaakt, aangemaakt_door).
      Slug uit norm + periode; bestaand id → leesbare fout, geen suffix
- [x] 1.2 Periode-validatie: `YYYY-Qn` en `YYYY-Hn` toestaan met een leesbare fout
      bij vrije tekst, zodat sorteren op periode betrouwbaar blijft
- [x] 1.3 `AuditSession` per audit-id openen i.p.v. één keer bij app-start; de klasse
      zelf ongewijzigd. **Let op:** de sessies worden per audit-id gecachet in
      `api/deps.py`, want de voortgang van een lopende run leeft in het
      sessie-object. Een verse sessie per request liet `GET /run/progress` altijd
      `idle` zeggen terwijl de run draaide
- [x] 1.4 `runs.jsonl`: append-only run-registratie met run-id, tijd, identiteit,
      modus, norm, bronnen, hoofdstuk, aantal toegevoegd, aantal overgeslagen. Ook
      mislukte runs, met hun fout
- [x] 1.5 Aanvullende run: nieuwe kandidaten toevoegen zonder bestaande te wijzigen
      of te verwijderen; getrieerde bevindingen houden hun status
- [x] 1.6 Dedup deterministisch op norm + clausule + bron + genormaliseerde titel
      (lowercase + whitespace-collaps). Geen LLM, geen gelijkenis-drempel.
      Overgeslagen duplicaten geteld bij het run-record
- [x] 1.7 `.actief`-bestand met identiteit en timestamp, verversd bij elke mutatie;
      geen slot. Vers record (< 5 min) van een andere identiteit → waarschuwing
- [x] 1.8 Tests: aanmaken, dubbel id, aanvullende run behoudt triage, dedup
      reproduceerbaar en geteld, mislukte run geregistreerd, `.actief`-waarschuwing

## 2. API audit-gescoped (capability: audit-api, MODIFIED)

- [x] 2.1 Routes omzetten naar `/audits`, `POST /audits`, `/audits/{id}`,
      `/audits/{id}/runs`, `/audits/{id}/findings`, `/audits/{id}/trail`,
      `/audits/{id}/memo/…`. `GET /config/health` en `/healthz` blijven ongescoped
- [x] 2.2 Geen impliciete "huidige audit" in servergeheugen. Onbekend id → 404 met
      leesbare melding, geen audit aanmaken
- [x] 2.3 Status afgeleid uit de bestanden (`nieuw` / `loopt` / `memo-klaar`); géén
      opgeslagen statusveld
- [x] 2.4 `GET /audits` levert de vier kolommen: norm+periode, status,
      triage-voortgang + memo-klaar, bronnen, laatste bewerker + tijdstip
- [x] 2.5 De actor in de trail blijft de geverifieerde identiteit (bestaand gedrag
      uit `iso-portal` niet stukmaken); audit-log krijgt het audit-id erbij
- [x] 2.6 Tests: beslissing landt in de genoemde audit en niet in een andere; 404 op
      onbekend id; status verandert mee met de bestanden

## 3. UI (capability: portal-dashboard, portal-config-view)

- [ ] 3.1 Landingsscherm: audit-overzicht met de vier kolommen, inclusief lege
      audits. Nieuwe audit aanmaken vanaf hier
- [ ] 3.2 Audit-detail: de bestaande triage- en memo-flow, nu binnen één audit,
      plus de run-historie uit `runs.jsonl`
- [ ] 3.3 Configuratie als eigen scherm: per bron gekoppeld/niet uit
      `/config/health`, met de ontbrekende env-var of Secret-key erbij.
      **Alleen-lezen** — geen enkel endpoint dat bron-config of credentials schrijft
- [ ] 3.4 Waarschuwing wanneer een andere identiteit recent actief was in deze audit
- [ ] 3.5 `ui.html` blijft één bestand zonder build-stap

## 4. Uitrollen en documentatie

- [ ] 4.1 Eenmalige migratie van de bestaande `sessie/`-dir naar
      `audits/<norm>-<periode>/` — **mens-actie**, gedocumenteerd, geen automatische
      verplaatsing. Het portaal verzint niet welke audit dat was
- [ ] 4.2 initContainer `seed-sessie` aanpassen: `audits/`-root aanmaken i.p.v. een
      lege sessie. Idempotent blijven
- [ ] 4.3 `deployment.yaml`: de `--session`-arg vervalt; het portaal krijgt de
      audits-root. Versie + `newTag` gelijk bumpen (de image-check faalt anders)
- [ ] 4.4 `deploy/README.md` en `docs/` bijwerken: nieuwe routes, de migratiestap, en
      dat configuratie alleen-lezen is en waarom
- [ ] 4.5 `CHANGELOG.md`: breaking API-change expliciet benoemen

## 5. Buiten scope — niet stilzwijgend toevoegen

Deze punten staan in `proposal.md` als buiten scope en horen niet in deze change te
sluipen: meerdere schrijvers in één audit, per-audit autorisatie, een leesrol voor
management, en scope-bewerking in de UI.
