# Triage doorwerkbaar maken: eerst niet-tellen, dan ordenen, dan pas een agent

## Waarom

De eerste volledige run leverde **1241 bevindingen** op (901 na dedup en ruisfilter), over 86
clausules en 119 documenten. Met de hand doorwerken is de bottleneck van dit tool: 433 NC's
over 79 clausules, en **53 clausules met meer dan tien bevindingen**. Clausule 8.16 alleen
heeft er 49.

Een agent lijkt dan het antwoord. Maar de meting zegt iets anders — twee derde van het
probleem is deterministisch, en dáár moet het beginnen.

### 37% van de werklijst komt uit onze eigen output

**462 van de 1241 bevindingen zijn afgeleid uit documenten die dit tool zelf heeft
geschreven.** Twaalf van zulke bestanden staan in het landschap:

| bestand | wat het is |
|---|---|
| `Auditrapport_beide_v3.3_2026-05-05` in **.md, .docx, .html én .pdf** | hetzelfde rapport, vier keer geclassificeerd |
| `Bevindingen_beide_v3.3_2026-05-05` in **.csv én .xlsx** | dezelfde bevindingenlijst, twee keer |
| `Auditrapport_beide_2026-03-24_s05.md` | 76 bevindingen — de grootste bron in de hele set |
| `Auditmemo_management_2026-05-06`, `_v3.pdf`, `2026-06-23.pdf` | onze eigen managementmemo's |

De naamvorm is die van `reporting/local_report.schrijf_rapport`: `Auditrapport_<norm>_<datum>`.
Deze bestanden zijn dus in Drive gezet en worden nu als bewijs teruggelezen.

Dat is precies de kringloop die het `iso-agents`-voorstel benoemde voor de Opsteller — "dan
auditeert het tool zijn eigen output" — en hij is er al, niet met gegenereerd beleid maar met
onze eigen rapporten. Voor ISO 27001 raakt dat de onafhankelijkheid van de interne
auditfunctie: een bevinding die als bewijs een eerder auditrapport aanwijst, is geen
onafhankelijke observatie maar een echo.

Nuance die erbij hoort: een auditrapport van de **certificerende instantie** is wél bewijs —
dat is een externe waarneming. Het onderscheid is niet "rapport" maar "van ons of van hen".

### Exacte duplicaten, geen gelijkenis nodig

**264 regels zijn een exact duplicaat** van een eerdere `(clausule, beschrijving)` in dezelfde
set. Niet vaag, niet "0,83 vergelijkbaar" — letterlijk dezelfde tekst op dezelfde clausule.
Die zijn samen te vouwen zonder één drempel, en dat is precies de regel die `api/runs.py` al
aanhoudt: deterministisch in code, geen LLM en geen gelijkenis-drempel.

### Wat er dan nog over is

Na die twee: ongeveer **515 bevindingen** in plaats van 1241. Dan is de vraag pas of een agent
helpt, en waarmee.

## Wat er verandert

**Laag 0 — eigen output telt niet als bewijs.** Documenten die dit tool heeft geschreven,
worden herkend en niet geclassificeerd. Herkenning op een merkteken in het document zelf, niet
op de bestandsnaam: een naam wijzigt, en `Auditrapport 2022.docx` is van een ander en moet
gewoon meetellen.

**Laag 1 — exacte duplicaten samengevouwen.** Eén regel per `(clausule, beschrijving)`, met
het aantal en de bronnen erbij. De auditor ziet dat het uit vier bestanden komt in plaats van
vier keer hetzelfde te lezen.

**Laag 2 — een agent die voorbereidt, niet oordeelt.** Per clausule bundelt hij wat er is: de
`bewijslast` uit de normtekst, de gekoppelde documenten, eerdere oordelen en de opvolgpunten.
Hij benoemt tegenspraak. Hij zet de werklijst op volgorde van "waar valt de meeste
onduidelijkheid weg" — dat is een uitspraak over aandacht, niet over bewijs.

**Wat de agent nooit doet: een triage-status voorstellen.** Geen "dit lijkt valide". De
auditor-spiegel is de capability die dit tool draagt; een concept dat er al staat wordt
bevestigd in plaats van gevormd, en dan is de onafhankelijkheid van de auditor een formaliteit.

## Wat er niet verandert

**Geen gelijkenis-drempel.** Bijna-duplicaten blijven staan. "0,83 leek genoeg" is geen
antwoord aan een auditor, en dezelfde weigering staat al in `runs.dedup_sleutel`.

**Niets wordt verwijderd.** Eigen output en duplicaten verdwijnen uit de werklijst, niet uit
het landschap of de trail — zelfde regel als bij het verbergen van runs.

**De classificatie zelf verandert niet.** Laag 0 en 1 zitten vóór en ná de classificatie, niet
erin.

## Capability-impact

Versterkt de **auditor-spiegel** het meest: een werklijst van 1241 waarvan 37% een echo van
onszelf is, wordt niet doorgewerkt maar afgevinkt. En een agent die voorbereidt zonder te
oordelen houdt het oordeel waar het hoort.

Raakt **onafhankelijke bronnen** direct: onze eigen rapporten zijn geen onafhankelijke bron
over onszelf.

Versterkt **patroondetectie** licht: 53 clausules met meer dan tien bevindingen zijn nu niet te
overzien, en een gebundelde weergave per clausule maakt een patroon zichtbaar dat in een platte
lijst van 1241 regels verdwijnt.
