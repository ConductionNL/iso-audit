# Design — iso-vraagassistent

## Ophalen met wat er al staat

De vier bronnen zijn alle vier al doorzoekbaar. Geen nieuwe index, geen embeddings, geen
vector-store:

- **Documenten** — `documents_fts`, een FTS5-tabel met triggers die hem bijhoudt
  (`store.py:192`). Trefwoordzoeken over naam en tekst.
- **Clausule-koppelingen** — `clause_matches`, waarmee "welke documenten raken 8.24" een
  query is en geen zoekopdracht.
- **Normteksten** — `data/normteksten.lookup(norm, clausule)`, een directe opzoeking.
- **Bevindingen en trail** — `bevindingen` en `decisions`.
- **Opvolgpunten** — via `sources/opvolgpunten.py`, dezelfde weg die de pipeline gebruikt.

Overwogen en verworpen: semantisch zoeken met embeddings. Dat vindt dingen die FTS5 mist, en
het is een tweede administratie die uiteenloopt met de eerste zodra iemand vergeet hem bij te
werken. Blijkt trefwoordzoeken in de praktijk te grofmazig, dan is dat een meting en een
volgende change — geen aanname vooraf.

## Clausule eerst, dan tekst

De ophaalstrategie is tweetraps en de volgorde is niet willekeurig. Bevat de vraag een
clausule (`8.24`, `10.2`, "clausule 5.27"), dan is `clause_matches` de ingang: dat is een exacte
koppeling die de pipeline zelf heeft gelegd. Alleen zonder clausule valt hij terug op FTS5.

Waarom die volgorde: een auditor vraagt meestal per clausule, en de koppeling is preciezer dan
elke tekstmatch. Zoeken op "encryptie" vindt documenten die het woord bevatten; zoeken op 8.24
vindt de documenten die het tool aan die eis heeft gekoppeld — inclusief die waar het woord niet
in staat.

## Geen citaat, dus wat dan wel

Een antwoord verwijst met clausule-ID, documentnaam en een link naar het document in het
landschapsscherm (`#/landschap`, dat al een zoekveld heeft). De assistent parafraseert.

Voor normtekst is dat een licentiekeuze: `data/normteksten/` bevat bewust verkorte eisen, en
letterlijke ISO-tekst doorgeven aan een gebruiker is een andere handeling dan die tekst
intern gebruiken om te classificeren. Voor eigen documenten zou citeren mogen, maar dan zijn er
twee regels in plaats van één — en een regel die per bron verschilt, wordt op den duur
verkeerd toegepast.

Consequentie die in de UI moet staan: het antwoord is een aanwijzing naar bewijs, niet het
bewijs zelf. De auditor opent het document.

## Wat "niet in het corpus" betekent voor de prompt

Het model kent ISO. Het weigeren moet dus uit de prompt komen, en dat is de kwetsbaarste plek
in deze change: een systeem-prompt die zegt "antwoord alleen uit de meegegeven bronnen" is een
instructie, geen garantie.

Twee maatregelen bovenop de instructie:

1. **De bronnen gaan expliciet mee** in de user-prompt, met hun herkomst erbij. Een antwoord
   dat naar een bron verwijst die niet in die lijst staat, is per definitie verzonnen.
2. **De verwijzingen worden nagelopen** vóór het antwoord de auditor bereikt: elke
   clausule-ID en elk document-ID in het antwoord moet voorkomen in wat er is meegegeven.
   Klopt dat niet, dan is het antwoord een storing en geen antwoord — dezelfde regel als bij
   de classificatie (zie `openspec/changes/classificatie-modelkeuze/`).

Die tweede is het verschil tussen "we hebben het gevraagd" en "we hebben het gecontroleerd".

## Thinking, model en budget

Expliciet `thinking: disabled` en het tekstblok opzoeken via
`classification/respons.py:tekst_uit`, om precies de reden die daar staat: weglaten van de
parameter maakt het gedrag afhankelijk van het gekozen model, en dat leverde op 2026-08-17 stil
nul bevindingen op twee van de drie modellen.

Het model volgt de bestaande modelkeuze (`KIESBARE_MODELLEN`). Uit de meting van 2026-08-17
blijkt dat prijs bij dit volume geen argument is — $0,79 tot $3,95 voor 215 classificaties —
dus er is geen reden om hier een goedkoper model te forceren dan de auditor voor de rest kiest.

Het output-budget is ruimer dan bij de classificatie: een antwoord met verwijzingen is langer
dan een JSON-bevinding van 80 woorden. Bij een krap budget kapt het antwoord af en verliest het
juist de bronvermelding aan het eind — dus het budget hoort bij de langste variant te passen,
niet bij de gemiddelde.

## Tegenspraak is een uitkomst, geen fout

Bronnen die elkaar tegenspreken worden beide getoond met hun herkomst, plus de constatering dat
ze niet overeenkomen. De assistent kiest niet en rangschikt niet.

Dat vraagt iets van de prompt en van de UI: de prompt moet tegenspraak expliciet als geldige
uitkomst benoemen (anders lost het model het stilletjes op door één bron te negeren), en de UI
moet twee bronnen naast elkaar kunnen tonen zonder dat de ene als het antwoord leest.

## Trail: vraag, antwoord en de bronnen

Append-only, naast `decisions` en `classifications`. Vastgelegd worden: de vraag, het antwoord,
de bron-ID's die zijn meegegeven, welke daarvan in het antwoord terugkomen, het model, en de
kosten met peildatum en grondslag.

Die vierde — welke bronnen zijn meegegeven — is het punt waarop dit later na te trekken is. Een
antwoord dat achteraf verkeerd blijkt, is alleen te begrijpen als je weet wat de assistent op
dat moment kon zien.
