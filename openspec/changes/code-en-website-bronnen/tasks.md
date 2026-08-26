# Taken — code-en-website-bronnen

## 0. Eerst meten (vóór er code komt)

- [x] 0.1 183 actieve repo's op ConductionNL (164 publiek, 19 privé) + 63 op codeberg/conduction
- [x] 0.2 Steekproef van 12 recentst gepushte repo's: 6/12 SECURITY.md, 6/12 CODEOWNERS,
      6/12 CONTRIBUTING.md, 11/12 LICENSE, 9/12 dependabot, 0/12 pre-commit, 12/12 workflows.
      **0/12 met verplichte review op de hoofdbranch** — dat is de bevinding waarvoor dit bestaat.
- [x] 0.3 Sitemap bestaat, 146 URL's (137 na filtering), robots.txt staat alles toe.
      Bevat `/privacy/`, `/terms/` en `/quality/` — de externe toezeggingen.
- [x] 0.4 0,45s per GitHub-aanroep; 246 repo's x ~8 aanroepen = ~7 min. Vandaar MAX_PR=20.

## 1. Configuratie

- [ ] 1.1 `bronnen.yaml` op het datavolume: schema met `repos:` en `websites:`
- [ ] 1.2 `examples/bronnen.yaml` als sjabloon met commentaar; test dat de run hem niet leest
- [ ] 1.3 Validatie: onbekende forge is een fout met de naam erin, geen stille overslag
- [ ] 1.4 Tokens als `Veld(..., geheim=True)` in `config/settings.py`
- [ ] 1.5 Wijzigingen in dezelfde append-only trail als `bron_config_log.jsonl`
- [ ] 1.6 Test: twee schrijvers tegelijk (zelfde slot-discipline als `api/werkset.py`)

## 2. `repo`-adapter

- [x] 2.1 `sources/repo.py` met `@register`; `clients/forge.py` met beide dunne clients
- [x] 2.2 Beide clients leveren dezelfde `Repositoriegegevens`; live getoetst op beide forges
- [x] 2.3 Bewijspaden ophalen; ontbrekend pad is een waarneming, geen fout
- [x] 2.4 Metadata: zichtbaarheid, archiefstatus, branch-protectie, review-eis
- [x] 2.5 Pull-request-aggregaten, geen namen
- [ ] 2.6 Limieten instelbaar; test dat overschrijding meldt in plaats van afkapt
- [x] 2.7 Test: geen enkele schrijf-aanroep, en geen git clone/subprocess

## 3. `website`-adapter

- [x] 3.1 `sources/website.py` met `@register`
- [x] 3.2 Sitemap lezen; DOCTYPE geweigerd
- [x] 3.3 `robots.txt` respecteren; uitgesloten paden in `overgeslagen`
- [x] 3.4 Zichtbare tekst opslaan, geen HTML
- [x] 3.5 Verzoekvertraging tegen een externe host
- [x] 3.6 Test: geen links volgen

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
