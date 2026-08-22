---
status: current
last_reviewed: 2026-08-22
---

# Vraagassistent — de Bronbevrager

Eén vraag, één antwoord, uitsluitend uit wat dit tool heeft ingelezen. Het scherm staat onder
**Vragen** in het portaal, achter dezelfde auth-gate als de rest.

De Bronbevrager is de eerste van vier agents uit change `iso-agents`; de Normuitlegger, de
Gap-analist en de Opsteller volgen. De scheiding tussen die vier is op **bronregel** en niet op
onderwerp: een agent die niet uit ons corpus put, kan ook niet per ongeluk als bewijs gelden.

## Het corpus

Vier bronnen, alle vier al doorzoekbaar zonder nieuwe index:

| bron | ingang |
|---|---|
| documentenlandschap | `clause_matches` bij een clausule, anders `documents_fts` (FTS5) |
| bevindingen en audithistorie | `bevindingen` |
| opvolgpunten | `bevindingen` met herkomst `<bron>-opvolging` |
| normteksten | `data/normteksten.lookup()` — interpretatie en bewijslast |

**Clausule eerst.** Bevat de vraag een clausule (`8.24`, "clausule 5.27"), dan is
`clause_matches` de ingang: dat is een exacte koppeling die de pipeline zelf heeft gelegd.
Zoeken op "encryptie" vindt documenten die het woord bevatten; zoeken op 8.24 vindt de
documenten die het tool aan die eis heeft gekoppeld — inclusief die waar het woord niet in
staat. Alleen zonder clausule valt het ophalen terug op FTS5.

**Geen embeddings.** Semantisch zoeken vindt dingen die FTS5 mist, maar het is een tweede
administratie die uiteenloopt met de eerste zodra iemand vergeet hem bij te werken. Blijkt
trefwoordzoeken te grofmazig, dan is dat een meting en een volgende change.

**Er zit een bovengrens op.** Maximaal twaalf documenten, bevindingen en opvolgpunten gaan mee.
Niet om tokens te sparen maar om het antwoord bruikbaar te houden: een lijst van negentig
documenten bij clausule 5.1 levert een antwoord dat alles noemt en niets aanwijst. Wordt er
afgekapt, dan staat dat in het antwoord én in de trail — een lijst die stil op twaalf stopt
leest als "dit is alles".

## Waarom hij niet uit modelkennis antwoordt

Het model kent ISO 27001 en 9001 uit zijn training. Een antwoord zonder bron van Conduction is
voor een audit waardeloos: niet natrekbaar, terwijl het op bewijs lijkt. Een markering als
"dit is algemene kennis" lost dat niet op — die klopt vandaag en over een jaar staat er
onnatrekbare tekst in een audittool.

Twee harde maatregelen, want de systeem-prompt is een instructie en geen garantie:

1. **Leeg corpus, geen aanroep.** Levert het ophalen niets op, dan gaat er geen vraag naar het
   model en komt er een vaste tekst terug ("dit staat niet in de bronnen die ik kan zien"). Een
   antwoord zonder bronnen kan per definitie niet uit de bronnen komen, en dat is met een `if`
   af te dwingen in plaats van met een verzoek.
2. **Verwijzingen worden nagelopen.** Het antwoord verwijst met `[bron:<id>]`. Elk id moet in
   het meegegeven corpus voorkomen, en elke clausule die het antwoord noemt moet in een
   meegegeven bron zitten. Klopt dat niet, dan is het een **storing** en geen antwoord. Ook een
   afgekapt antwoord (`stop_reason: max_tokens`) is een storing: bij afkapping verdwijnt juist de
   bronvermelding aan het eind.
3. **Een antwoord zonder énige verwijzing wordt vervangen.** Niet geweigerd en niet getoond met
   een waarschuwing: de auditor ziet een vaste tekst, en de prose van het model gaat alleen naar
   de trail. Zie hieronder.

### Waarom vervangen en niet weigeren

Een antwoord zonder verwijzing kan twee dingen zijn: een eerlijk "dit staat niet in deze bronnen",
of een bewering uit modelkennis. **Van buitenaf is dat onderscheid niet te maken.** Drie vormen
zijn geprobeerd:

| aanpak | uitkomst |
|---|---|
| weigeren (502) | twee van drie echte vragen faalden terwijl het model correct antwoordde |
| een merkteken dat het model zet | werkt zolang het model zich eraan houdt — tegen het echte model deed het dat niet |
| **vervangen** | dekt beide gevallen, hangt niet af van medewerking |

Het merkteken `[niets-gevonden]` staat nog wel in de prompt: het helpt, maar de handhaving zit in
de vervanging.

### Vormvarianten die het model gebruikt

Het model groepeert verwijzingen op manieren die een naïeve parser als verzonnen leest. Alle drie
gevonden tegen het echte corpus, elk keer met geldige ID's die werden afgewezen:

- `[bron:a, b, c]` — komma-lijst binnen één merkteken
- `[bron:a en b]` — het Nederlandse "en" als scheidingsteken
- `[bron:a, bron:b]` — het voorvoegsel herhaald binnen één merkteken

De splitsing gebruikt woordgrenzen, zodat een ID dat "en" bevat (`1eDQv1pQ8r2Sv...`) heel blijft.
Tolerant voor de vorm, niet voor de inhoud: élk los ID moet in het corpus zitten.

