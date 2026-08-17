# Tasks: landschap-dekking

Volgorde is die van het design: laag 1 en 2 leveren 71 bestanden op zonder één nieuwe regel in
`uv.lock`; laag 3 (PDF) vraagt een afhankelijkheidsbesluit en staat daarom achteraan, met de
meldingen (blok 2) ervóór zodat het gat zichtbaar is ook als laag 3 blijft liggen.

## 1. Laag 1 — tekstformaten (6 bestanden, geen nieuwe code)

- [ ] 1.1 `text/markdown`, `text/html` en `text/csv` toevoegen aan `ONDERSTEUNDE_MIME_TYPES` in
      `sources/drive.py`, met een comment waarom ze er niet in stonden: de lijst kende alleen
      `text/plain`, niet omdat de andere onleesbaar zijn
- [ ] 1.2 Test: een markdown-bestand in een gekoppelde locatie komt als document met tekst
      terug

## 2. Zeggen wat er niet gelezen wordt (het stille gat)

- [ ] 2.1 `logger.debug("Skip (onbekend MIME)")` op regel 188 van `sources/drive.py` vervangen:
      per categorie tellen en na afloop op INFO melden met aantal en reden. Nu verdwijnen 92
      bestanden zonder één regel op INFO-niveau
- [ ] 2.2 Onbekende types (niet in `ONDERSTEUNDE_MIME_TYPES`, niet in `NIET_TEKSTUEEL`) krijgen
      een eigen categorie "onbekend type" — een nieuw bestandstype mag niet stil terugvallen in
      hetzelfde gat
- [ ] 2.3 De slotregel op regel 426 (`%d documenten ingelezen, %d voor handmatige review`)
      uitbreiden met het aantal gezien en het aantal niet gelezen; nu telt hij 119 van de 213
- [ ] 2.4 Test: een bron met een niet-ondersteund type levert een melding met dat type en het
      aantal, niet alleen een debug-regel

## 3. Dekking in het run-record

- [ ] 3.1 `Dekking`-dataclass in `api/runs.py` naast `Kosten`: gezien, gelezen, en per reden het
      aantal overgeslagen. Aantallen, geen bestandsnamen — 213 namen per record maakt de trail
      onleesbaar
- [ ] 3.2 `afsluiten()` accepteert `dekking: Dekking | None` en schrijft het als
      `record["dekking"]`, langs dezelfde weg als `kosten` op 2026-08-17
- [ ] 3.3 De telling doorgeven vanuit de Drive-adapter naar `run_job.py` → `session.py` →
      `afsluiten`, met dezelfde callback-vorm als `_bewaar_kosten`
- [ ] 3.4 Test: na een run met overgeslagen bestanden staat de dekking in het afsluitrecord

## 4. Laag 2 — bestaande afhankelijkheden (65 bestanden)

- [ ] 4.1 `.xlsx` via `openpyxl` (23 bestanden): celtekst per blad, bladnaam als kop
- [ ] 4.2 `.pptx` via `python-pptx` (2 bestanden)
- [ ] 4.3 Google Sheets (21) exporteren als CSV via de Drive-export, zoals Docs nu als tekst
      wordt geëxporteerd
- [ ] 4.4 Google Slides (19) exporteren als platte tekst; ze staan nu op `NIET_TEKSTUEEL` en
      verdwijnen daarmee in "handmatige review"
- [ ] 4.5 `NIET_TEKSTUEEL` opschonen: wat nu gelezen wordt, hoort daar niet meer in
- [ ] 4.6 Test per formaat: een bestand met bekende inhoud levert die tekst op

## 5. Snelkoppelingen (29 bestanden)

- [ ] 5.1 `shortcutDetails(targetId, targetMimeType)` toevoegen aan `_LIJST_VELDEN` in
      `clients/google_drive.py` — die velden komen nu niet mee uit de API
- [ ] 5.2 Snelkoppeling volgen naar het doelbestand, dat daarna dezelfde behandeling krijgt als
      elk ander bestand
- [ ] 5.3 Doel-ID door dezelfde `gezien`-set als de rest, zodat een doel dat ook rechtstreeks in
      scope zit niet twee keer meetelt
- [ ] 5.4 Test: snelkoppeling naar een leesbaar document levert één document op; een
      snelkoppeling naar een document dat ook rechtstreeks in scope zit, levert er samen één op

## 6. Leeg extractieresultaat is een storing

- [ ] 6.1 Nul tekens uit een geslaagde extractie ⇒ geen document, wel een melding "onleesbaar,
      mogelijk gescand", en meetellen in de dekking
- [ ] 6.2 Test: een bestand dat nul tekst oplevert komt niet als leeg document in het landschap

## 7. Laag 3 — PDF (91 bestanden, nieuwe afhankelijkheid)

- [ ] 7.1 **Besluit aan de opdrachtgever vóór 7.2**: `pypdf` toevoegen als afhankelijkheid. Een
      nieuwe dependency in een repo die zelf onder ISO 27001-scope valt is een beslissing, geen
      bijvangst
- [ ] 7.2 `uv add pypdf`, `uv.lock` gecommit, lockfile-diff gereviewd op onverwachte
      resolved-URL's — de supply-chain-discipline uit `~/.claude/CLAUDE.md`
- [ ] 7.3 PDF-tekstextractie in `sources/drive.py`; PDF van `NIET_TEKSTUEEL` af
- [ ] 7.4 Gescande PDF (nul tekens) valt onder 6.1 en komt niet als leeg document binnen
- [ ] 7.5 Test met een PDF-fixture in `examples/` — geanonimiseerd, geen klantdocument

## 8. Verificatie en documentatie

- [ ] 8.1 Meting herhalen tegen de gekoppelde Shared Drive en de dekking rapporteren: gezien,
      gelezen, en per reden overgeslagen. Uitgangspunt is 512 gezien / 299 gelezen op 2026-08-17
- [ ] 8.2 Controleren dat de 41 auditkritische bestanden uit het voorstel nu binnenkomen — de
      auditrapporten van de certificerende instantie, het NC-registratieformulier, de VvT
- [ ] 8.3 `docs/reference/` bijwerken: welke formaten gelezen worden, welke niet, en waar de
      dekking van een run te vinden is
- [ ] 8.4 CHANGELOG-regel met de motivatie: 42% van de bron werd niet gelezen, waarvan 92
      bestanden zonder melding
