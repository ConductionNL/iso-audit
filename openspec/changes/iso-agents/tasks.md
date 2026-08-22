# Tasks: iso-agents

## Bronbevrager (agent 1)

- [x] 1.1 `assistent/ophalen.py`: clausule-detectie in de vraag (`8.24`, "clausule 5.27") en
      ophalen via `clause_matches`; alleen zonder clausule terugvallen op `documents_fts` —
      de koppeling die de pipeline legde is preciezer dan elke tekstmatch
- [x] 1.2 Ophalen uit de andere drie bronnen: `normteksten.lookup`, `bevindingen`, en de
      opvolgpunten. **Afgeweken:** opvolgpunten komen uit de DB en niet live via
      `sources/opvolgpunten.py` — de pipeline legt ze bij een run vast, en live ophalen zou een
      vraag laten hangen op een externe API en een ánder corpus opleveren dan de run gebruikte.
      Ze staan in `bevindingen` met herkomst `<bron>-opvolging` en komen als eigen soort mee,
      niet dubbel. `decisions` blijft buiten dit corpus: dat is het besluitspoor, niet bewijs
- [x] 1.3 Eén bron-record per treffer: soort, id, naam, clausule(s) en een link naar
      `#/landschap` — dit is wat straks in de trail gaat én wat het antwoord mag noemen
- [x] 2.1 `assistent/vraag.py`: systeem-prompt met de drie regels expliciet — alleen uit de
      meegegeven bronnen, verwijzen zonder citeren, en tegenspraak benoemen als geldige uitkomst
      (zonder die laatste lost het model het stil op door één bron te negeren)
- [x] 2.2 `thinking: disabled` en `tekst_uit` uit `classification/respons.py`; output-budget
      op de langste variant, niet de gemiddelde — bij een krap budget verdwijnt juist de
      bronvermelding aan het eind
- [x] 3.1 **Verwijzingscontrole:** verwijzingen gaan als `[bron:<id>]`; elk id én elke
      genoemde clausule moet in de meegegeven bronnen zitten, anders storing. Een antwoord
      **zonder** verwijzing is ook een storing — dan valt er niets na te trekken, en juist zo
      ziet een antwoord uit modelkennis eruit. Plus: leeg corpus ⇒ geen aanroep, want een
      antwoord zonder bronnen kan niet uit de bronnen komen en dat is met een `if` af te dwingen
- [x] 3.2 Storing telt en logt met de reden, zoals bij de classificatie — niet stil een leeg
      antwoord teruggeven
- [x] 4.1 `store.py`: tabel `assistent_vragen`, append-only, met vraag, antwoord, meegegeven
      bron-ID's, gebruikte bron-ID's, model, kosten, `PRIJZEN_PEILDATUM` en `PRIJZEN_GRONDSLAG`
- [x] 4.2 `GET /instellingen/...`-stijl route in `api/app.py`: `POST /assistent/vraag`, achter
      de bestaande auth-gate, met de `_run_loopt`-check zoals de configroute (een vraag tijdens
      een run leest een halve werkset)
- [x] 5.1 `api/ui.html`: scherm met één vraagveld en één antwoord; geen gespreksgeschiedenis
- [x] 5.2 Bronnen naast elkaar bij tegenspraak, zó dat geen van de twee als hét antwoord leest
- [x] 5.3 In de UI benoemen dat het antwoord een aanwijzing naar bewijs is en niet het bewijs
      zelf — de auditor opent het document
- [x] 6.1 Test: vraag zonder dekking in het corpus levert "staat er niet in", geen ISO-kennis
- [x] 6.2 Test: antwoord dat een niet-meegegeven document-ID noemt wordt geweigerd als storing
- [x] 6.3 Test: tegenspraak tussen document en bevinding levert beide bronnen, geen keuze
- [x] 6.4 Test: clausule in de vraag gebruikt `clause_matches` en niet FTS5
- [x] 6.5 Test: de assistent schrijft niets — geen rij in `bevindingen`, geen `decisions`
- [x] 6.6 Test: vraag en antwoord staan in `assistent_vragen` met de meegegeven bron-ID's
- [x] 6.7 Contract-test in `test_ui_contract.py`: één vraagveld, geen geschiedenis, en de
      aanwijzing-geen-bewijs-tekst staat er