Die tweede is het verschil tussen "we hebben het gevraagd" en "we hebben het gecontroleerd" —
dezelfde discipline als bij de classificatie, waar een onleesbaar of afgekapt antwoord sinds
2026-08-17 ook geen leeg oordeel meer is.

## "Staat er niet in" — met de reden erbij

Drie uitkomsten die verschillende dingen betekenen, en één tekst zou ze alle drie toedekken:

| geval | antwoord |
|---|---|
| de clausule bestaat niet in deze norm | dat wordt gezegd, met een suggestie als er een clausule met dezelfde cijferreeks bestaat |
| de clausule bestaat, er is niets aan gekoppeld | de normtekst met `bewijslast` gaat mee — een dekkingsgat is een auditbevinding in de dop, geen leeg antwoord |
| geen clausule in de vraag, tekstzoekopdracht leeg | de algemene "staat er niet in" |

De suggestie is een cijfervergelijking en geen gelijkenis-maat: `8.2.4` en `8.24` hebben
dezelfde cijferreeks zonder punten, dus dat is een kandidaat. Bewust geen drempel — "0.83 leek
genoeg" is geen antwoord aan een auditor, dezelfde weigering als bij de dedup-sleutel in
`api/runs.py`.

Dit staat er omdat de eerste echte vraag in het portaal (2026-08-21) `8.2.4` was. Die clausule
bestaat niet in ISO 27001:2022; Annex A kent `8.24`, en daar hingen 24 documenten aan. Het
antwoord "staat er niet in" was juist en hielp niemand.

## Waarom er niet geciteerd wordt

De assistent parafraseert en verwijst: clausule-ID, documentnaam, en een link naar het
landschapsscherm.

Voor normtekst is dat een licentiekeuze — `data/normteksten/` bevat bewust verkorte eisen, en
letterlijke ISO-tekst doorgeven aan een gebruiker is een andere handeling dan die tekst intern
gebruiken om te classificeren. Voor eigen documenten zou citeren mogen, maar dan zijn er twee
regels in plaats van één, en een regel die per bron verschilt wordt op den duur verkeerd
toegepast.

Gevolg dat in het scherm staat: **het antwoord is een aanwijzing naar bewijs, niet het bewijs
zelf.** De auditor opent het document.

## Tegenspraak wordt benoemd, niet opgelost

Spreken bronnen elkaar tegen — een document dat dekking claimt terwijl een eerdere bevinding een
NC noemt — dan gaan ze beide mee met hun herkomst, en constateert de assistent dat ze niet
overeenkomen. Hij kiest niet en rangschikt niet.

Een regel als "nieuwste wint" zou precies de interessantste uitkomst verbergen: een oud NC dat
nooit is afgesloten verdwijnt dan achter een nieuw document. Daarom benoemt de systeem-prompt
tegenspraak expliciet als geldige uitkomst — zonder dat lost het model het stil op door één
bron te negeren.

## Hij velt geen oordeel

De assistent maakt geen bevinding aan, stelt geen triage voor en raakt de werkset niet.
Vraagt de auditor of iets een afwijking is, dan komt het bewijs en de eerdere oordelen met hun
bron terug; de auditor beslist.

De auditor-spiegel is de capability die dit tool draagt: op vaste punten houdt een mens het
oordeel. Een assistent die een concept-NC oppert schuift dat oordeel richting het model, en een
concept dat er al staat wordt bevestigd in plaats van gevormd.

## Wat er in de trail komt

Tabel `assistent_vragen`, append-only, per vraag één rij: de vraag, het antwoord, de bron-ID's
die aan het model meegingen, welke daarvan in het antwoord terugkomen, het model, en de kosten
met peildatum en prijsgrondslag.

**Ook een storing wordt vastgelegd**, met de reden en zonder antwoord. Dat is het enige spoor
dat de verwijzingscontrole heeft gewerkt.

De meegegeven bron-ID's zijn het punt waarop een antwoord later na te trekken is: een antwoord
dat achteraf verkeerd blijkt, is alleen te begrijpen als je weet wat de assistent op dat moment
kon zien.

## Wat er niet is

- **Geen gesprek.** Eén vraag, één antwoord. Een gesprek maakt van het vorige antwoord een bron
  voor het volgende, en dan is niet meer te zeggen waar een bewering vandaan kwam.
- **Geen vragen tijdens een run.** De route geeft 409 zolang er een run loopt: een vraag tijdens
  een run leest een halve werkset, en het antwoord zou een dekking suggereren die pas na de run
  bestaat.
- **Niet openbaar.** Het corpus bevat auditbevindingen en interne memo's. Openstellen voor
  medewerkers of externen is een publicatiebesluit met een eigen afweging.

## Model en budget

Volgt de modelkeuze uit het configuratiescherm (`AUDIT_CLASSIFICATION_MODEL`), met
`thinking` expliciet uit — weglaten maakt het gedrag afhankelijk van het model, en dat leverde
op 2026-08-17 stil nul bevindingen op twee van de drie modellen.

Het output-budget (2000 tokens) is op de langste variant gezet en niet op de gemiddelde. Bij een
krap budget kapt het antwoord af, en wat er dan als eerste sneuvelt is de bronvermelding aan het
eind — precies het deel dat dit antwoord bruikbaar maakt.
