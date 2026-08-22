# Tasks: interview-planning

Voorstellen kan zonder credential-beslissing; inplannen niet. Vandaar de scheiding: blok 1–3
levert bruikbare waarde op, blok 5 wacht op een besluit.

## 1. Welke bewijslast een mens kan bevestigen — **vervallen na meting**

- [x] 1.1 ~~Per bewijslast-item markeren: artefact of waarneming~~ — **niet gedaan.** Gemeten op
      2026-08-22: van de **481 bewijslast-items** beschrijven er ongeveer **drie** een
      waarneming. De catalogus is vrijwel volledig artefact-gericht. 481 items markeren zou
      betekenen dat dit tool zijn eigen bewijsstandaard verzint, en dat is een auditoroordeel
- [x] 1.2 ~~Test op artefact-only clausules~~ — vervalt met 1.1
- [x] 1.3 ~~Test op de volledigheid van de markering~~ — vervalt met 1.1

> **De vraag is omgedraaid.** Niet "welk bewijs kan een mens bevestigen", maar "we vinden dit
> artefact niet — bestaat het, en waar?" Dat is wat een auditor in een interview vraagt, het volgt
> volledig uit de bestaande catalogus, en het antwoord is een aanwijzing naar bewijs in plaats van
> een vervanging ervan. Zie het herziene voorstel en `src/iso_audit/interviewvoorstel.py`.
>
> **Aan de opdrachtgever:** de catalogus verrijken met waarneembare bewijslast blijft nuttig, maar
> is inhoudelijk ISO-werk. Aparte change, en die vraagt Marianne of jou — niet dit tool.

## 2. Het voorstel

- [x] 2.1 `interviewvoorstel.stel_voor()`: per ongedekte clausule (via `_haal_gaps_op`) één
      vraag per bewijslast-item, plus de rol. **Gemeten tegen het echte corpus: 14 voorstellen
      met 42 vragen** — 13 voor 27001 (o.a. 5.20 leveranciersovereenkomsten, 5.28 verzamelen van
      bewijs) en 1 voor 9001 (8.1 operationele planning)
- [x] 2.2 Vragen deterministisch uit de bewijslast, vaste formulering, geen LLM
- [x] 2.3 `ROLLEN` bestaat en is **bewust leeg opgeleverd**; onbekend toont `nog te bepalen`.
      De rol invullen is organisatiekennis en zit niet in de norm
- [x] 2.4 Test: elke vraag bevat het bewijslast-item waar hij uit komt
- [x] 2.5 Test: geen zelfbedachte persoonsnaam, en `ROLLEN` is leeg
- [x] 2.6 Titel uit de clause-map en niet uit `normteksten` — die laatste heeft geen `titel` per
      clausule (nagemeten: leeg voor élke 27001-clausule), en "5.28" zonder titel laat de
      auditor eerst opzoeken waar het over gaat

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