- [x] 7.1 `docs/reference/vraagassistent.md`: het corpus, waarom er niet geciteerd wordt, en
      waarom hij niet uit modelkennis antwoordt
- [x] 7.2 CHANGELOG-regel met de motivatie
- [x] 8.1 In het cluster geverifieerd op 2026-08-22 met drie vragen. Uitkomst: **1 van 3
      slaagde**, en de twee die faalden legden defecten in de verificatie bloot — een eerlijk
      "niet gevonden" heeft geen bron om naar te verwijzen, en het model groepeert verwijzingen
      op drie manieren die als verzonnen werden gelezen. Alle drie gerepareerd; een
      onverifieerbaar antwoord wordt nu vervangen in plaats van geweigerd
- [x] 8.2 **Beantwoord door het eerste gebruik (2026-08-21):** te streng op één punt. De
      vraag was "welk bewijs hebben we voor 8.2.4?"; die clausule bestaat niet in ISO
      27001:2022 (Annex A kent 8.24, met 24 gekoppelde documenten). "Staat er niet in" was
      correct en verzweeg dat de clausule zelf niet bestaat. Nu drie te onderscheiden
      uitkomsten: clausule bestaat niet (met een suggestie op gelijke cijferreeks), clausule
      bestaat zonder gekoppeld bewijs (een dekkingsgat, dus de normtekst met bewijslast gaat
      mee), of geen clausule in de vraag. Of de rest te streng is, blijft in gebruik te zien

## Normuitlegger (agent 2)

- [ ] 9.1 Antwoordt uit `data/normteksten.lookup()`: `normtekst`, `interpretatie` en
      `bewijslast`, geparafraseerd. Beweert niets over Conduction — dat is de Bronbevrager
- [ ] 9.2 Test: een vraag naar wat een clausule eist noemt geen Conduction-document

## Gap-analist (agent 3) — **gebouwd als de clausule-agent**

- [x] 10.1 `assistent/clausule.py` zet `bewijslast` per clausule naast de gekoppelde bronnen
- [x] 10.2 Geen eigen oordeel: `VERBODEN_VELDEN` weigert `voorstel`, `classificatie`, `oordeel`,
      `advies`, `triage` en `aanbeveling` in het antwoord
- [x] 10.3 Test: de agent schrijft niets en levert geen oordeelsveld
- [x] 10.4 Test: ontbrekende bewijslast komt als constatering (`bewijs_ontbreekt`), niet als NC

> Deze agent is gebouwd binnen change `triage-ondersteuning`, omdat de aanleiding daar lag: een
> werklijst van 1241 bevindingen. Functioneel is het de Gap-analist uit dit voorstel — dezelfde
> bronregel, dezelfde grens. Twee implementaties zou een tweede oordeelspad opleveren.

## Opsteller (agent 4)

- [ ] 11.1 Genereert beleidsstuk, risicoregister of VvT uit modelkennis, met de
      documentstructuur die de skill als inspiratie gaf (doel, scope, rollen, review-cyclus)
- [ ] 11.2 **Merkteken dat meereist met het document** — in de bestandsinhoud, niet alleen in
      de UI, want het document verlaat het portaal richting Drive
- [ ] 11.3 De classificatie negeert gemarkeerde documenten als bewijs
- [ ] 11.4 Een mens kan vastleggen dat de organisatie het document heeft overgenomen; vanaf dan
      telt het als gewoon bewijs, en die overname staat in de trail
- [ ] 11.5 Test: gegenereerd document in een gekoppelde Drive-locatie levert geen bevinding
- [ ] 11.6 Test: na vastgelegde overname telt hetzelfde document wél mee
- [ ] 11.7 In de UI benoemen dat de Opsteller uit modelkennis put en geen bewijs oplevert

## Overkoepelend

- [ ] 12.1 Agentkeuze in de UI: de auditor ziet welke agent antwoordde en waarom die past
- [ ] 12.2 Trail legt de agent vast naast vraag, antwoord en bronnen
- [ ] 12.3 Test: elke agent houdt zich aan zijn bronregel — de Normuitlegger raakt het corpus
      niet, de Bronbevrager put niet uit modelkennis
- [ ] 12.4 **Voorleggen aan Mark:** is de scheiding in de praktijk te volgen, of gaat een
      auditor de verkeerde agent vragen? Dat is pas in gebruik te beoordelen
