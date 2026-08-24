# Taken — clausule-per-norm

## 1. Meten wat er nu misgaat (vastleggen vóór de verbouwing)

- [x] 1.1 `laad_clause_map("beide")` levert 103 ingangen waar er 121 horen; 18 ISO
      9001-clausules worden overschreven. Vastgelegd als `strict` xfail in
      `tests/data/test_norm_db_export.py`
- [ ] 1.2 Tellen hoeveel bevindingen uit een bestaande run op een botsend nummer zitten — dat is
      de groep waarvan het **oordeel** verkeerd kan zijn, niet alleen het label
- [ ] 1.3 Van een handvol daarvan nagaan tegen welke normtekst ze zijn beoordeeld

## 2. Koppeling per norm

- [ ] 2.1 `koppel_documenten` per norm aanroepen in plaats van op een samengevoegde map
- [ ] 2.2 Elke match draagt zijn norm; de samenvoeging in `laad_clause_map("beide")` verdwijnt
      of wordt verliesloos
- [ ] 2.3 Test: een document dat 9001 §8.4 raakt levert een 9001-match, niet 27001 §8.4
- [ ] 2.4 Test: de gecombineerde dekking noemt 121 clausules

## 3. Opslag

- [x] 3.1 `clause_matches`: `norm` in de primaire sleutel
- [x] 3.2 Migratie voor bestaande databases — tabel opnieuw opbouwen, geen rij verliezen
- [ ] 3.3 `bevindingen.norm` bevat `9001` of `27001`, nooit `beide`
- [x] 3.4 Test: twee normen met hetzelfde nummer op hetzelfde document geven twee rijen
- [ ] 3.5 Test: de migratie op een kopie van een echte database behoudt het aantal rijen

## 4. Classificatie

- [ ] 4.1 De prompt krijgt normtekst, interpretatie en bewijslast van de norm van de match
- [ ] 4.2 Test: classificatie op 9001 §7.5 bevat de 9001-tekst, niet die van 27001
- [ ] 4.3 `input_hash` moet de norm meenemen, anders deelt een botsend nummer zijn cache met de
      andere norm — dat zou een verkeerd oordeel bevriezen

## 4b. Blast radius — gemeten op 2026-08-24

Twaalf modules gaan uit van "een clausule is een nummer", 108 plekken noemen `clausule_id`
zonder norm ernaast. Volgorde die het risico beperkt:

- [ ] 4b.1 Eerst de **schrijfkant** (koppeling, opslag, classificatie), met `beide` als
      overgangswaarde die blijft werken
- [ ] 4b.2 Dan de **leeskant** (`memo/builder.py`, `memo/pattern_detection.py`,
      `api/landschap.py`, `api/routes_triage.py`, `classification/thema.py`,
      `interviewvoorstel.py`)
- [ ] 4b.3 Pas als beide kanten om zijn: de overgangswaarde `beide` verbieden
- [ ] 4b.4 **Niet in één keer.** Elke stap moet met een echte run te verifiëren zijn; een
      halve verbouwing die groen test maar tegen echte data faalt is precies het patroon dat
      dit project blijft raken

## 5. Werkset en UI

- [ ] 5.1 Bevinding-id's uniek over normen heen
- [ ] 5.2 `_resolve_standard()` verwijderen; de rij weet de norm
- [ ] 5.3 De UI toont de norm bij een clausule, zodat §5.1 leesbaar is
- [ ] 5.4 Test: twee bevindingen op §5.1 uit verschillende normen zijn los te triageren

## 6. Afronden

- [ ] 6.1 De `strict` xfail in `tests/data/test_norm_db_export.py` moet nu falen → markering weg
- [ ] 6.2 Bestaande werksets: de norm-labels herstellen met een spoor per wijziging, zoals bij
      `herstel_dubbele_ids()`
- [ ] 6.3 `docs/reference/` bijwerken: waarom een clausule (norm, nummer) is
- [ ] 6.4 CHANGELOG met de motivatie en de meting
