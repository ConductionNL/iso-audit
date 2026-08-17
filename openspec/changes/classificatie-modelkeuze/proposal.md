# Modelkeuze die werkt, en een kostenvraag die te beantwoorden is

## Waarom

### 1. Twee van de drie kiesbare modellen leveren stil nul bevindingen

`KIESBARE_MODELLEN` biedt Haiku 4.5, Sonnet 5 en Opus 5. De classificatie werkt alleen op
Haiku. Kies je een van de andere twee, dan meldt de run zich `klaar` met nul bevindingen,
zonder foutmelding en zonder regel in het log.

De keten, alle stappen in `classification/findings.py`:

1. `_classificeer_doc_batch` roept `client.messages.create()` aan (regel 316) **zonder
   `thinking`-parameter**. Op Haiku 4.5 betekent dat geen thinking. Op Sonnet 5 en Opus 5
   staat adaptive thinking dan **standaard aan** — het weglaten van de parameter is op die
   modellen niet "uit" maar "adaptief".
2. Daardoor is `resp.content[0]` een thinking-blok, geen tekstblok.
3. Regel 328 doet `resp.content[0].text`. Dat gooit een `AttributeError`, die op regel 330
   wordt afgevangen en `raw = ""` zet.
4. `_parse_json_list("")` vindt geen `[`, en **returnt op regel 263 een lege lijst zonder
   exception**. Dus `teller.fouten` gaat niet omhoog en de `except`-tak met de logregel
   (regel 349) wordt niet bereikt.

Netto: nul bevindingen als geldige uitkomst. Dit is dezelfde vorm als de hardcoded
planning-sheet (16-08) en de Drive-locatie die geen map is (17-08), maar op de plek die het
zwaarst weegt: het oordeel zelf. Een auditor die Opus 5 kiest omdat hij een beter oordeel
wil, krijgt een schone run met niets erin.

### 2. Het output-budget begrenst thinking én antwoord samen

`max_tokens=150 * len(clausule_ids) + 64` — bij vijf clausules 814 tokens. Op Sonnet 5 en
Opus 5 is `max_tokens` een plafond op thinking **plus** responstekst. Zelfs met probleem 1
opgelost eet thinking dat budget op en wordt de JSON halverwege afgekapt.

Dit is niet hypothetisch: het staat als breaking change in de migratiegids voor beide
modellen ("every route that never set `thinking`: it now thinks, and `max_tokens` caps
thinking + response text together").

### 3. De kostenvraag is onbeantwoordbaar

De tabel `classifications` heeft een `usage_json`-kolom (`store.py:158`) en
`_usage_dict(resp.usage)` wordt netjes meegegeven aan `log_classification`. Toch staat er in
geen enkele run data in: gemeten op 17-08 tegen zowel `output/audit.db` als de
referentie-checkout `~/projects/iso-audit/output/audit.db` — nul rijen met een gevulde
`usage_json`.

Gevolg: "wat kost een audit" is niet te beantwoorden, en daarmee is elke modelkeuze een
gevoelskwestie. De vraag komt van de opdrachtgever, niet van ons.

### 4. De prijzentabel staat op lijstprijs terwijl er een introtarief geldt

`PRIJZEN` zet Sonnet 5 op $3,00 / $15,00 per miljoen tokens. Er geldt tot en met
31 augustus 2026 een introductietarief van $2,00 / $10,00. `PRIJZEN_PEILDATUM` is
2026-08-14 en valt dus al binnen die periode.

Een auditrapport overschat de kosten van een Sonnet-5-run daarmee met een derde. Of dat
fout is hangt af van wat we bedoelen te rapporteren — werkelijke kosten of lijstprijs — en
dat staat nergens vastgelegd. Dat is het echte gat: het rapport noemt een bedrag en een
peildatum zonder te zeggen welke van de twee het is.

## Wat er verandert

**De thinking-configuratie wordt expliciet** in plaats van model-afhankelijk. Elke
classificatie-aanroep zegt zelf wat hij wil, zodat het gedrag niet stilletjes verandert
zodra iemand een ander model kiest.

**Het tekstblok wordt opgezocht in plaats van aangenomen.** `resp.content[0]` is een
aanname die op twee van de drie modellen niet klopt.

**Een lege parse wordt een fout, geen uitkomst.** Nul bevindingen uit een aanroep die wél
tokens heeft verbruikt is een storing en hoort geteld en gelogd te worden.

**Het output-budget krijgt ruimte** wanneer thinking aanstaat, met de reden erbij.

**`usage_json` wordt daadwerkelijk gevuld**, en het run-record krijgt de kosten met de
peildatum en de prijsgrondslag erbij.

**De prijsgrondslag wordt benoemd** — lijstprijs of werkelijk tarief — en de Sonnet-5-regel
volgt die keuze.

## Wat er niet verandert

**Geen model wordt uit de keuzelijst gehaald.** Het probleem is niet dat Sonnet 5 en Opus 5
er staan; het probleem is dat ze niet werken. Ze weghalen zou de auditor een keuze
ontnemen die hij hoort te hebben.

**Er komt geen aanbeveling over welk model "het beste" is.** Dat hoort uit een meting te
komen: dezelfde run op twee modellen, triage vergeleken met de referentie-output van juni.
Deze change maakt die meting mogelijk, hij loopt er niet op vooruit.

## Capability-impact

Versterkt de **auditor-spiegel**, tweemaal. Een oordeelloze run die zich als klaar meldt is
de ernstigste vorm van de valse dekkingsclaim die dit tool juist moet voorkomen. En een
auditor die het model kan kiezen maar niet kan zien wat die keuze kost of oplevert, heeft
geen keuze maar een knop.

Raakt **patroondetectie** indirect: een model dat beter redeneert over compensating
controls vindt andere patronen. Deze change maakt dat vergelijkbaar in plaats van
gissen.

Raakt **onafhankelijke bronnen** niet.
