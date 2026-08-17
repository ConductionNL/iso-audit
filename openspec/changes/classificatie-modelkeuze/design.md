# Design — classificatie-modelkeuze

## Thinking expliciet uitzetten, niet aanzetten

De classificatie krijgt `thinking={"type": "disabled"}` mee, niet adaptive thinking.

Overwogen en verworpen: thinking aanzetten omdat het oordeel er beter van wordt. Dat is
waarschijnlijk waar, maar het is een aparte beslissing met een eigen prijskaartje, en die
hoort uit een meting te komen — niet uit een bugfix. Deze change maakt de modelkeuze
*werkend*; of thinking aan moet, is de volgende vraag.

Expliciet uitzetten heeft bovendien een eigenschap die impliciet weglaten mist: het gedrag
verandert niet meer als iemand een ander model kiest. Dat is precies de val die deze change
opruimt, en die zou terugkomen bij het volgende model dat een andere default heeft.

**Let op bij een latere overstap naar thinking-aan:** op Claude Opus 5 mag
`thinking: disabled` alleen bij effort `high` of lager — de combinatie met `xhigh`/`max`
geeft een 400. Deze change zet geen `effort`, dus dat speelt nu niet; wie het later
toevoegt moet het wél weten.

## Het tekstblok opzoeken, niet aannemen

`resp.content[0].text` wordt een zoekactie naar het eerste blok met `type == "text"`.

Dat is nodig ook mét thinking uitgezet: de aanname "het eerste blok is tekst" is niet
gegarandeerd door de API en klopt al niet zodra er een thinking-blok, een tool-blok of een
toekomstig bloktype voor staat. Eén helper, gebruikt door beide classificatiepaden (doc en
Miro), zodat de fout niet op één plek wordt gerepareerd en op de andere blijft staan.

## Een lege parse is een fout

`_parse_json_list("")` returnt nu stil een lege lijst. Dat blijft geldig voor een respons
die écht geen array bevat maar wel tekst — daar is een lege uitkomst een oordeel.

Wat verandert is de laag erboven: een aanroep die tokens verbruikte en waaruit **geen
tekstblok** te halen was, is een storing. Die telt mee in `teller.fouten` en krijgt een
logregel met de reden. Zo is het onderscheid dat nu ontbreekt — "het model vond niets" versus
"we konden het antwoord niet lezen" — terug in de trail.

Overwogen: hard falen (exception) in plaats van tellen en doorgaan. Verworpen omdat één
onleesbaar document een run van 400 documenten niet hoort af te breken; de foutenteller en
het run-record maken het zichtbaar, en `run_record.fout` bestaat al.

## Output-budget: ruimte laten en de reden erbij

`max_tokens = 150 * len(clausule_ids) + 64` blijft de basis met thinking uit. Het getal is
niet willekeurig — 150 tokens per clausule is de begroting voor een beschrijving van maximaal
80 woorden plus de onderbouwing — en dat hoort in een comment te staan, want zonder die
uitleg is het een magisch getal dat niemand durft aan te raken.

Wordt thinking later aangezet, dan moet dit budget mee omhoog: `max_tokens` begrenst op deze
modellen thinking én antwoord samen. Dat staat als waarschuwing bij de constante, niet in een
losse doc, omdat dit de plek is waar iemand het nodig heeft.

## Kosten: vullen wat er al is

`usage_json` in `classifications` bestaat en `_usage_dict(resp.usage)` wordt al meegegeven
aan `log_classification`. Er is dus geen schema-wijziging nodig — alleen uitzoeken waarom de
kolom leeg blijft. Dat is een bug, niet een feature, en de taak is het te vinden en te
bewaken met een test.

Het run-record krijgt daarnaast de totale kosten met `PRIJZEN_PEILDATUM` **en de
prijsgrondslag** erbij. Een bedrag zonder die twee is niet navertelbaar: prijzen wijzigen
buiten deze repo om, en lijstprijs is niet hetzelfde als wat er gefactureerd wordt.

## Prijsgrondslag benoemen in plaats van kiezen

De tabel krijgt een expliciet veld dat zegt wat de tarieven zijn: lijstprijs of werkelijk
tarief inclusief tijdelijke acties.

Bewust geen automatische introtarief-logica met einddatums. Dat is een tweede administratie
die achterloopt op de leverancier, precies wat `PRIJZEN_PEILDATUM` moet voorkomen. Eén
handmatig bijgehouden tabel met een peildatum en een benoemde grondslag is saai en
controleerbaar; een tabel die zelf datums evalueert is dat niet.

Welke grondslag we kiezen is een vraag voor de opdrachtgever, niet voor deze change. De
change maakt zichtbaar wélke het is.

## Buiten scope: welk model het beste is

Deze change kiest geen model. Dat hoort uit een meting: dezelfde run op Haiku 4.5 en op
Sonnet 5, triage vergeleken met de referentie-output van juni in
`~/projects/iso-audit/output/audit_reports/`. Zonder gevulde `usage_json` is die vergelijking
alleen op kwaliteit te maken en niet op prijs — daarom komt de kostenregistratie in deze
change en de modelvergelijking daarna.
