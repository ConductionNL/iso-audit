# Tasks: landschap-dekking

Volgorde is die van het design: laag 1 en 2 leveren 71 bestanden op zonder één nieuwe regel in
`uv.lock`; laag 3 (PDF) vraagt een afhankelijkheidsbesluit en staat daarom achteraan, met de
meldingen (blok 2) ervóór zodat het gat zichtbaar is ook als laag 3 blijft liggen.

## 1. Laag 1 — tekstformaten (6 bestanden, geen nieuwe code)

- [x] 1.1 `text/markdown`, `text/html` en `text/csv` toevoegen aan `ONDERSTEUNDE_MIME_TYPES` in
      `sources/drive.py`, met een comment waarom ze er niet in stonden: de lijst kende alleen
      `text/plain`, niet omdat de andere onleesbaar zijn
- [x] 1.2 Test: een markdown-bestand in een gekoppelde locatie komt als document met tekst
      terug

## 2. Zeggen wat er niet gelezen wordt (het stille gat)

- [x] 2.1 `logger.debug("Skip (onbekend MIME)")` op regel 188 van `sources/drive.py` vervangen:
      per categorie tellen en na afloop op INFO melden met aantal en reden. Nu verdwijnen 92
      bestanden zonder één regel op INFO-niveau
- [x] 2.2 Onbekende types (niet in `ONDERSTEUNDE_MIME_TYPES`, niet in `NIET_TEKSTUEEL`) krijgen
      een eigen categorie "onbekend type" — een nieuw bestandstype mag niet stil terugvallen in
      hetzelfde gat
- [x] 2.3 De slotregel op regel 426 (`%d documenten ingelezen, %d voor handmatige review`)
      uitbreiden met het aantal gezien en het aantal niet gelezen; nu telt hij 119 van de 213
- [x] 2.4 Test: een bron met een niet-ondersteund type levert een melding met dat type en het
      aantal, niet alleen een debug-regel

## 3. Dekking in het run-record

- [x] 3.1 `Dekking`-dataclass in `api/runs.py` naast `Kosten`: gezien, gelezen, en per reden het
      aantal overgeslagen. Aantallen, geen bestandsnamen — 213 namen per record maakt de trail
      onleesbaar
- [x] 3.2 `afsluiten()` accepteert `dekking: Dekking | None` en schrijft het als
      `record["dekking"]`, langs dezelfde weg als `kosten` op 2026-08-17
- [x] 3.3 De telling doorgeven vanuit de Drive-adapter naar `run_job.py` → `session.py` →
      `afsluiten`, met dezelfde callback-vorm als `_bewaar_kosten`
- [x] 3.4 Test: na een run met overgeslagen bestanden staat de dekking in het afsluitrecord

## 4. Laag 2 — bestaande afhankelijkheden (65 bestanden)

- [x] 4.1 `.xlsx` via `openpyxl` (23 bestanden): celtekst per blad, bladnaam als kop
- [x] 4.2 `.pptx` via `python-pptx` (2 bestanden)
- [x] 4.3 Google Sheets (21) exporteren — **als `.xlsx` en niet als CSV**, anders dan het
      design zei: een CSV-export van een Google Sheet bevat alleen het **eerste** blad, en dat
      is dezelfde stille onvolledigheid die deze change weghaalt. Als xlsx komen alle bladen
      mee en doet de lezer uit 4.1 de rest
- [x] 4.4 Google Slides (19) exporteren als platte tekst; ze staan nu op `NIET_TEKSTUEEL` en
      verdwijnen daarmee in "handmatige review"
- [x] 4.5 `NIET_TEKSTUEEL` opschonen: wat nu gelezen wordt, hoort daar niet meer in
- [x] 4.6 Test per formaat: een bestand met bekende inhoud levert die tekst op

## 5. Snelkoppelingen (29 bestanden)

- [x] 5.1 `shortcutDetails(targetId, targetMimeType)` toevoegen aan `_LIJST_VELDEN` in
      `clients/google_drive.py` — die velden komen nu niet mee uit de API
- [x] 5.2 Snelkoppeling volgen naar het doelbestand, dat daarna dezelfde behandeling krijgt als
      elk ander bestand
- [x] 5.3 Doel-ID door dezelfde `gezien`-set als de rest, zodat een doel dat ook rechtstreeks in
      scope zit niet twee keer meetelt
- [x] 5.4 Test: snelkoppeling naar een leesbaar document levert één document op; een
      snelkoppeling naar een document dat ook rechtstreeks in scope zit, levert er samen één op

## 6. Leeg extractieresultaat is een storing

- [x] 6.1 Nul tekens uit een geslaagde extractie ⇒ geen document, wel een melding "onleesbaar,
      mogelijk gescand", en meetellen in de dekking
- [x] 6.2 Test: een bestand dat nul tekst oplevert komt niet als leeg document in het landschap

## 7. Laag 3 — PDF (91 bestanden, nieuwe afhankelijkheid)

- [x] 7.1 **Besluit aan de opdrachtgever vóór 7.2**: `pypdf` toevoegen als afhankelijkheid. Een
      nieuwe dependency in een repo die zelf onder ISO 27001-scope valt is een beslissing, geen
      bijvangst
- [x] 7.2 `uv add pypdf`, `uv.lock` gecommit, lockfile-diff gereviewd op onverwachte
      resolved-URL's — de supply-chain-discipline uit `~/.claude/CLAUDE.md`
- [x] 7.3 PDF-tekstextractie in `sources/drive.py`; PDF van `NIET_TEKSTUEEL` af
- [x] 7.4 Gescande PDF (nul tekens) valt onder 6.1 en komt niet als leeg document binnen
- [x] 7.5 Test met een PDF — **met de hand opgebouwd in de test** in plaats van een
      gecommitte binary in `examples/`: een auditor moet in de test kunnen zien wat er in het
      bestand zit. Zelfde keuze voor de xlsx- en pptx-fixtures. Variant zonder tekstlaag bootst
      een scan na

## 8. Verificatie en documentatie

- [x] 8.1 Meting herhaald op 2026-08-18 tegen dezelfde Shared Drive: **502 gezien, 456
      gelezen (91%), 46 niet** — was 512 / 299 (58%). Van de 46: 6 bewust uitgesloten
      normteksten, 12 afbeeldingen, 6 Google Forms, 1 video, 1 Drive-tekening, en 18
      snelkoppelingen waarvan het doel een 404 geeft (verwijderd, of in een My Drive die niet
      met het service-account is gedeeld) — een vondst die het tool eerder niet kon melden
- [x] 8.2 Gecontroleerd op 50 auditkritische bestanden, echt ingelezen: **45 leveren tekst
      op** (auditrapporten 38k–73k tekens, NC-registratieformulier 7.853, VvT 23.400,
      RI&E-actielijst 13.597, `instructie management review.pdf` 2.170, alle
      kwartaalverslagen). 4 zijn scans en worden als scan gemeld: beide ISO-certificaten en twee
      RI&E-overzichten. 1 geeft een 403 "this file cannot be downloaded" (downloadbeperking) en
      gaat als leesfout naar handmatige review
- [x] 8.3 `docs/reference/` bijwerken: welke formaten gelezen worden, welke niet, en waar de
      dekking van een run te vinden is
- [x] 8.4 CHANGELOG-regel met de motivatie: 42% van de bron werd niet gelezen, waarvan 92
      bestanden zonder melding
