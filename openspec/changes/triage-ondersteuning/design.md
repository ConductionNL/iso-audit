# Design — triage-ondersteuning

## Herkennen van eigen output: een merkteken, niet een naam

De twaalf bestanden zijn op naam te vinden (`Auditrapport_`, `Bevindingen_`, `Auditmemo_`), en
dat is precies waarom het geen naamregel moet worden. Twee redenen:

1. **Namen wijzigen.** Iemand slaat het rapport op als `Auditrapport def.docx` en het telt weer
   mee, stil.
2. **Valse treffers.** `Auditrapport 2022.docx` staat in het landschap en is niet van ons —
   dat is een rapport van de certificerende instantie, en dat is juist bewijs.

Daarom een **merkteken in het document zelf**, gezet door `schrijf_rapport` en de memo-render:
één regel in de kop, en voor de binaire formaten een documenteigenschap. Bij het inlezen wordt
daarop gefilterd.

Dat is dezelfde regel die het `iso-agents`-voorstel al voor de Opsteller vastlegde ("een
merkteken dat meereist met het document, in de bestandsinhoud, niet alleen in de UI"). Hier
komt hij eerder van pas dan verwacht.

**Bestaande bestanden hebben dat merkteken niet.** Voor de twaalf die er nu staan is een
eenmalige, expliciete lijst nodig — met een datum en een reden erbij, niet als permanente
naamregel. Zodra de rapporten opnieuw geschreven worden, dragen ze het merkteken zelf.

## Vier formaten van hetzelfde rapport

`Auditrapport_beide_v3.3_2026-05-05` staat in md, docx, html en pdf; `Bevindingen_beide_v3.3`
in csv en xlsx. Dat is geen apart probleem: met laag 0 vallen ze alle zes weg. Maar het is wel
een aanwijzing dat de exportstap alle formaten naar dezelfde map schrijft, en dat het landschap
die map leest. Buiten de scope hier — het hoort bij de vraag waar rapporten landen.

## Samenvouwen: exact, en zichtbaar

Sleutel: `(clausule_id, norm, genormaliseerde beschrijving)`, met dezelfde normalisatie als
`runs.dedup_sleutel` (lowercase, whitespace-collaps). Niets meer: interpunctie strippen of
synonymen matchen maakt de regel onuitlegbaar.

De samengevouwen regel toont het aantal en de brondocumenten. Weglaten van dat aantal zou de
werklijst korter maken en de waarheid armer — een bevinding die uit vier documenten komt, weegt
anders dan een die uit één komt.

## De agent: wat hij mag zien en wat hij oplevert

Hergebruikt de Bronbevrager uit `iso-agents`: dezelfde bronregel, dezelfde
verwijzingscontrole, dezelfde weigering om uit modelkennis te antwoorden. Per clausule krijgt
hij de `bewijslast` uit `data/normteksten`, de gekoppelde documenten, de bevindingen en de
opvolgpunten.

Hij levert per clausule op:

| veld | wat het is |
|---|---|
| `bewijs_aanwezig` | welke items uit `bewijslast` gedekt zijn, met verwijzing |
| `bewijs_ontbreekt` | welke niet — een constatering, geen NC |
| `tegenspraak` | bronnen die elkaar tegenspreken, beide genoemd |
| `waarom_nu` | waarom deze clausule aandacht verdient |

**Geen `voorstel`-veld.** Dat is de hele grens: zodra er een voorgestelde klasse in het model
zit, is de auditor aan het bevestigen in plaats van aan het beoordelen. De Gap-analist uit
`iso-agents` heeft dezelfde regel, en die twee moeten dezelfde blijven — anders is er een
tweede oordeelspad met een ander antwoord op dezelfde vraag.

## Ordenen is een uitspraak over aandacht

De werklijst sorteren op "waar valt de meeste onduidelijkheid weg" is een agent-uitspraak, en
die is niet controleerbaar zoals een verwijzing dat is. Daarom: de ordening is **zichtbaar en
omkeerbaar** — de auditor ziet waarom iets bovenaan staat en kan terug naar clausule-orde. Een
onzichtbare ordening is een oordeel dat zich voordoet als een lijst.

## Wat dit kost

Laag 0 en 1 kosten niets en verlagen de classificatiekosten: 462 bevindingen minder betekent
ook minder documenten om te classificeren. De agent kost per clausule één aanroep — bij 86
clausules en de tarieven van 2026-08-20 is dat onder een euro.
