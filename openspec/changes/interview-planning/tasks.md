# Tasks: interview-planning

Voorstellen kan zonder credential-beslissing; inplannen niet. Vandaar de scheiding: blok 1–3
levert bruikbare waarde op, blok 5 wacht op een besluit.

## 1. Welke bewijslast een mens kan bevestigen

- [ ] 1.1 Per bewijslast-item in `data/normteksten` markeren: artefact of waarneming
- [ ] 1.2 Test: een clausule met uitsluitend artefact-bewijslast levert geen interviewvoorstel
- [ ] 1.3 Test: de markering bestaat voor élk bewijslast-item — een ontbrekende markering mag
      niet stil "waarneming" worden

## 2. Het voorstel

- [ ] 2.1 Per ongedekte clausule (via `interview._haal_gaps_op`) een voorstel: open
      bewijslast-items, één vraag per item, en de rol
- [ ] 2.2 Vragen deterministisch uit de bewijslast, geen modelkennis over interviewtechniek
- [ ] 2.3 Rol per clausule in de norm-catalogus; geen naam, geen e-mailadres
- [ ] 2.4 Test: elke vraag is te herleiden naar een bewijslast-item
- [ ] 2.5 Test: er staat geen zelfbedachte persoonsnaam in een voorstel

## 3. In de UI

- [ ] 3.1 Voorstellen naast de werklijst, niet erin — een voorstel is geen bevinding
- [ ] 3.2 Per voorstel: clausule, open bewijslast, vragen, rol
- [ ] 3.3 Contract-test: een voorstel is visueel geen triage-regel

## 4. Antwoorden vastleggen

- [ ] 4.1 Bestaande `interviews`-tabel gebruiken; het antwoord gaat ongewijzigd in
- [ ] 4.2 Test: geen samenvatting of herformulering vóór het opslaan

## 5. Inplannen — na de credential-beslissing

- [ ] 5.1 **Besluit aan de opdrachtgever:** inplannen vraagt een agenda-scope op een
      org-credential. Vandaag loopt `stuur_calendar_uitnodiging` via de `gws`-CLI met een
      persoonlijke OAuth-sessie; die binary zit niet in het image, dus vanuit het portaal kan
      het nu niet. Dit hoort bij `iso-portal` 7.4
- [ ] 5.2 Agenda-uitnodiging via het org-service-account, niet via de CLI
- [ ] 5.3 Expliciete handeling, nooit onderdeel van een run
- [ ] 5.4 Idempotent op `(audit_id, clausule_id, norm)`
- [ ] 5.5 Append-only spoor: wie, welke clausule, welke rol, welke uitkomst
- [ ] 5.6 Test: twee keer inplannen levert één uitnodiging
- [ ] 5.7 Test: een run stuurt geen uitnodiging

## 6. Preflight en documentatie

- [ ] 6.1 Component `interview` in `scripts/preflight.py`: voorstellen tegen het echte corpus,
      zonder iets te versturen
- [ ] 6.2 `docs/reference/interviews.md`: waar de vragen vandaan komen, waarom rol en geen
      naam, en waarom inplannen apart staat
- [ ] 6.3 CHANGELOG met de motivatie
