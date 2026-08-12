# Spec — portal-dashboard (nieuw)

## ADDED Requirements

### Requirement: Het landingsscherm is een overzicht van audits

Het portaal MUST als landingsscherm een overzicht van alle audits tonen, met per
audit: norm en periode, een afgeleide status, de triage-voortgang en of de memo
gegenereerd is, de geraadpleegde bronnen, en wie er als laatste aan werkte en wanneer.

Het overzicht MUST ook audits tonen waarin nog geen run heeft gedraaid.

Rationale: een aangemaakte audit zonder run is een geldige toestand ("nog te
starten"). Hem verbergen tot er data is, maakt het scherm onbetrouwbaar als
werklijst.

#### Scenario: Overzicht toont de vier kolommen

- **WHEN** een auditor het portaal opent
- **THEN** ziet die per audit norm en periode, status, triage-voortgang, bronnen, en laatste bewerker met tijdstip

#### Scenario: Lege audit is zichtbaar

- **GIVEN** een audit die is aangemaakt maar waarin nog geen run draaide
- **WHEN** het overzicht wordt geopend
- **THEN** staat die audit erin met de status "nieuw"

### Requirement: Status is afgeleid, niet opgeslagen

De status van een audit MUST berekend worden uit de bestanden in de audit: geen run
betekent `nieuw`, wel een run met onvolledige triage betekent `loopt`, volledige
triage met gegenereerde memo betekent `memo-klaar`. Er MUST NOT een apart statusveld
bijgehouden worden dat kan afwijken van de bestanden.

Rationale: een los statusveld gaat op termijn liegen tegen de werkelijkheid, en in
een auditwerktuig is dat erger dan een berekening die een fractie langzamer is.

#### Scenario: Status volgt de werkelijkheid

- **WHEN** de laatste openstaande kandidaat-NC getrieerd wordt
- **THEN** verandert de status mee zonder dat er iets apart bijgewerkt hoeft te worden

### Requirement: Elk audit-specifiek verzoek noemt zijn audit

Alle routes die auditdata lezen of wijzigen MUST de audit expliciet in het pad
noemen. Er MUST NOT een impliciete "huidige audit" in servergeheugen bestaan.

Rationale: een impliciete huidige audit is precies hoe je in een auditwerktuig
beslissingen in de verkeerde audit vastlegt — en dat is niet terug te draaien in een
append-only trail.

#### Scenario: Onbekende audit geeft een leesbare fout

- **WHEN** een verzoek een audit-id noemt dat niet bestaat
- **THEN** antwoordt de API met 404 en een leesbare melding
- **AND** wordt er geen audit aangemaakt

#### Scenario: Beslissing landt in de genoemde audit

- **WHEN** een auditor een bevinding triëert binnen audit A
- **THEN** staat de trail-regel in audit A
- **AND** is audit B ongewijzigd

### Requirement: Een audit starten is een auditorhandeling

Een auditor MUST via het portaal een nieuwe audit kunnen aanmaken en daarin een run
kunnen starten, zonder tussenkomst van een beheerder en zonder wijziging aan een
manifest of deployment.

Rationale: zolang een nieuwe audit een `kubectl`-actie vraagt, is het portaal een
demonstratie en geen werktuig.

#### Scenario: Nieuwe audit zonder beheerder

- **WHEN** een auditor norm en periode invult en een run start
- **THEN** bestaat de audit en draait de run
- **AND** was daar geen wijziging in de deployment voor nodig
