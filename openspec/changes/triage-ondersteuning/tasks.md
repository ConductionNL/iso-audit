# Tasks: triage-ondersteuning

Volgorde is die van de meting: laag 0 haalt 462 bevindingen weg en kost niets, laag 1 nog 264,
en pas daarna is de vraag wat een agent toevoegt. Omgekeerd beginnen zou een agent bouwen om
een probleem te verzachten dat deterministisch op te lossen was.

## 1. Laag 0 — eigen output telt niet als bewijs

- [x] 1.1 Merkteken in de kop van `reporting/local_report.schrijf_rapport` en in de
      memo-render; voor binaire formaten als documenteigenschap
- [x] 1.2 Bij het inlezen op dat merkteken filteren; het document blijft in het landschap met
      de reden "eigen output, geen bewijs"
- [x] 1.3 **Eenmalige lijst** voor de twaalf bestaande bestanden, met datum en reden erbij —
      geen permanente naamregel, want een naam wijzigt en `Auditrapport 2022.docx` is extern
- [x] 1.4 Test: document met merkteken levert geen bevinding; extern auditrapport zonder
      merkteken wel
- [x] 1.5 Test: het merkteken overleeft de md → docx/html/pdf-conversie
- [x] 1.6 **Gemeten na de wijziging: 1241 → 779 bevindingen (−462, 37%).** Clausules met meer
      dan tien bevindingen: 53 → 27

## 2. Laag 1 — exacte duplicaten samenvouwen — **vervallen, gemeten overbodig**

- [x] 2.1 ~~Groeperen op `(clausule_id, norm, genormaliseerde beschrijving)`~~ — **niet
      gebouwd.** Nagemeten ná laag 0: van de 264 exacte duplicaten blijft er **één** over. Ze
      zaten vrijwel allemaal ín de eigen output — hetzelfde auditrapport in md, docx, html en
      pdf levert vier keer dezelfde beschrijving, en die vier vallen nu al weg.
- [x] 2.2 ~~Aantal en brondocumenten tonen~~ — vervalt met 2.1
- [x] 2.3 ~~Test op vier identieke beschrijvingen~~ — vervalt met 2.1
- [x] 2.4 ~~Test op de drempelloosheid~~ — vervalt met 2.1

> Eén samenvouwmechanisme bouwen voor één rij is duurder dan het oplevert: het is code die
> onderhouden moet worden, en elke groepering maakt de werklijst een stap verder van de ruwe
> bevindingen af. Blijkt het aantal duplicaten te groeien, dan is dit weer een change — met een
> nieuwe meting eronder in plaats van de oude.

## 3. Laag 2 — de agent die voorbereidt

- [x] 3.1 Per clausule de `bewijslast` uit `data/normteksten` naast de gekoppelde documenten,
      bevindingen en opvolgpunten leggen
- [x] 3.2 Resultaat: `bewijs_aanwezig`, `bewijs_ontbreekt`, `tegenspraak`, `waarom_nu` — elk
      met bronverwijzing, via de verificatie uit `assistent/vraag.py`. Plus een controle dat de
      genoemde bewijslast **letterlijk** in de norm staat: een eis die het model erbij verzint
      hoort niet in een auditdossier
- [x] 3.3 **Geen `voorstel`-veld**, en een test die faalt als het er komt
- [x] 3.4 Hergebruik van de Bronbevrager: dezelfde bronregel en dezelfde weigering om uit
      modelkennis te antwoorden
- [x] 3.5 Test: de agent schrijft geen triage-status en geen classificatie
- [x] 3.6 Test: ontbrekend bewijs komt als constatering, niet als NC

## 4. Ordening

- [x] 4.1 Ordening op aandacht, met per regel de reden zichtbaar. **Berekend en niet gevraagd**:
      het model levert feiten per clausule, de sortering gebeurt op dekkingsgraad en aantal
      tegenspraken. Een ordening die het model verzint is niet na te rekenen
- [x] 4.2 Terug naar clausule-orde met één handeling
- [ ] 4.3 Contract-test: de reden staat in de UI en de omschakeling bestaat. **Nog niet
      gedaan** — de agent en de ordening bestaan, het scherm nog niet

## 5. Preflight en documentatie

- [x] 5.1 Component `triage-agent` in `scripts/preflight.py` (betaald), gedraaid tegen het
      echte corpus in het cluster: clausule 5.12, 25 bronnen, 3 bewijslast-items, $0,0051. Die
      run vond twee fouten: de dekkingsgraad telde rijen in plaats van verschillende items (9.2
      meldde "2 van 8" terwijl de norm er vier kent), en de check koos een clausule zonder
      bewijslast en slaagde dus leeg
- [ ] 5.2 `docs/reference/triage.md`: wat er niet meetelt en waarom, hoe samenvouwen werkt, en
      waar de grens van de agent ligt
- [x] 5.3 CHANGELOG met de meting: 462 van 1241 uit eigen output, 264 exacte duplicaten

## 6. Aan de opdrachtgever

- [ ] 6.1 **Beslissing:** de vier formaten van hetzelfde rapport (md/docx/html/pdf) landen in
      een map die het landschap leest. Laag 0 dekt het, maar de vraag blijft of rapporten daar
      moeten staan
- [ ] 6.2 **Voorleggen na gebruik:** is de ordening op aandacht bruikbaar, of wil de auditor
      gewoon clausule-orde? Dat is pas in gebruik te beoordelen
