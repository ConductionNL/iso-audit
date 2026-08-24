# Autonome review: een tweede model dat vraagt of een bevinding ergens op slaat

## Waarom

De run van 2026-08-24 leverde **800 bevindingen** op (buiten de Jira-opvolgpunten), waarvan
**387 NC's**. Ter vergelijking: in het handgemaakte Q2-memo hield de auditor er **2** over.

De bevindingen zijn niet dubbel — dat is gecontroleerd: slechts 4 van de 800 hebben een
herhaalde beschrijving. Het zijn 85 clausules maal meerdere documenten, gemiddeld 6,8 per
document, met uitschieters van 52 en 50 op één document. Dat is breedte, geen ruis, en breedte is
op zichzelf goed.

Wat er wél mis is:

- **55 OFI's hebben geen beschrijving én geen onderbouwing.** Een oordeel zonder inhoud, dat
  wel meetelt in het rapport. Dat is het "false green"-patroon dat dit project blijft raken.
- **387 NC's is geen werklijst.** De auditor zette op 24 augustus 902 bevindingen in vier
  bulkacties op `valide` — dat is geen triage, dat is capituleren voor het aantal. Bij 387 NC's
  gebeurt precies dat weer.

De classificatie draait op een goedkoop model over honderden documenten; dat is een verdedigbare
keuze voor de eerste zeef. Maar er is nu geen tweede zeef, en de auditor is de enige die het
verschil moet maken tussen "dit document noemt encryptie niet" en "hier ontbreekt aantoonbaar
een beheersmaatregel".

## Wat er verandert

**Een reviewstap tussen classificatie en triage.** Per bevinding beoordeelt een zwaarder model
(Sonnet of Opus) één vraag: *slaat deze bevinding ergens op?* Concreet vier deelvragen:

1. **Is er inhoud?** Een bevinding zonder beschrijving of onderbouwing is geen bevinding.
2. **Past de bevinding bij de clausule?** De koppeling is op zoektermen gemaakt; een document
   dat het woord "toegang" bevat is nog geen bewijs over toegangsbeheer.
3. **Is de klasse verdedigbaar?** Een NC beweert dat er iets ontbreekt. Een document dat over een
   ander onderwerp gaat, toont dat niet aan.
4. **Beschrijft dit hetzelfde gebrek als een andere bevinding op deze clausule?** Niet
   dedupliceren op tekst — dat leverde maar 4 treffers op — maar op *gebrek*.

**De uitkomst is een advies met een reden, geen status.** De auditor ziet per bevinding wat de
review ervan vond en waarom, en beslist zelf. Zelfde grens als in `triage-agents`: een agent die
een status zet, maakt van beoordelen bevestigen.

**Wat er wél automatisch mag: intrekken wat leeg is.** Een bevinding zonder beschrijving én
zonder onderbouwing kan geen oordeel dragen. Die wordt niet weggegooid maar gemarkeerd als
onbruikbaar, met de reden, en telt niet mee in het rapport. Dat is geen inhoudelijk oordeel maar
een vormcontrole — dezelfde soort regel als "een antwoord zonder bronverwijzing is een storing".

**Modelkeuze en kosten per stap in de trail.** De review draait over 800 bevindingen, dus dit is
de duurste stap van de pipeline. Het budget en het model zijn configureerbaar, en de kosten staan
apart in de run-samenvatting zodat iemand kan besluiten of het het waard was.

## Beide normen, altijd

Een audit toetst **9001 én 27001**. Wordt er toch één gekozen, dan is dat **27001** — dat is de
norm waar de informatiebeveiligingsaudit op staat en waar de meeste beheersmaatregelen zitten
(93 clausules tegen 28).

Dat heeft gevolgen voor deze change: de review moet weten tegen welke norm een bevinding is
beoordeeld, en dat weet het tool vandaag niet. `bevindingen.norm` bevat `beide` voor alle 800
rijen. Zolang `clausule-per-norm` niet is doorgevoerd, kan de review een bevinding op §7.5 niet
tegen de juiste normtekst leggen — en dan beoordeelt het zware model de bevinding tegen dezelfde
verkeerde tekst als het goedkope.

## Wat er niet verandert

- **De auditor beslist over NC's.** Dit is een zeef, geen rechter.
- **De trail.** Elke reviewaanroep komt met vraag, antwoord, model, kosten en peildatum in
  `assistent_vragen`, storingen inbegrepen.
- **De eerste classificatie blijft.** De review vervangt hem niet; hij weegt hem.

## Volgorde

1. **`clausule-per-norm` eerst**, anders reviewt het zware model tegen de verkeerde normtekst.
2. Dan de vormcontrole (lege bevindingen) — die heeft geen model nodig en haalt er meteen 55 uit.
3. Dan de inhoudelijke review, eerst op een steekproef van 50 om te meten wat hij eruit haalt
   voordat er 800 doorheen gaan.
