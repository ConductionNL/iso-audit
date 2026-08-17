---
status: current
last_reviewed: 2026-08-17
---

# Modelkeuze en kosten

Welk Claude-model de classificatie gebruikt, kiest de auditor in het configuratiescherm. Wat
die keuze betekent — en wat er níet bij hoort — staat hier.

## Kiesbare modellen

`KIESBARE_MODELLEN` in `classification/findings.py`. Elk model hier moet een prijsregel hebben;
`tests/config/test_modelkeuze.py` faalt anders, want een model zonder prijsregel draait met een
kostenpost van nul en dat ziet in een auditrapport compleet uit.

| model | invoer | uitvoer | cache-read | cache-minimum |
|---|---|---|---|---|
| Haiku 4.5 | $1,00 | $5,00 | $0,10 | 4096 tokens |
| Sonnet 5 | $3,00 | $15,00 | $0,30 | 1024 tokens |
| Opus 5 | $5,00 | $25,00 | $0,50 | 512 tokens |

Bedragen per miljoen tokens, peildatum in `PRIJZEN_PEILDATUM`.

## Prijsgrondslag: lees `PRIJZEN_GRONDSLAG`

De tabel staat op **lijstprijs**. Dat is niet altijd wat er gefactureerd wordt: Sonnet 5 had
op 2026-08-17 een introductietarief van $2,00/$10,00 tot en met 31 augustus 2026, een derde
onder de lijstprijs. Een gerapporteerd bedrag voor dat model valt dus hoger uit dan de factuur.

Wil de opdrachtgever werkelijke kosten in het rapport, dan is dat een waardewijziging in
`PRIJZEN` plus `PRIJZEN_GRONDSLAG`, geen codewijziging. Er zit bewust **geen datumlogica** in
de tabel die zelf tussen tarieven kiest: dat zou een tweede administratie zijn die achterloopt
op de leverancier, precies wat de peildatum moet voorkomen.

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

`memo/draft.py`, `classification/thema.py` en `reporting/report_generation.py` hardcoderen
`claude-haiku-4-5-20251001`. De keuze in de UI gaat alleen naar `classification/findings.py`.

De UI-kaart zegt "Classificatie en memo-tekst", en dat is dus te ruim: de memo-tekst volgt de
keuze niet. Bekend, niet opgelost — uitbreiden of de kaarttekst aanpassen is een aparte
afweging.
