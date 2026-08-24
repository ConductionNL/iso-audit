# Taken — autonome-review

## 0. Volgorde

- [ ] 0.1 **`clausule-per-norm` eerst.** `bevindingen.norm` is nu `beide` voor alle 800 rijen;
      zonder de norm legt de review een bevinding op §7.5 tegen dezelfde verkeerde normtekst als
      de eerste classificatie — een duurdere manier om dezelfde fout te bevestigen

## 1. Vormcontrole (geen model nodig)

- [ ] 1.1 Bevinding zonder beschrijving én zonder onderbouwing → onbruikbaar, met reden
- [ ] 1.2 De rij blijft bestaan; dat een bevinding leeg terugkwam is zelf een gegeven
- [ ] 1.3 Onbruikbare bevindingen tellen niet mee in rapport en tellingen
- [ ] 1.4 Test: 55 lege OFI's uit de meting van 2026-08-24 vallen eruit, de rest blijft
- [ ] 1.5 Test: alleen-onderbouwing blijft wél meetellen

## 2. Steekproef vóór de volledige run

- [ ] 2.1 Review op N bevindingen met een rapport van wat hij zou adviseren en wat het kostte
- [ ] 2.2 Draaien op 50 bevindingen uit de echte werkset; vaststellen wat hij eruit haalt
- [ ] 2.3 **Beslissen** of de volledige run zinvol is — niet automatisch doorpakken

## 3. De review zelf

- [ ] 3.1 Vier deelvragen: is er inhoud, past het bij de clausule, is de klasse verdedigbaar,
      beschrijft dit hetzelfde gebrek als een andere bevinding op deze clausule
- [ ] 3.2 Uitkomst is advies + reden, nooit een status
- [ ] 3.3 Geen schrijfpad naar `triage_status` of naar het verwijderen van een bevinding
- [ ] 3.4 Model configureerbaar (Sonnet of Opus); budget expliciet
- [ ] 3.5 Test: een advies-veld met een verboden waarde wordt geweigerd, zoals in
      `assistent/clausule.py`

## 4. Norm

- [ ] 4.1 Beide normen is de standaard; bij één norm is dat 27001
- [ ] 4.2 Een run met één norm meldt expliciet dat de andere niet is getoetst
- [ ] 4.3 Een bevinding met `norm = beide` op een botsend nummer wordt niet gereviewd, met reden

## 5. Kosten

- [ ] 5.1 Elke aanroep in de trail met model, kosten, peildatum, prijsgrondslag
- [ ] 5.2 Reviewkosten apart van classificatiekosten in de run-samenvatting
- [ ] 5.3 Test: de opgetelde kosten kloppen met de trail-rijen

## 6. Documentatie

- [ ] 6.1 `docs/reference/autonome-review.md`: waarom een tweede zeef, en waar de grens ligt
      tussen zeven en oordelen
- [ ] 6.2 CHANGELOG met de meting van vóór en ná
