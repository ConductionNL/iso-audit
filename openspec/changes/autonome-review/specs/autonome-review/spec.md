# Spec — autonome-review (nieuw)

## ADDED Requirements

### Requirement: Een bevinding zonder inhoud draagt geen oordeel

Een bevinding zonder beschrijving én zonder onderbouwing MUST als onbruikbaar worden gemarkeerd,
met de reden, en MUST NOT meetellen in het rapport of in de tellingen.

De rij MUST blijven bestaan.

Rationale: 55 van de 800 bevindingen van 2026-08-24 waren OFI's met een lege beschrijving én lege
onderbouwing. Die telden mee in het rapport en zeiden niets. Dit is een vormcontrole en geen
inhoudelijk oordeel — dezelfde soort regel als "een antwoord zonder bronverwijzing is een
storing" bij de Bronbevrager. Weggooien mag niet: dat een bevinding leeg terugkwam is zelf een
gegeven over de classificatie.

#### Scenario: Lege OFI

- **WHEN** een bevinding geen beschrijving en geen onderbouwing heeft
- **THEN** wordt hij gemarkeerd als onbruikbaar met de reden, blijft de rij bestaan, en telt hij
  niet mee in het rapport

#### Scenario: Alleen onderbouwing

- **WHEN** de beschrijving leeg is maar de onderbouwing gevuld
- **THEN** blijft de bevinding gewoon meetellen — er is inhoud om op te oordelen

### Requirement: De review adviseert en beslist niet

De review MUST per bevinding een advies met een reden opleveren.

De review MUST NOT een triage-status zetten en MUST NOT een bevinding verwijderen.

Rationale: de auditor-spiegel is de capability die dit tool draagt. Een agent die een status zet,
maakt van beoordelen bevestigen — dezelfde grens als in `triage-agents` en
`assistent/clausule.py`, waar `VERBODEN_VELDEN` dat afdwingt met een test.

#### Scenario: Review vindt een NC onverdedigbaar

- **WHEN** de review oordeelt dat een NC niet door het document wordt gedragen
- **THEN** staat dat als advies met reden bij de bevinding, en blijft de triage-status ongemoeid

### Requirement: De review kent de norm van de bevinding

De review MUST de normtekst, interpretatie en bewijslast krijgen van de norm waartegen de
bevinding is beoordeeld.

Rationale: `bevindingen.norm` bevat vandaag `beide` voor alle 800 rijen, en achttien
clausulenummers bestaan in beide normen. Zonder `clausule-per-norm` legt de review een bevinding
op §7.5 tegen dezelfde verkeerde tekst als de eerste classificatie — dan is een tweede model
alleen een duurdere manier om dezelfde fout te bevestigen.

#### Scenario: Norm nog niet vastgelegd

- **WHEN** een bevinding `norm = "beide"` heeft op een clausulenummer dat in beide normen bestaat
- **THEN** wordt die bevinding niet gereviewd, met de reden — liever geen oordeel dan een oordeel
  tegen de verkeerde norm

### Requirement: Beide normen worden getoetst

Een audit MUST beide normen toetsen. Wordt er één norm gekozen, dan MUST dat ISO 27001 zijn.

Rationale: expliciete keuze van de auditor (2026-08-24). ISO 27001 draagt de
informatiebeveiligingsaudit en heeft 93 clausules tegen 28 voor 9001; een audit die maar één norm
doet en 9001 kiest, laat het grootste deel van de beheersmaatregelen liggen.

#### Scenario: Eén norm gekozen

- **WHEN** een run met één norm wordt gestart
- **THEN** is dat 27001, en meldt de run expliciet dat 9001 niet is getoetst

### Requirement: Kosten en model van de review staan apart in de trail

Elke reviewaanroep MUST met model, kosten, peildatum en prijsgrondslag in de trail komen, ook bij
een storing.

De run-samenvatting MUST de reviewkosten apart van de classificatiekosten tonen.

Rationale: de review draait over honderden bevindingen op een zwaarder model en is daarmee de
duurste stap van de pipeline. Zonder aparte telling kan niemand besluiten of het het waard was.

#### Scenario: Review op 800 bevindingen

- **WHEN** de review over een volledige werkset draait
- **THEN** staan de kosten apart in de samenvatting, met het gebruikte model

### Requirement: De review draait eerst op een steekproef

Er MUST een manier zijn om de review op een beperkt aantal bevindingen te draaien voordat hij
over de volledige werkset gaat.

Rationale: 800 bevindingen op een zwaar model is een uitgave die je één keer wil doen met de
juiste prompt. Wat de review eruit haalt, moet eerst gemeten zijn op een steekproef — anders is
de eerste volledige run tegelijk het experiment en de rekening.

#### Scenario: Steekproef van 50

- **WHEN** de review op 50 bevindingen draait
- **THEN** rapporteert hij wat hij zou adviseren en wat dat kostte, zonder de rest aan te raken
