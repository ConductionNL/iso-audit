# Tasks: iso-agents

## Bronbevrager (agent 1)

- [ ] 1.1 `assistent/ophalen.py`: clausule-detectie in de vraag (`8.24`, "clausule 5.27") en
      ophalen via `clause_matches`; alleen zonder clausule terugvallen op `documents_fts` —
      de koppeling die de pipeline legde is preciezer dan elke tekstmatch
- [ ] 1.2 Ophalen uit de andere drie bronnen: `normteksten.lookup`, `bevindingen` + `decisions`,
      en de opvolgpunten via `sources/opvolgpunten.py`
- [ ] 1.3 Eén bron-record per treffer: soort, id, naam, clausule(s) en een link naar
      `#/landschap` — dit is wat straks in de trail gaat én wat het antwoord mag noemen
- [ ] 2.1 `assistent/vraag.py`: systeem-prompt met de drie regels expliciet — alleen uit de
      meegegeven bronnen, verwijzen zonder citeren, en tegenspraak benoemen als geldige uitkomst
      (zonder die laatste lost het model het stil op door één bron te negeren)
- [ ] 2.2 `thinking: disabled` en `tekst_uit` uit `classification/respons.py`; output-budget
      op de langste variant, niet de gemiddelde — bij een krap budget verdwijnt juist de
      bronvermelding aan het eind
- [ ] 3.1 **Verwijzingscontrole:** elke clausule-ID en elk document-ID in het antwoord moet in
      de meegegeven bronnen voorkomen; zo niet, dan storing en geen geldig antwoord
- [ ] 3.2 Storing telt en logt met de reden, zoals bij de classificatie — niet stil een leeg
      antwoord teruggeven
- [ ] 4.1 `store.py`: tabel `assistent_vragen`, append-only, met vraag, antwoord, meegegeven
      bron-ID's, gebruikte bron-ID's, model, kosten, `PRIJZEN_PEILDATUM` en `PRIJZEN_GRONDSLAG`
- [ ] 4.2 `GET /instellingen/...`-stijl route in `api/app.py`: `POST /assistent/vraag`, achter
      de bestaande auth-gate, met de `_run_loopt`-check zoals de configroute (een vraag tijdens
      een run leest een halve werkset)
- [ ] 5.1 `api/ui.html`: scherm met één vraagveld en één antwoord; geen gespreksgeschiedenis
- [ ] 5.2 Bronnen naast elkaar bij tegenspraak, zó dat geen van de twee als hét antwoord leest
- [ ] 5.3 In de UI benoemen dat het antwoord een aanwijzing naar bewijs is en niet het bewijs
      zelf — de auditor opent het document
- [ ] 6.1 Test: vraag zonder dekking in het corpus levert "staat er niet in", geen ISO-kennis
- [ ] 6.2 Test: antwoord dat een niet-meegegeven document-ID noemt wordt geweigerd als storing
- [ ] 6.3 Test: tegenspraak tussen document en bevinding levert beide bronnen, geen keuze
- [ ] 6.4 Test: clausule in de vraag gebruikt `clause_matches` en niet FTS5
- [ ] 6.5 Test: de assistent schrijft niets — geen rij in `bevindingen`, geen `decisions`
- [ ] 6.6 Test: vraag en antwoord staan in `assistent_vragen` met de meegegeven bron-ID's
- [ ] 6.7 Contract-test in `test_ui_contract.py`: één vraagveld, geen geschiedenis, en de
      aanwijzing-geen-bewijs-tekst staat er
- [ ] 7.1 `docs/reference/vraagassistent.md`: het corpus, waarom er niet geciteerd wordt, en
      waarom hij niet uit modelkennis antwoordt
- [ ] 7.2 CHANGELOG-regel met de motivatie
- [ ] 8.1 In het cluster verifiëren met drie vragen: één met dekking, één zonder, en één waar
      document en bevinding elkaar tegenspreken
- [ ] 8.2 **Voorleggen aan Mark:** is "staat er niet in" in de praktijk bruikbaar of te streng?
      Dat is de enige ontwerpkeuze die pas in gebruik te beoordelen is

## Normuitlegger (agent 2)

- [ ] 9.1 Antwoordt uit `data/normteksten.lookup()`: `normtekst`, `interpretatie` en
      `bewijslast`, geparafraseerd. Beweert niets over Conduction — dat is de Bronbevrager
- [ ] 9.2 Test: een vraag naar wat een clausule eist noemt geen Conduction-document

## Gap-analist (agent 3)

- [ ] 10.1 Zet `bewijslast` per clausule naast wat er via `clause_matches` gekoppeld is
- [ ] 10.2 Oordeel komt uit de bestaande classificatie (`bevindingen`), niet uit deze agent —
      anders is er een tweede classificatiepad met een ander antwoord
- [ ] 10.3 Test: de Gap-analist schrijft geen rij in `bevindingen` en velt geen classificatie
- [ ] 10.4 Test: ontbrekende bewijslast wordt getoond als constatering, niet als NC

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
