# Tasks: triage-ondersteuning

Volgorde is die van de meting: laag 0 haalt 462 bevindingen weg en kost niets, laag 1 nog 264,
en pas daarna is de vraag wat een agent toevoegt. Omgekeerd beginnen zou een agent bouwen om
een probleem te verzachten dat deterministisch op te lossen was.

## 1. Laag 0 — eigen output telt niet als bewijs

- [ ] 1.1 Merkteken in de kop van `reporting/local_report.schrijf_rapport` en in de
      memo-render; voor binaire formaten als documenteigenschap
- [ ] 1.2 Bij het inlezen op dat merkteken filteren; het document blijft in het landschap met
      de reden "eigen output, geen bewijs"
- [ ] 1.3 **Eenmalige lijst** voor de twaalf bestaande bestanden, met datum en reden erbij —
      geen permanente naamregel, want een naam wijzigt en `Auditrapport 2022.docx` is extern
- [ ] 1.4 Test: document met merkteken levert geen bevinding; extern auditrapport zonder
      merkteken wel
- [ ] 1.5 Test: het merkteken overleeft de md → docx/html/pdf-conversie
- [ ] 1.6 Meten na de wijziging: hoeveel bevindingen blijven over van de 1241

## 2. Laag 1 — exacte duplicaten samenvouwen

- [ ] 2.1 Groeperen op `(clausule_id, norm, genormaliseerde beschrijving)` met dezelfde
      normalisatie als `runs.dedup_sleutel`
- [ ] 2.2 De samengevouwen regel toont het aantal en de brondocumenten
- [ ] 2.3 Test: vier identieke beschrijvingen leveren één regel met aantal vier
- [ ] 2.4 Test: een verschil van meer dan witruimte levert twee regels — geen drempel

## 3. Laag 2 — de agent die voorbereidt

- [ ] 3.1 Per clausule de `bewijslast` uit `data/normteksten` naast de gekoppelde documenten,
      bevindingen en opvolgpunten leggen
- [ ] 3.2 Resultaat: `bewijs_aanwezig`, `bewijs_ontbreekt`, `tegenspraak`, `waarom_nu` — elk
      met bronverwijzing, via de verificatie uit `assistent/vraag.py`
- [ ] 3.3 **Geen `voorstel`-veld**, en een test die faalt als het er komt
- [ ] 3.4 Hergebruik van de Bronbevrager: dezelfde bronregel en dezelfde weigering om uit
      modelkennis te antwoorden
- [ ] 3.5 Test: de agent schrijft geen triage-status en geen classificatie
- [ ] 3.6 Test: ontbrekend bewijs komt als constatering, niet als NC

## 4. Ordening

- [ ] 4.1 Ordening op aandacht, met per regel de reden zichtbaar
- [ ] 4.2 Terug naar clausule-orde met één handeling
- [ ] 4.3 Contract-test: de reden staat in de UI en de omschakeling bestaat

## 5. Preflight en documentatie

- [ ] 5.1 Component `triage-agent` in `scripts/preflight.py` (betaald), tegen het echte corpus
- [ ] 5.2 `docs/reference/triage.md`: wat er niet meetelt en waarom, hoe samenvouwen werkt, en
      waar de grens van de agent ligt
- [ ] 5.3 CHANGELOG met de meting: 462 van 1241 uit eigen output, 264 exacte duplicaten

## 6. Aan de opdrachtgever

- [ ] 6.1 **Beslissing:** de vier formaten van hetzelfde rapport (md/docx/html/pdf) landen in
      een map die het landschap leest. Laag 0 dekt het, maar de vraag blijft of rapporten daar
      moeten staan
- [ ] 6.2 **Voorleggen na gebruik:** is de ordening op aandacht bruikbaar, of wil de auditor
      gewoon clausule-orde? Dat is pas in gebruik te beoordelen
