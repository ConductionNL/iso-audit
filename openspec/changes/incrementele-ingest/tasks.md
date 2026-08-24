# Taken — incrementele-ingest

## 1. Meten vooraf (gedaan 2026-08-24)

- [x] 1.1 Drie runs op één database: 31,2 / 16,4 / 15,9 min, met 118 / 0 / 0 classificatie-calls
- [x] 1.2 Per bron: Drive 65 s listing + 2,49 s/doc inhoud = 1.202 s; Nextcloud 3,2 s + 0,55 s/doc
- [x] 1.3 Wijzigingstijd beschikbaar: Drive 439/439, Nextcloud 120/120, Planning 0/150

## 2. Overslaan op wijzigingstijd

- [ ] 2.1 Vóór `fetch_content`: vergelijk de wijzigingstijd met `documents.modified_at`
- [ ] 2.2 Alleen overslaan als er ook tekst is opgeslagen — een leeg document is niet gelezen
- [ ] 2.3 Listing draait altijd volledig
- [ ] 2.4 Test: niets gewijzigd → geen enkele `fetch_content`
- [ ] 2.5 Test: één document gewijzigd → precies één `fetch_content`
- [ ] 2.6 Test: bron zonder wijzigingstijd → alles gelezen, geen geraden tijdstempel

## 3. Dekking blijft eerlijk

- [ ] 3.1 Overgeslagen document telt als gezien én gelezen
- [ ] 3.2 De melding zegt hoeveel er uit de vorige run komen
- [ ] 3.3 Test: dekking na een incrementele run is gelijk aan die na een volledige

## 4. Uitweg

- [ ] 4.1 `--opnieuw-lezen` negeert de opgeslagen tekst
- [ ] 4.2 Test: met de schakelaar wordt élk document opgehaald
- [ ] 4.3 In de documentatie: na een wijziging in de lezers is dit verplicht. Op 2026-08-24
      werden 32 OpenDocument-bestanden voor het eerst leesbaar; met alleen een
      tijdstempel-vergelijking zouden die als "ongewijzigd" nooit binnen zijn gekomen

## 5. Meten achteraf

- [ ] 5.1 Twee runs na elkaar: de tweede moet onder de twee minuten blijven
- [ ] 5.2 Zelfde aantal bevindingen als bij een volledige run — anders is er iets overgeslagen
      dat niet overgeslagen had mogen worden
- [ ] 5.3 CHANGELOG met beide metingen
