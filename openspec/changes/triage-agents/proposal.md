# Agents die triage ondersteunen: hub-and-spoke

## Waarom

De run van 2026-08-24 leverde **903 bevindingen** op. De auditor heeft ze in vier bulkacties op
`valide` gezet — 902 stuks tussen 13:12 en 13:49 lokale tijd. Dat is geen triage, dat is
capituleren voor het aantal. En het is niet te verwijten: 903 bevindingen één voor één wegen is
werk waar niemand aan begint.

Tegelijk laat het handmatige Q2-memo zien wat er wél mogelijk is: 61 ruwe NC's teruggebracht tot
**2 genummerde NC's** met drie acties elk. Iemand heeft daar de samenhang in gezien — drie
clausules die één gebrek beschrijven. Dat is het werk dat waarde heeft, en het is precies het
werk waar het aantal bevindingen nu overheen walst.

Agents kunnen dat voorwerk doen. Wat ze **niet** mogen, is het oordeel overnemen. Dat is geen
voorzichtigheid maar de missie van dit tool: de auditor-spiegel. Er bestaat al een precedent in
de code — `assistent/clausule.py` weigert met `VERBODEN_VELDEN` elk antwoord waarin `voorstel`,
`classificatie`, `oordeel`, `advies`, `triage` of `aanbeveling` voorkomt, met een test die faalt
als iemand die grens oprekt. Een voorgestelde klasse maakt van beoordelen bevestigen.

## Wat er verandert

Drie agents, plus een hub die ze aanstuurt.

**De Landschapsagent (lezen en ophalen).** Haalt op wat er over een clausule of thema in het
corpus staat: documenten, eerdere bevindingen, opvolgpunten uit Jira, normtekst met bewijslast.
Dit is de bestaande Bronbevrager-machinerie (`assistent/ophalen.py`), maar aangeroepen door een
hub in plaats van door een mens met één vraag. Hij put uitsluitend uit wat het tool heeft
ingelezen — een antwoord uit modelkennis is voor een audit waardeloos.

**De Triage-ondersteuner.** Per bevinding of cluster: wat is het bewijs, wat ontbreekt er
volgens de bewijslast van de clausule, welke bronnen spreken elkaar tegen, en welke bevindingen
beschrijven hetzelfde gebrek. Hij levert **geen** triage-status. Zelfde grens als de bestaande
clausule-agent, met dezelfde afgedwongen weigering.

**De Synthesizer.** Neemt de door de auditor gecureerde NC's en stelt de groepering naar thema's
voor, plus de synthese-alinea per thema — de tekst die in het Q2-memo zegt *"Drie clausules, één
hoofdgebrek"*. Dit is de enige agent die een tekst produceert die de deur uit gaat, en daarom is
hij de enige met een verplichte redactieslag door de auditor vóór publicatie.

**De hub.** Eén orchestrator die de taak opdeelt, de agents parallel aanroept, en hun uitkomsten
samenvoegt. Dat is het patroon dat Anthropic beschrijft voor multi-agent-systemen: een lead die
decomponeert, workers die onafhankelijk en parallel werken, en de lead die synthetiseert.

**Spokes praten niet met elkaar.** Dat is de kern van het patroon en hier bovendien een
audit-eis: als agent A de uitvoer van agent B als bron gebruikt, is niet meer na te trekken waar
een bewering vandaan komt — dezelfde reden dat de Bronbevrager geen gesprek voert. Elke spoke
krijgt zijn opdracht van de hub, put uit het corpus, en levert terug aan de hub.

**Zwaardere modellen mogen.** De classificatie draait op een goedkoop model omdat het over 903
documenten gaat; deze agents draaien over een handvol clusters en het oordeel dat ze voorbereiden
is duurder dan de tokens. De modelkeuze staat per agent in de configuratie en gaat mee in de
trail, zoals bij elke andere aanroep.

## Wat er niet verandert

- **De auditor beslist.** Geen agent zet een triage-status, geen agent sluit een bevinding.
- **De trail.** Elke aanroep komt in `assistent_vragen`: vraag, antwoord, meegegeven bron-ID's,
  model, kosten en peildatum. Ook een storing.
- **Geen nieuw corpus.** De agents lezen wat de bronnen hebben opgeleverd. Geen embeddings, geen
  tweede index.

## Wat dit eerst nodig heeft

Een 500 op de assistent-route laat vandaag **geen spoor** in `assistent_vragen` — de trail loopt
tot 2026-08-22 terwijl er op 24 augustus een storing was. Voor één handmatige vraag is dat
vervelend; voor een hub die tientallen aanroepen per run doet is het onacceptabel, want dan is
niet meer vast te stellen wat een agent gezien heeft toen hij iets beweerde. Dat moet vóór deze
change gerepareerd zijn.
