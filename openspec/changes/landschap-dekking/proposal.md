# Dekking van het landschap: lees meer, en zeg wat je niet leest

## Waarom

Gemeten op 2026-08-17 tegen de gekoppelde Shared Drive: **512 bestanden, waarvan er 299
worden gelezen. 213 niet — 42%.**

Dat is op zichzelf een keuze die te verdedigen valt. Wat het een probleem maakt, is wélke
bestanden het zijn en hoe stil een deel ervan verdwijnt.

### Wat er niet binnenkomt is precies het bewijs dat telt

41 van de overgeslagen bestanden zijn op naam alleen al auditkritisch:

- **De certificeringsrapporten zelf** — `20250619_313 Auditrapport ISMS V20-2022_HER`,
  `20250619_283 Auditrapport ISO 9001 V15_HER`, de CA2-rapporten van 2024, het fase-2-rapport
  van 2022. Het oordeel van de certificerende instantie over Conduction.
- **`Afwijking 20250605_247 Registratieformulier NC-B-2025-01`** — het NC-registratieformulier.
  De systeem-prompt van de classifier legt uitgebreid uit dat het bestaan van zo'n memo
  aantoont dat de NC-procedure werkt; juist dat document komt niet binnen.
- **`VvT Conduction ISO 27001.pdf`** — de Verklaring van Toepasselijkheid, verplicht voor
  clausule 6.1.3.
- De ISO-certificaten, de RI&E met actielijst, de ISMS-, 9001- en AVG-handboeken,
  `instructie management review.pdf`, de interne-auditverslagen per kwartaal.

Dat raakt 9.2 (interne audit), 9.3 (directiebeoordeling), 10.2 (afwijkingen en corrigerende
maatregelen) en 6.1.3 (VvT) — de clausules waar een certificerende instantie het hardst op
doorvraagt.

### Twee soorten gemis, en de tweede is erger

| categorie | aantal | wat er gebeurt |
|---|---|---|
| PDF | 91 | op `NIET_TEKSTUEEL`, gemeld als "handmatige review" |
| Google Slides | 19 | idem |
| **Onbekend MIME** | **92** | `logger.debug("Skip (onbekend MIME)")` — **geen melding** |

Die 92 verdwijnen zonder dat het tool zegt dat het ze heeft laten liggen: ze zitten niet in
het aantal van 119 dat als handmatige review wordt gemeld, en op INFO-niveau is er geen
regel. Uitgesplitst: 29 snelkoppelingen, 23 `.xlsx`, 21 Google Sheets, 6 Forms, 3 markdown,
3 SVG, 2 HTML, 2 `.pptx`, 1 CSV, 1 MP4.

Drie daarvan zijn wrang: **markdown, HTML en CSV zijn pure tekst** en worden overgeslagen
terwijl `text/plain` wel wordt gelezen — waaronder `Auditrapport_beide_v3.3_2026-05-05.md`,
zelf een auditkritisch document. En de **29 snelkoppelingen** wijzen naar echte documenten,
mogelijk precies het bewijs dat je zoekt; ze maken bovendien de voor de hand liggende
workaround — een map met snelkoppelingen naar de relevante stukken — stil onbruikbaar.

### Een dekkingspercentage dat je niet ziet, is een dekkingsclaim

Het run-record vertelt hoeveel documenten zijn toegevoegd, niet welk deel van de bron
ongelezen bleef. Een auditor die 299 documenten ziet, ziet niet dat er 213 buiten stonden.
Dat is dezelfde vorm als de vier valse-groens die vandaag zijn weggehaald: het rapport ziet
er compleet uit en is het niet.

## Wat er verandert

**Lezen wat zonder nieuwe afhankelijkheid te lezen valt.** De dependencies bevatten al
`openpyxl`, `python-pptx` en `python-docx`. Daarmee komen `.xlsx` (23), `.pptx` (2), Google
Sheets (21, via export) en Google Slides (19, via export) binnen bereik, plus markdown, HTML
en CSV die alleen een MIME-regel missen (6).

**Snelkoppelingen volgen.** Een Drive-snelkoppeling draagt `shortcutDetails.targetId`; die
oplossen en het doel lezen, met dedup op file-id zodat een document dat ook rechtstreeks in
scope zit niet twee keer meetelt.

**PDF lezen.** 91 bestanden, de grootste en meest auditkritische groep. Dit vraagt wél een
nieuwe afhankelijkheid.

**Zeggen wat er niet gelezen is.** Elke overgeslagen categorie krijgt een melding op
INFO-niveau, en het run-record krijgt de dekking: hoeveel gezien, hoeveel gelezen, en per
reden hoeveel niet.

**Een leeg extractieresultaat is een storing.** Een gescande PDF levert nul tekst op. Dat mag
niet lezen als "document zonder inhoud" — dezelfde regel als bij de classificatie, waar een
afgekapt antwoord vandaag ook geen leeg oordeel meer is.

## Wat er niet verandert

**Geen OCR.** Gescande PDF's en afbeeldingen blijven onleesbaar. Dat is een aparte afweging
met eigen kosten; deze change zorgt dat ze *zichtbaar* onleesbaar zijn in plaats van stil
afwezig.

**Geen video.** De ene MP4 blijft buiten.

**Geen wijziging aan de classificatie.** Meer documenten betekent meer classificaties en dus
meer kosten — bij de gemeten tarieven een paar euro per audit, dus geen bezwaar. De
oordeelslogica blijft ongemoeid.

## Capability-impact

Versterkt **onafhankelijke bronnen** direct: een bron waarvan 42% niet wordt gelezen is geen
onafhankelijke bron maar een steekproef, en niemand koos die steekproef bewust.

Versterkt de **auditor-spiegel**: de dekking in het run-record maakt van "wat heeft het tool
gezien" een beantwoordbare vraag. Nu is het antwoord alleen uit een logregel te halen die na
een podherstart weg is.

Raakt **patroondetectie** indirect maar sterk: patronen over interne audits en afwijkingen
zijn niet te vinden zolang de interne-auditverslagen en het NC-formulier buiten het landschap
blijven.
