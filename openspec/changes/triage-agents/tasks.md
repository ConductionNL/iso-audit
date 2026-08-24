# Taken — triage-agents

## 0. Eerst dit, anders is de trail niet te vertrouwen

- [ ] 0.1 Een exceptie op een agent- of assistent-route MOET een rij in `assistent_vragen`
      opleveren, met reden en zonder antwoord. Vandaag laat een 500 geen spoor: de trail loopt
      tot 2026-08-22 terwijl er op 2026-08-24 een storing was. Bij één handmatige vraag is dat
      vervelend, bij tientallen aanroepen per run is het onbruikbaar
- [ ] 0.2 Test: een geforceerde exceptie levert een trail-rij op

## 1. De hub

- [ ] 1.1 Clustering: welke bevindingen horen bij elkaar volgens een **regel** (clausule, thema,
      documentherkomst), met de reden per cluster — zoals `assistent/clausule.orden()` dat doet
- [ ] 1.2 Opdracht per spoke: taaktekst, toegestane bron-ID's, model, tokenbudget
- [ ] 1.3 Parallel met een configureerbare bovengrens; voortgang meldt hoeveel er wachten
- [ ] 1.4 Samenvoegen van uitkomsten zonder er iets aan toe te voegen
- [ ] 1.5 Test: twee runs op een onveranderde werkset geven dezelfde ordening en verdeling
- [ ] 1.6 Test: een falende spoke stopt de andere niet

## 2. Landschapsagent (lezen en ophalen)

- [ ] 2.1 Hergebruik `assistent/ophalen.py` — clausule-eerst, dan FTS5, met de bovengrens op
      twaalf bronnen en de melding bij afkapping
- [ ] 2.2 Aanroepbaar door de hub met een expliciete bronselectie
- [ ] 2.3 Test: geen corpus betekent geen modelaanroep (bestaande regel, nu ook voor de hub)

## 3. Triage-ondersteuner

- [ ] 3.1 Per cluster: welk bewijs is er, wat ontbreekt volgens de bewijslast, welke bronnen
      spreken elkaar tegen, welke bevindingen beschrijven hetzelfde gebrek
- [ ] 3.2 `VERBODEN_VELDEN` zoals in `assistent/clausule.py`, met een test die faalt als iemand
      de lijst inkort
- [ ] 3.3 Test: agents hebben geen schrijfpad naar `apply_triage`
- [ ] 3.4 Test tegen het echte model op de echte werkset — een agent die tegen mocks werkt en
      tegen het model niet, is de fout die de Bronbevrager drie iteraties kostte

## 4. Synthesizer

- [ ] 4.1 Alleen bevindingen met `triage_status == "valide"` als invoer
- [ ] 4.2 Voorstel voor de groepering naar NC-thema's, met per thema de synthese-alinea
- [ ] 4.3 Conceptstatus: niet-geredigeerde tekst blokkeert de memo-generatie op dat thema
- [ ] 4.4 De onbewerkte modeltekst blijft in de trail, ook na redactie
- [ ] 4.5 Test: een niet-aangeraakt concept komt niet in de memo
- [ ] 4.6 Vergelijking met het handmatige Q2-memo: haalt de synthesizer een clustering die daar
      in de buurt komt? Zo niet, is dat een meting en geen mislukking

## 5. Kosten en modellen

- [ ] 5.1 Model per agent configureerbaar; zwaardere modellen toegestaan
- [ ] 5.2 Kosten, peildatum en prijsgrondslag per aanroep in de trail
- [ ] 5.3 Agentkosten in de run-samenvatting, apart van de classificatiekosten
- [ ] 5.4 Test: de opgetelde kosten in de samenvatting kloppen met de trail-rijen

## 6. Documentatie

- [ ] 6.1 `docs/reference/triage-agents.md`: de vier rollen, waarom spokes niet met elkaar
      praten, en waar de grens tussen voorbereiden en oordelen precies ligt
- [ ] 6.2 `docs/explanation/missie.md` bijwerken: hoe dit de auditor-spiegel versterkt in plaats
      van uitholt
- [ ] 6.3 CHANGELOG met de motivatie
