---
status: current
last_reviewed: 2026-08-21
---

# Run-historie: wat er in de trail staat, en wat je ermee kunt

`runs.jsonl` per audit, append-only. Eén run levert minstens twee regels op: een startrecord dat
het runnummer reserveert, en een afsluitrecord met de uitkomst. Er wordt nooit iets herschreven.

## Waarom twee records en geen update

Tot 2026-08-14 las de route de uitkomst direct nadat de worker-thread was gestart — dus altijd
`(0, 0)` — en schreef `status: "klaar"`. Elk live-run-record beweerde daardoor permanent "klaar,
0 toegevoegd", geschreven vóórdat er iets gelezen was. Append-only betekent dat je dat niet meer
kunt rechtzetten; vandaar dat de uitkomst eigendom is van de worker, die zijn eigen
afsluitrecord schrijft.

Lezers gebruiken `samengevat()`: dat legt de records per `run_id` over elkaar heen (laatste wint
per veld) en levert de stand op die de UI toont. `lijst()` blijft de ruwe waarheid.

## Wat er in een afgerond record staat

    "toegevoegd": 901, "overgeslagen": 0, "status": "klaar",
    "kosten":  {"usd": 0.6958, "model": "claude-haiku-4-5", "calls": 119, "fouten": 0,
                "peildatum": "2026-08-20", "grondslag": "werkelijk tarief"},
    "dekking": {"gezien": 502, "gelezen": 439, "niet_gelezen": 63,
                "overgeslagen": {"<reden>": <aantal>, ...}}

**Kosten** met model, peildatum én grondslag: een bedrag zonder die drie is niet navertelbaar —
prijzen wijzigen buiten deze repo om, en lijstprijs is niet hetzelfde als wat er gefactureerd
wordt. **Dekking** met aantallen per reden en géén bestandsnamen: die staan in het
handmatige-reviewspoor, en 213 namen per record maakt de trail onleesbaar.

## Een run die "loopt" en niet loopt

Een run leeft in een thread van het portaalproces. Sneuvelt dat proces (podherstart, crash,
deploy), dan schrijft niemand meer een afsluitrecord en blijft het startrecord `loopt` beweren.

Op 2026-08-21 stonden er vier zulke records in één audit: het proces was omgevallen, maar de
historie zei "loopt nog…" alsof er vier runs bezig waren. Daarom sluit het portaal **bij het
opstarten** elke run die nog `loopt` zegt af als afgebroken — bij een verse start kan zo'n run
per definitie niet meer lopen. Append-only: het startrecord blijft staan, er komt een
afsluitrecord bij met de reden.

## Eén run per audit tegelijk

`POST /run/start` weigert een tweede run met **409** zolang er één loopt. Dat is geen
netheidsregel: vier startknoppen binnen twintig seconden maakten op 2026-08-21 vier threads in
één proces, die één niet-thread-safe Google-client deelden — het proces viel om met SIGSEGV. En
vier gelijktijdige ingests betalen viermaal de classificatie van dezelfde documenten.

## Verbergen, niet verwijderen

`POST /audits/<id>/runs/<run_id>/zichtbaarheid` met `{"verborgen": true, "reden": "..."}` haalt
een run uit de **werklijst**. Er wordt niets geschrapt: het is een extra regel met wie het deed,
wanneer en waarom. `GET /runs` blijft alles teruggeven met een `verborgen`-vlag; de UI filtert,
met een schakelaar "toon verborgen (N)".

Waarom geen `DELETE`: een certificerende instantie moet kunnen zien dat er runs zijn geweest die
faalden, en een bestand waaruit regels geschrapt kunnen worden is precies zoveel waard als de
discipline van degene die schrapt.

Waarom het er tóch is: op 2026-08-21 stonden er negen runs in één audit, waarvan vier
weesrecords en drie mislukte pogingen. Zo'n lijst is als werklijst onbruikbaar, en een
onbruikbare lijst wordt genegeerd — een slechtere uitkomst dan een lijst waarin iemand
expliciet, met zijn naam eronder, ruis heeft weggezet.

Twee regels eromheen:

- **Een lopende run kan niet verborgen worden** (409). Dat zou de enige aanwijzing weghalen dat
  er iets bezig is.
- **Wie de run startte blijft staan.** Het zichtbaarheidsrecord zegt wie iets verborg
  (`verborgen_door`), niet wie de run draaide; `door` uit het startrecord wordt niet
  overschreven. Zonder die uitzondering leest de historie alsof de opruimer de run had gedraaid.

Omkeerbaar met `{"verborgen": false}` — ook weer als extra regel.

## Rollen

Het portaal kent nu één rol: wie door de auth-gate komt, is auditor. Verbergen is daarmee niet
rol-gebonden; wat vastligt is de **identiteit** van degene die het deed. Een echt rolmodel
(bijvoorbeeld: alleen een leadauditor mag verbergen) is een aparte change en vraagt eerst een
antwoord op de vraag welke rollen Conduction hier wil onderscheiden.
