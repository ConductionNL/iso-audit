---
status: current
last_reviewed: 2026-08-20
---

# Modelkeuze en kosten

Welk Claude-model de classificatie gebruikt, kiest de auditor in het configuratiescherm. Wat
die keuze betekent — en wat er níet bij hoort — staat hier.

## Kiesbare modellen

`iso_audit.modellen.KIESBAAR`, doorgegeven als `KIESBARE_MODELLEN` in
`classification/findings.py`. Elk model hier moet een prijsregel hebben;
`tests/config/test_modelkeuze.py` faalt anders, want een model zonder prijsregel draait met een
kostenpost van nul en dat ziet in een auditrapport compleet uit.

| model | invoer | uitvoer | cache-read | cache-minimum |
|---|---|---|---|---|
| Haiku 4.5 | $1,00 | $5,00 | $0,10 | 4096 tokens |
| Sonnet 5 | $2,00* | $10,00* | $0,20 | 1024 tokens |
| Opus 5 | $5,00 | $25,00 | $0,50 | 512 tokens |

Bedragen per miljoen tokens, peildatum in `PRIJZEN_PEILDATUM`.
\* Introtarief t/m 2026-08-31; lijstprijs is $3,00/$15,00.

## Elke modelnaam staat in `iso_audit.modellen`

Eén module met de namen, en elders alleen verwijzingen. Tot 2026-08-20 stond dezelfde naam in
vijf spellingen in `src/` — vier constanten op `claude-haiku-4-5-20251001` en één fallback op
`claude-haiku-4-5`. Vijf plekken die uit elkaar kunnen lopen zonder dat iets faalt: een model
bumpen was vijf greps, en één vergeten regel geeft geen foutmelding maar een run die stil op een
ander model draait dan het rapport zegt.

`test_geen_modelnaam_als_letterlijke_string_buiten_modellen_py` is de gate: een modelnaam als
letterlijke string buiten die module laat de suite falen. In een comment of docstring mag hij.

Een gedateerd model-ID uit een historisch record (`claude-haiku-4-5-20251001`) wordt via
`modellen.GEDATEERDE_VORM` naar zijn alias herleid, zodat `prijs_voor()` oude runs kan prijzen
zonder een tweede prijsregel per spelling.

## Prijsgrondslag: lees `PRIJZEN_GRONDSLAG`

De tabel staat sinds 2026-08-20 op het **werkelijke tarief**, op verzoek van de opdrachtgever:
het bedrag in het rapport moet zo dicht mogelijk bij de factuur liggen. Concreet raakt dat één
regel — Sonnet 5 staat op zijn introtarief van $2,00/$10,00 in plaats van de lijstprijs
$3,00/$15,00.

Wat het **niet** is: de factuur. Hier staat het publieke tarief dat op de peildatum gold. Heeft
Conduction een eigen afspraak met Anthropic (volumekorting, commitment), dan wijkt de factuur
daar nog van af en is dit een bovengrens. Dat hoort zo te blijven staan in het rapport: een
bovengrens die je kunt navertellen is bruikbaar, een bedrag dat een contract nabootst niet.

Er zit bewust **geen datumlogica** in de tabel die zelf tussen tarieven kiest: dat zou een
tweede administratie zijn die achterloopt op de leverancier, precies wat de peildatum moet
voorkomen. In plaats daarvan noteert `TIJDELIJK_TARIEF_TOT` welk tarief tijdelijk is en tot
wanneer, en logt `prijs_voor()` een waarschuwing zodra die datum verstreken is. **Voor Sonnet 5
is dat 2026-08-31**: daarna staat er een te laag bedrag in de tabel tot iemand hem bijwerkt, en
een te laag bedrag is schadelijker dan geen bedrag omdat het compleet lijkt.

## Wat een run kost — gemeten, niet geschat

Uit 215 echte classificaties in de referentie-checkout (2026-08-17): gemiddeld **702 invoer- en
594 uitvoertokens** per classificatie. Voor die hele set:

