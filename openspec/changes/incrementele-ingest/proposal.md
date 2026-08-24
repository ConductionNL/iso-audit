# Incrementele ingest: een ongewijzigd document niet opnieuw ophalen

## Waarom

Drie runs op één database, gemeten op 2026-08-24:

| ronde | duur | nieuwe documenten | classificatie-calls |
|---|---|---|---|
| 1 (koud) | 31,2 min | 709 | 118 |
| 2 | 16,4 min | 0 | 0 |
| 3 | 15,9 min | 0 | 0 |

Het dure deel — de modelaanroepen — wordt volledig hergebruikt. Ronde 2 en 3 deden geen enkele
classificatie. Toch duurt een herhaalde run zestien minuten, en die gaan **volledig op aan het
opnieuw ophalen van documenten die niet veranderd zijn**.

Gemeten per bron:

| bron | lijst ophalen | inhoud per document | totaal |
|---|---|---|---|
| Drive | 65 s voor 456 docs | 2,49 s | **1.202 s** |
| Nextcloud | 3,2 s voor 121 docs | 0,55 s | 69 s |

Drive is 95% van de tijd, en het zit niet in de lijst maar in de inhoud: elk document wordt
opgehaald, geëxporteerd en uitgepakt, ook als het sinds de vorige run niet is aangeraakt.

**De gegevens om dat te vermijden zijn er al.** Drive en Nextcloud leveren allebei een
wijzigingstijd voor élk document (559 van de 709 in de gemeten database; de 150 zonder zijn
Planning-rijen uit een sheet). Die tijd wordt opgeslagen in `documents.modified_at` en wordt
vandaag alleen gebruikt om documenten ouder dan twee jaar te archiveren. Ook `ingest_log` wordt
elke run geschreven en nooit gelezen.

## Wat er verandert

**De ingest slaat een document over waarvan de wijzigingstijd niet is veranderd** ten opzichte
van wat er in `documents` staat. De tekst is er al; opnieuw ophalen levert hetzelfde op.

**De listing blijft volledig.** Er wordt niets overgeslagen bij het opsommen — dat is 65 s bij
Drive en het is de enige manier om te merken dat een document is verdwenen of bijgekomen. Alleen
de `fetch_content` wordt overgeslagen.

**De dekkingstelling blijft kloppen.** Een overgeslagen document telt als gezien én gelezen, met
de vermelding dat het uit de vorige run komt. Een document dat stil uit de telling valt omdat het
niet opnieuw is opgehaald, zou de dekking laten dalen zonder dat er iets veranderd is — precies
het soort stille afwijking dat dit tool elders juist bestrijdt.

**Er komt een `--opnieuw-lezen`-schakelaar.** Bij twijfel over de opgeslagen tekst, of na een
wijziging in de lezers (zoals de OpenDocument-lezer van 2026-08-24), moet alles opnieuw kunnen.
Zonder die uitweg is een cache een val.

## Wat er niet verandert

- **De classificatie-cache.** Die werkt al en blijft zoals hij is (`input_hash`).
- **Bronnen zonder wijzigingstijd.** Planning levert er geen; die wordt elke run volledig
  gelezen. Geen geraden tijdstempel — een verzonnen wijzigingstijd is erger dan geen.
- **De twee-jaar-archiefgrens.** Die gebruikt dezelfde kolom voor iets anders en blijft staan.

## Wat dit oplevert

Als de schatting klopt, gaat een herhaalde run van ~16 minuten naar onder de twee: de listing
(68 s) plus het lezen van wat er écht veranderd is. Dat is het verschil tussen "een run draaien
als je iets wil weten" en "een run inplannen".

**Meten, niet aannemen.** De opbrengst hangt af van hoeveel documenten er tussen twee runs
wijzigen, en dat is bij een auditcorpus laag maar niet nul. De change is pas af als er een run
vóór en ná is gemeten, met hetzelfde aantal bevindingen als uitkomst.
