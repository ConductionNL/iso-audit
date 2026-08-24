# Taken — managementmemo-1a4

## 0. Blokkade eerst

- [ ] 0.1 **Norm-DB besluit.** 75 van de 87 gebruikte clausules ontbreken in `examples/norms/`.
      Zonder clausuleteksten weigert de memo op de echte dataset. Dit is een inhoudelijke en
      licentie-afweging (de repo bevat bewust geen normtekst) en hoort vóór de rest — anders
      levert deze change een sjabloon dat in productie weigert
- [ ] 0.2 Melding bij ontbrekende normtekst: alle ontbrekende clausules noemen met het totaal,
      niet alleen de eerste. Kleine fix, maakt 0.1 werkbaar

## 1. Datamodel

- [ ] 1.1 Actie-velden op een bevinding: `wat`, `wie`, `waar`, `uiterlijk` — nu bestaan ze
      nergens en zijn ze in het Q2-voorbeeld met de hand getypt
- [ ] 1.2 NC-groepering: een `thema`-veld waarmee meerdere bevindingen onder één genummerde NC
      vallen. Met de hand te vullen in deze change; `triage-agents` stelt het later voor
- [ ] 1.3 Migratie: bestaande werksets zonder deze velden blijven werken (leeg = onbeslist)
- [ ] 1.4 Test: een bevinding zonder actie-velden breekt de generatie niet, maar wordt geteld
      als onvolledig

## 2. Sjabloon

- [ ] 2.1 Kop: titel, auditor met rol, datum
- [ ] 2.2 Aanhef met ruwe én gecureerde telling en de verwijzing naar de detailrapportage
- [ ] 2.3 NC-blok: themanaam, bullets met bronverwijzing (`ISO-746`), documentnaam en clausule
- [ ] 2.4 Synthese-alinea per NC — in deze change een veld dat de auditor vult
- [ ] 2.5 Actietabel Wat | Wie | Waar | Uiterlijk
- [ ] 2.6 Normregel per NC (`Norm: ISO 27001:2022 §8.14 / §5.29 / §5.30`)
- [ ] 2.7 Verbeterpunten-tabel: Onderwerp | Actie | Norm
- [ ] 2.8 Voetregel met auditor, datum en vindplaats van de verantwoording

## 3. Paginabudget

- [ ] 3.1 Paginatelling na render (WeasyPrint levert het aantal; `pypdf` leest het terug)
- [ ] 3.2 Melding bij meer dan drie pagina's, met wat er niet past
- [ ] 3.3 Test tegen een dataset die te groot is: de memo wordt geschreven **en** gemeld
- [ ] 3.4 Test tegen de Q2-dataset: twee pagina's, zoals het handmatige voorbeeld

## 4. Vergelijking met het handmatige voorbeeld

- [ ] 4.1 `Auditmemo_management_2026-06-23.pdf` als referentie in `examples/` (geanonimiseerd —
      het bevat echte namen en rollen)
- [ ] 4.2 Vaststellen waar de gegenereerde memo van het handwerk afwijkt, en per verschil
      besluiten of het sjabloon moet meebewegen of het handwerk een uitzondering was

## 5. Documentatie

- [ ] 5.1 `docs/reference/managementmemo.md`: de vorm, het paginabudget, en waarom de memo
      alleen de acties bevat
- [ ] 5.2 README: de memo als eindproduct naast de verantwoording
- [ ] 5.3 CHANGELOG met de motivatie
