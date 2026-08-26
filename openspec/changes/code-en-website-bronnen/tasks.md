# Taken — code-en-website-bronnen

## 0. Eerst meten (vóór er code komt)

- [ ] 0.1 Welke repositories vallen onder scope? Aantal op GitHub, aantal op Codeberg
- [ ] 0.2 Hoeveel van de zes bewijspaden bestaan er nu per repository? (Nul is ook een uitkomst,
      en waarschijnlijk de interessantste)
- [ ] 0.3 Sitemap van conduction.nl: bestaat hij, hoeveel URL's, wat zegt `robots.txt`?
- [ ] 0.4 Tijd per API-aanroep meten, zodat de limieten op cijfers rusten en niet op gevoel

## 1. Configuratie

- [ ] 1.1 `bronnen.yaml` op het datavolume: schema met `repos:` en `websites:`
- [ ] 1.2 `examples/bronnen.yaml` als sjabloon met commentaar; test dat de run hem niet leest
- [ ] 1.3 Validatie: onbekende forge is een fout met de naam erin, geen stille overslag
- [ ] 1.4 Tokens als `Veld(..., geheim=True)` in `config/settings.py`
- [ ] 1.5 Wijzigingen in dezelfde append-only trail als `bron_config_log.jsonl`
- [ ] 1.6 Test: twee schrijvers tegelijk (zelfde slot-discipline als `api/werkset.py`)

## 2. `repo`-adapter

- [ ] 2.1 `sources/repo.py` met `@register`; `_github.py` en `_codeberg.py` als dunne clients
- [ ] 2.2 Beide clients leveren dezelfde `Repositoriegegevens`; test met opgenomen antwoorden
- [ ] 2.3 Bewijspaden ophalen; ontbrekend pad is een waarneming, geen fout
- [ ] 2.4 Metadata: zichtbaarheid, archiefstatus, branch-protectie, review-eis
- [ ] 2.5 Pull-request-aggregaten — test die faalt zodra er een naam in de uitvoer staat
- [ ] 2.6 Limieten instelbaar; test dat overschrijding meldt in plaats van afkapt
- [ ] 2.7 Test: adapter doet geen enkele schrijf-aanroep (verboden HTTP-methodes)

## 3. `website`-adapter

- [ ] 3.1 `sources/website.py` met `@register`
- [ ] 3.2 Sitemap lezen; terugval op opgegeven URL-lijst
- [ ] 3.3 `robots.txt` respecteren; uitgesloten pad staat als overgeslagen in de dekking
- [ ] 3.4 Zichtbare tekst opslaan, geen HTML; zelfde limieten als de documentbronnen
- [ ] 3.5 Verzoekvertraging tegen een externe host
- [ ] 3.6 Test: geen links volgen (pagina met links levert geen extra documenten)

## 4. Clausule-koppeling

- [ ] 4.1 Bewijspaden en metadata koppelen aan §8.4, §8.8, §8.9, §8.25, §8.28, §8.31, §8.32
- [ ] 4.2 Websitepagina's koppelen aan §5.31, §5.34 en 9001 §8.2
- [ ] 4.3 Test dat een repository zonder review-eis een waarneming op §8.32 oplevert

## 5. UI

- [ ] 5.1 Bronnen-scherm: repositories en websites toevoegen, wijzigen, verwijderen
- [ ] 5.2 Bron-health toont per forge of het token werkt — en welk niet
- [ ] 5.3 Browsertest, niet alleen een contract-test (de filter-les van 2026-08-26: de route kon
      het al, de knop ontbrak)

## 6. Aantonen dat het iets oplevert

- [ ] 6.1 Schone run mét de nieuwe bronnen; verschil in bevindingen op §8.25/§8.32 vastleggen
- [ ] 6.2 Nagaan of het thema *Ontwikkeling & wijzigingsbeheer* nu op praktijk rust in plaats
      van op documenten die zeggen wat er zou moeten gebeuren
- [ ] 6.3 Dekkingsrapport: wat is er gezien, wat bewust niet, en waarom

## 7. Documentatie

- [ ] 7.1 README: bronnentabel bijwerken (vijf wordt zeven)
- [ ] 7.2 `docs/how-to/`: een token aanmaken voor GitHub en voor Codeberg, met de minimale scope
- [ ] 7.3 CHANGELOG met de gemeten cijfers uit taak 0 en 6
