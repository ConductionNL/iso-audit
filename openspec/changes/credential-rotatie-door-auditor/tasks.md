# Taken — credential-rotatie-door-auditor

## 1. Precedence en opslag

- [x] 1.1 `config/settings.py`: `Bron` krijgt `ui-override`; `load_config` krijgt
      `overschrijvingen` en plaatst die boven de omgeving.
- [x] 1.2 `api/bron_config.py`: gereserveerde sleutel `__overschrijvingen__` met per
      env-naam een hash van de omgevingswaarde ten tijde van overschrijven. Wie en wanneer
      komt uit het bestaande `bron_config_log.jsonl` — geen tweede administratie.
- [x] 1.3 `BronConfig` legt de omgeving vast bij constructie (`basis`). Zonder die
      momentopname is "komt deze waarde uit de omgeving?" zelfreferentieel, omdat de store
      zelf naar `os.environ` schrijft.
- [x] 1.4 `naar_omgeving()` overschrijft een bestaande env-waarde alleen voor velden die
      als overschrijving zijn gemarkeerd.
- [x] 1.5 Leegmaken verwijdert de markering en herstelt de omgevingswaarde.

## 2. API

- [x] 2.1 `POST /config/bronnen/{bron}` accepteert een waarde over een omgevingswaarde
      heen, zonder extra vlag of bevestigingsstap.
- [x] 2.5 `GET /config/health/{bron}` — één bron testen, niet alle.
- [x] 2.2 `bron_config_log.jsonl` krijgt `overschrijft_omgeving: true` op zo'n regel.
- [x] 2.3 Toegangslog onderscheidt `bron_overschreven` van `bron_geconfigureerd`.
- [x] 2.4 `/config/bronnen` geeft per veld `uit_omgeving`, `overschreven` en
      `omgeving_gewijzigd`.

## 3. UI

- [x] 3.1 Elk veld is gewoon invulbaar; geen `readonly`, geen bevestigingsknop.
- [x] 3.2 Een veld dat de omgeving vervangt toont dat, met "Terug naar de omgeving".
- [x] 3.3 Waarschuwing als de omgeving sindsdien is gewijzigd.
- [x] 3.4 Knop "Testen" per bron, plus "Opslaan en testen" met de uitslag in beeld.
- [x] 3.5 Contract-test: elke waarde van `Bron` heeft een label in de UI.
- [x] 3.6 `Cache-Control: no-store` op de UI — zonder header serveert een browser na een
      uitrol het oude scherm, en dat kostte een sessie aan verwarring.

## 4. Verificatie

- [x] 4.1 Test: een ingevulde waarde vervangt de omgeving en de herkomst is
      `ui-override`.
- [x] 4.6 **End-to-end in een echte browser** (`tests/e2e/`, Playwright): velden zijn
      typbaar, er is geen bevestigingsknop, opslaan toont een testuitslag, en terugdraaien
      herstelt de beheerderswaarde. Contract-tests op de HTML-brontekst zagen dit niet —
      die voeren de JS nooit uit, en juist daar zat de fout.
- [x] 4.2 Test: de overschrijving staat als zodanig in het wijzigingsspoor, zonder waarde.
- [x] 4.3 Test: terugdraaien herstelt de omgevingswaarde.
- [x] 4.4 Test: een gewijzigde omgeving achter een overschrijving wordt gemeld.
- [ ] 4.5 In het cluster verifiëren met een geroteerd Secret: de melding verschijnt en de
      overschrijving blijft gebruikt tot iemand hem verwijdert.

## 5. Documentatie

- [x] 5.1 CHANGELOG met de motivatie en het rotatiescenario.
- [x] 5.2 `docs/reference/configuratie.md` bijwerken: de *fixed*-markering is nu
      "vastgezet, tenzij expliciet overschreven".
- [x] 5.3 `deploy/README.md`: bij de credential-tabel noteren dat een auditor een
      credential kan overschrijven en dat dat in het spoor staat.
