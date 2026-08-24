# Componenten splitsen: één kapot onderdeel is geen belemmering

## Waarom

Op 2026-08-24 ging het drie keer mis, en drie keer nam één onderdeel iets anders mee:

| wat er stuk was | wat er niet meer werkte |
|---|---|
| geen Chrome in het image | de PDF ontbrak stil bij **elke** run, maanden lang |
| één koppelteken in een FTS5-query | de vraagassistent **en** het documentenzoekscherm gaven een 500 |
| twee schrijvers op `findings.json` | een halve werkset bij lezen, en een bevinding die niet te triageren was |

Alle drie zijn nu gerepareerd. Wat blijft is de vorm: het portaal is één proces met één
geheugenlimiet, één afhankelijkheidsboom en één faalvlak. De renderer die 350 MiB en 17 seconden
kost draait in hetzelfde proces als de API die een vraag moet beantwoorden. De run-worker
schrijft in hetzelfde bestand als het verzoek dat op dat moment triageert. Een `readOnlyRootFilesystem`
belet ons om ook maar één regel in productie te patchen, dus elke reparatie is een image en een
uitrol — vandaag drie keer gedaan.

**De architectuur heeft dit al deels voorzien.** `iso_audit.sources`, `.sinks` en `.notifiers`
zijn protocol-lagen met een echte grens: Nextcloud erbij zetten kostte geen enkele wijziging aan
de pipeline, en dat is het bewijs dat die grens werkt. Wat géén grens heeft is de rest: de
rapportketen, de assistent, de triage-werkset en de run-worker zitten allemaal rechtstreeks aan
het portaalproces.

## Wat er verandert

**Eerst de graaf, dan de knipbeslissing.** Welke module hangt aan welke, waar zit gedeelde
toestand, en welke paden raken hetzelfde bestand of dezelfde tabel. Dat is nu nergens
vastgelegd en het is met de code in de hand uit te rekenen — geen ontwerpsessie maar een meting.
Zonder die graaf is elke splitsing een gok over waar de koppeling zit.

**Daarna één component eruit, gemeten.** Niet vier tegelijk. De kandidaat met de sterkste zaak is
de **rapportketen**: hij heeft een duidelijke invoer (de werkset) en uitvoer (bestanden), hij is
de zwaarste (350 MiB, 17 s), hij hoeft nooit op een verzoek te antwoorden, en zijn falen is
vandaag al zichtbaar als "het rapport is er niet" in plaats van "het portaal is stuk". Als één
splitsing niet lukt bij deze, lukt geen enkele.

**De werkset is de moeilijkste en komt niet eerst.** `findings.json` wordt door de run-worker en
door elk triage-verzoek geschreven. Dat is nu opgelost met een bestandsslot en atomair schrijven,
en dat werkt ook tussen processen — bewust zo gekozen. Maar zodra de werkset door twee
deployments wordt gedeeld, is een gedeeld bestand op een PVC de zwakke schakel, en dan is de
vraag of de werkset niet naar de database moet. Dat is een eigen change.

**Per component: een contract en een faalmodus op papier.** Wat gaat erin, wat komt eruit, en wat
ziet de auditor als dit onderdeel er niet is. Die laatste vraag is de hele opbrengst van deze
change: "PDF-conversie mislukt" hoort geen `logger.warning` te zijn maar een zichtbare
onbeschikbaarheid van één functie.

## Wat er niet verandert

- **De protocol-lagen blijven zoals ze zijn.** Ze werken; ze zijn het model voor de rest.
- **Geen Kubernetes-operator, geen servicemesh, geen queue-broker** zolang niet gemeten is dat
  het nodig is. Een tweede deployment met een HTTP-contract is de saaie stap.
- **De auditgrenzen blijven.** Append-only trails, één identiteit per handeling, geen stille
  fallbacks. Componenten splitsen mag daar niets aan versoepelen — een deelbaar systeem met een
  onduidelijke trail is een achteruitgang.

## Wat dit oplevert, concreet

Vandaag: de assistent geeft een 500 → de auditor ziet een kapot scherm. De PDF-renderer valt om →
niemand weet het. Een run schrijft → triage kan een beslissing kwijtraken.

Na de splitsing: de assistent is onbeschikbaar en dat staat op het scherm, terwijl triage
doorgaat. De renderer is onbeschikbaar en het rapport meldt dat, terwijl de bevindingen kloppen.
Dat is niet minder falen maar zichtbaar en begrensd falen — en dat is precies wat een audittool
van zichzelf moet kunnen aantonen.