| model | kosten | bij 10× dit volume |
|---|---|---|
| Haiku 4.5 | $0,79 | $7,89 |
| Sonnet 5 | $2,37 | $23,68 |
| Opus 5 | $3,95 | $39,47 |

**Prijs is bij dit volume geen argument.** Het verschil tussen het goedkoopste en het duurste
model is een paar dollar per audit, voor een oordeel dat naar een certificerende instantie gaat.
De modelkeuze is daarmee een kwaliteitsvraag, niet een kostenvraag.

De kosten van een run staan in het run-record (`runs.jsonl`), met model, peildatum en
grondslag. Het tokengebruik per classificatie staat in `classifications.usage_json`.

## Thinking staat expliciet uit

De classificatie stuurt `thinking={"type": "disabled"}` mee. Dat is geen detail: **weglaten van
die parameter is niet "uit"**, maar model-afhankelijk. Gemeten tegen de echte API met een
classificatie-achtige vraag:

| aanroep | blokken | stop_reason |
|---|---|---|
| `claude-sonnet-5` zonder `thinking` | `['thinking']` | `max_tokens` |
| `claude-sonnet-5` met `thinking: disabled` | `['text']` | `max_tokens` |
| `claude-opus-5` zonder `thinking` | `['thinking']` | `max_tokens` |
| `claude-haiku-4-5` met `thinking: disabled` | `['text']` | — |

Zonder de parameter kwam er op Sonnet 5 en Opus 5 **alleen** een thinking-blok terug en géén
tekstblok, waarna de run zich klaar meldde met nul bevindingen. Dat gedrag was
invoer-afhankelijk: op een triviale vraag gaf Sonnet 5 wél tekst, want adaptive thinking
betekent dat het model zelf beslist. Het werkte dus in een snelle test en faalde op het echte
werk.

Wie thinking later aanzet moet twee dingen weten. `max_tokens` begrenst op deze modellen
thinking **én** antwoord samen — `_max_tokens_voor` is nu gedimensioneerd op het antwoord
alleen, dus dat budget moet mee omhoog. En op Opus 5 mag `thinking: disabled` alleen bij effort
`high` of lager; de combinatie met `xhigh`/`max` geeft een 400.

## De cache doet niets

`_maak_system_param` zet `cache_control: ephemeral` op de systeem-prompt. Bij de huidige
promptgroottes slaat dat **niet aan**: de prompts zijn 122–726 tokens en het minimum
cacheerbare prefix staat in de tabel hierboven. Onder dat minimum cachet de API stil niet —
geen fout, geen waarschuwing. Gemeten over 215 classificaties: `cache_read` en `cache_write`
allebei nul.

Opvallend gevolg: caching zou alleen op Opus 5 aanslaan (minimum 512, prompt 726), het duurste
model. Wil je de cache echt gebruiken, dan moet de systeem-prompt groter — en dat is een
afweging tussen promptkwaliteit en cachewinst, niet een instelling.

## De modelkeuze bereikt alleen de classificatie

`AUDIT_CLASSIFICATION_MODEL` gaat naar `classification/findings.py` en verder niet.
`classification/llm.py`, `classification/thema.py`, `memo/draft.py` en
`reporting/report_generation.py` draaien op `modellen.STANDAARD` (Haiku 4.5).

Dat is een keuze en geen restant: die vier paden schrijven tekst op basis van al
geclassificeerde bevindingen en vellen zelf geen oordeel over bewijs. Het duurdere model kopen
voor een samenvatting levert geen beter auditoordeel op.

De UI-kaart zei tot 2026-08-20 "Classificatie en memo-tekst" en dat was te ruim — de memo-tekst
volgt de keuze niet. De kaart zegt nu "Classificatie van bevindingen", met eronder expliciet dat
memo-tekst en rapportgeneratie altijd op Haiku draaien. Dat is dezelfde soort valse belofte als
de zes die op 16, 17 en 18 augustus zijn weggehaald: een scherm dat meer belooft dan de code
doet.
