# Een clausule is (norm, nummer) — niet alleen een nummer

## Waarom

In een gecombineerde audit worden **18 van de 28 ISO 9001-clausules nooit getoetst**. Niet omdat
ze ontbreken — ze staan compleet in `clause_map_9001.yaml` en in `iso_audit.data.normteksten` —
maar omdat één regel ze weggooit op het moment van laden:

```python
samengevoegd["clausules"] = {**map_9001["clausules"], **map_27001["clausules"]}
```

Twee dicts met het clausulenummer als sleutel. Achttien nummers bestaan in beide normen, en bij
een botsing overschrijft de tweede de eerste. ISO 9001 §5.1 "Leiderschap en betrokkenheid" wordt
ISO 27001 §5.1 "Beleid voor informatiebeveiliging"; §7.5 "Gedocumenteerde informatie" wordt
"Beveiligd ontwikkelen"; §8.4 "Beheersing van extern geleverde processen" wordt "Scheiding van
ontwikkel-, test- en productieomgevingen".

De samengevoegde map heeft **103 ingangen waar er 121 horen**. De verdwenen achttien:

§5.1 · §5.2 · §5.3 · §6.1 · §6.2 · §6.3 · §7.1 · §7.2 · §7.3 · §7.4 · §7.5 · §8.1 · §8.2 · §8.3 ·
§8.4 · §8.5 · §8.6 · §8.7

Dat is de kern van ISO 9001: leiderschap, beleid, rollen, risico's en kansen, doelstellingen,
middelen, competentie, bewustzijn, communicatie, gedocumenteerde informatie, operationele
planning, klanteisen, ontwerp, uitbesteding, productie, vrijgave en afwijkende output. Het
auditrapport zet op pagina 1 "ISO 9001:2015 + ISO 27001:2022".

**Dezelfde aanname zit dieper.** De primaire sleutel van `clause_matches` is
`(doc_id, herkomst, clausule_id, sub_punt)` — zonder norm. Zelfs als de koppeling per norm zou
draaien, zou de tweede match op §5.1 voor hetzelfde document door `INSERT OR IGNORE` stil
worden weggegooid. De `norm`-kolom bestaat wel, maar staat buiten de sleutel en bevat in de
praktijk `beide` in plaats van de norm van de match.

En daaruit volgt weer het derde symptoom, dat op 2026-08-24 als eerste opviel:
`run_job._resolve_standard()` moet achteraf raden bij welke norm een bevinding hoort, omdat de
match die kennis niet heeft bewaard. Met een half gevulde norm-DB raadde hij 448 van de 903
bevindingen verkeerd.

Drie symptomen, één oorzaak: **een clausule wordt geïdentificeerd door zijn nummer, en dat
nummer is niet uniek over normen heen.**

## Wat er verandert

**De identiteit van een clausule wordt `(norm, nummer)`.** Overal waar nu een clausulenummer
alleen wordt doorgegeven, gaat de norm mee.

- `laad_clause_map("beide")` verdwijnt als samenvoeging. De koppeling draait **per norm**, met
  de map van die norm, en tagt elke match met de norm waaruit hij komt.
- `clause_matches` krijgt `norm` in de primaire sleutel, met een migratie.
- `bevindingen.norm` bevat de norm van de match (`9001` of `27001`), nooit meer `beide`.
- `_resolve_standard()` verdwijnt. Er valt niets meer te raden: de rij weet het.
- Een bevinding-id draagt de norm, zodat §5.1 uit beide normen twee bevindingen kan opleveren
  zonder botsing.

**De classificatie ziet de juiste normtekst.** Nu krijgt het model bij een botsend nummer de
tekst van de norm die de merge won. Bij §7.5 betekent dat: een document wordt beoordeeld tegen
"Beveiligd ontwikkelen" terwijl de auditor "Gedocumenteerde informatie" verwacht. Dat is geen
dekkingsgat maar een verkeerd oordeel, en het is niet aan de uitkomst te zien.

**De dekkingstelling wordt eerlijk.** Een gecombineerde audit die 103 van de 121 clausules kent,
hoort dat te melden. Na deze change is dat 121 van de 121, en klopt "ISO 9001:2015 +
ISO 27001:2022" op de voorpagina.

## Wat er niet verandert

- **De clausulenummers zelf.** §5.1 blijft §5.1; alleen de norm gaat ernaast mee.
- **De maps en normteksten.** Die zijn compleet en kloppen; er hoeft geen inhoud bij.
- **De append-only trails.** Bestaande rijen blijven; de migratie voegt toe en herschrijft niet
  wat een mens heeft besloten.

## Wat dit kost

Zes plekken lezen de huidige vorm (`ingest.py`, `pipeline.py`, `classification/findings.py` op
twee plaatsen, `interview.py`, `interviewvoorstel.py`), plus de opslag, de werkset en de UI. Dit
is de duurste change op de lijst en de enige waarbij het tool vandaag aantoonbaar een verkeerd
antwoord geeft over de norm die het claimt te toetsen.

**Vastgelegd tot die tijd:** `tests/data/test_norm_db_export.py` heeft een `strict` xfail die het
gat vastpint. Zodra deze change is doorgevoerd, faalt die test en moet de markering weg — dat is
het signaal dat het echt gerepareerd is en niet alleen omzeild.
