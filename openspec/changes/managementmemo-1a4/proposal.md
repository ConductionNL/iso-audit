# Managementmemo: één tot drie A4, getemplate

## Waarom

De klant stelt een harde eis: **de uiteindelijke audit is één tot drie A4'tjes.** Per
non-conformiteit wil het management vier dingen weten — wat is het, waarom is het een NC, wie
moet er wat aan doen, en voor wanneer. Al het andere is verantwoording en hoort in de bijlage.

Wat het tool vandaag oplevert staat daar ver vandaan. De run van 2026-08-24 schreef een
auditrapport van **320 pagina's** met 903 bevindingen, plus csv, xlsx, docx en html. Dat is de
verantwoording en die is goed zoals hij is — een auditor moet elke bevinding kunnen natrekken.
Maar het is geen memo, en er is nu geen stap die van het een het ander maakt.

Er is wél een commando: `iso-audit memo`. Dat weigert op de huidige dataset:

> `fout: Clausule '10.3' ontbreekt in iso-9001-2015. Vul de norm-DB aan; een memo mag geen
> verzonnen citaat bevatten.`

Die weigering is terecht en blijft. Maar hij legt bloot dat de norm-DB waar het commando naar
wijst **13 clausules** bevat (4 voor 9001, 9 voor 27001) terwijl de bevindingen er **87** raken.
De repo bevat bewust geen normtekst; dat is een licentiekeuze en geen omissie. Het gevolg is wel
dat de memo-stap in de praktijk nooit gedraaid is.

## Het doelbeeld ligt er al

`Auditmemo_management_2026-06-23.pdf` (Q2 2026, twee A4) is met de hand gemaakt en is precies
wat er geautomatiseerd moet worden. De structuur:

1. **Kop** — titel, auditor met rol, datum.
2. **Aanhef, vier regels.** Ruwe telling ("61 NC, 156 OFI en 89 positieve bevindingen"), dan wat
   er na curatie overblijft ("2 non-conformiteiten en een reeks verbeterpunten"), een verwijzing
   naar de detailrapportage, en de zin die de rest van de memo verantwoordt: *"Deze memo bevat
   enkel de acties."*
3. **Per NC een blok** met een themanaam ("NC 1 — Bedrijfscontinuïteit & redundantie"):
   - de onderliggende bevindingen als bullets, elk met bronverwijzing (`ISO-746`), documentnaam
     en clausule;
   - één synthese-alinea die zegt wat het gemeenschappelijke gebrek is — *"Drie clausules, één
     hoofdgebrek: er is geen gedocumenteerd en getest continuïteitsbeheer"*;
   - een actietabel **Wat | Wie | Waar | Uiterlijk**;
   - een normregel: `Norm: ISO 27001:2022 §8.14 / §5.29 / §5.30`.
4. **Verbeterpunten** in één tabel (Onderwerp | Actie | Norm), met de zin die hun status bepaalt:
   "Geen managementbesluit nodig, wel opvolging."
5. **Voetregel** — auditor, datum, verwijzing naar de detailrapportage.

**Het interessantste getal in dat voorbeeld is de compressie: 61 ruwe NC's werden 2 genummerde
NC's.** Dat is geen filtering maar synthese — drie bevindingen op drie clausules die één gebrek
beschrijven, samengevat als één besluit met drie acties. Een sjabloon alleen levert dat niet op.

## Wat er verandert

**Een memo-sjabloon dat exact deze vorm produceert**, gevoed uit de werkset (`findings.json`),
de triage-status en de norm-DB. Alleen `triage_status == "valide"` gaat mee; dat is de bestaande
regel in `memo/builder.py` en die blijft.

**Een paginabudget dat afdwingbaar is.** Het sjabloon MOET binnen drie A4 blijven en de generatie
meldt het als dat niet lukt, met wat eruit gelaten is. Een memo die stil op vier pagina's uitkomt
is een memo die de klanteis breekt zonder dat iemand het ziet — hetzelfde patroon als de stille
MIME-skips en de verdwenen PDF.

**De acties krijgen velden.** `Wat`, `Wie`, `Waar` en `Uiterlijk` bestaan nu nergens in de
datamodellen; ze zijn met de hand in het Q2-voorbeeld getypt. Ze horen bij de bevinding, worden
door de auditor ingevuld (of door een agent voorbereid — zie `triage-agents`), en zijn de brug
naar voortgangsbewaking (zie `voortgangsbewaking`).

**De groepering van bevindingen naar NC-thema's** is een eigen stap. Deze change legt het
datamodel en het sjabloon vast en laat de groepering met de hand doen; `triage-agents` bouwt de
synthesizer die het voorstelt. In die volgorde, omdat een sjabloon dat je met de hand kunt vullen
te controleren is en een agent-uitvoer zonder sjabloon niet.

## Wat er niet verandert

- **De verantwoording blijft.** De 320 pagina's, de csv en de xlsx zijn de bijlage waar de memo
  naar verwijst. Er gaat niets weg.
- **De weigering bij ontbrekende normtekst blijft.** Een memo mag geen verzonnen citaat
  bevatten. Wel wordt de melding bruikbaar: welke clausules ontbreken, en hoeveel.
- **De auditor blijft beslissen.** Het sjabloon vult niets in wat een oordeel is.

## Wat dit blokkeert

De norm-DB. Zonder clausuleteksten voor de gebruikte clausules komt er geen memo uit, en dat is
opzet. Dit is een inhoudelijke en licentie-afweging die buiten deze change valt en die eerst
gemaakt moet worden — anders levert deze change een sjabloon op dat op de echte dataset weigert.
