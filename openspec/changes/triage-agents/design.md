# Ontwerp — triage-agents

## Waarom hub-and-spoke en niet een keten

Een keten (landschap → triage → synthese, elk voedt de volgende) is verleidelijk omdat de
stappen op elkaar volgen. Twee redenen om dat niet te doen.

**Auditgrond.** In een keten is de invoer van stap 3 de uitvoer van stap 2. Beweert de
synthesizer iets, dan is de herkomst "de triage-ondersteuner zei het", en die zei het omdat de
landschapsagent iets teruggaf. Na twee schakels is een bewering niet meer naar een document te
herleiden. Bij een hub put elke spoke rechtstreeks uit het corpus en levert hij zijn eigen
bronverwijzingen; de hub voegt samen maar bedenkt niets.

**Werkgrond.** De taken zijn onafhankelijk: het bewijs bij clausule 5.17 ophalen hangt niet af
van wat er bij 8.24 gevonden is. Parallel is dan sneller én eenvoudiger.

De prijs van hub-and-spoke is dubbel werk: twee spokes kunnen hetzelfde document ophalen. Dat is
tokens, en tokens zijn hier goedkoper dan een onnavolgbare bewering.

## De grens: voorbereiden, niet oordelen

`assistent/clausule.py` weigert al elk antwoord met `voorstel`, `classificatie`, `oordeel`,
`advies`, `triage` of `aanbeveling` erin, met een test die faalt als iemand die lijst inkort.
Dezelfde weigering geldt voor de Triage-ondersteuner.

De Synthesizer is de uitzondering en verdient uitleg. Hij schrijft de synthese-alinea — "Drie
clausules, één hoofdgebrek: er is geen gedocumenteerd en getest continuïteitsbeheer" — en dat
ligt tegen een oordeel aan. Het verschil: hij werkt **alleen op bevindingen die de auditor al op
`valide` heeft gezet**. Hij vat een genomen besluit samen; hij neemt er geen.

Twee maatregelen daarbovenop:

1. Zijn uitvoer is een **concept** met een aparte status. Wat niet door een mens is geredigeerd,
   komt niet in de memo.
2. De onbewerkte modeltekst gaat naar de trail, ook als de auditor hem herschrijft. Anders is
   later niet vast te stellen of een zin van de auditor of van het model kwam.

## Waarom de hub geen agent is

De hub is gewone code: hij bepaalt welke clusters er zijn, roept spokes aan, verzamelt en ordent.
Geen model.

Een model als orchestrator betekent dat de **volgorde en de selectie** van het werk niet
reproduceerbaar zijn: twee runs op dezelfde dataset kunnen andere clusters aan andere agents
geven. Voor een audit is dat een probleem — "waarom is deze bevinding wel bekeken en die niet"
moet te beantwoorden zijn met een regel, niet met een steekproef. De ordening die de bestaande
clausule-agent gebruikt (`assistent/clausule.orden()`, met een reden per rij) is het model
hiervoor.

## Wat een spoke terugkrijgt en teruggeeft

Elke spoke krijgt van de hub: de opdracht in tekst, de bron-ID's die hij mag gebruiken, een
modelkeuze en een tokenbudget. Elke spoke geeft terug: een gestructureerd antwoord met per
bewering de bron-ID's die hem dragen.

De verwijzingscontrole die de Bronbevrager al doet — elk `[bron:<id>]` moet in het meegegeven
corpus voorkomen, anders is het een storing en geen antwoord — geldt voor elke spoke. Dat is de
enige maatregel die het verschil maakt tussen "we hebben het gevraagd" en "we hebben het
gecontroleerd".

## Parallellisme en kosten

Spokes draaien parallel met een bovengrens. Zonder grens is een run met 87 clausules 87
gelijktijdige aanroepen, en dan is een rate-limit de eerste die het merkt — zoals de
Planning-bron in juli met 429's.

Elke aanroep gaat met kosten en peildatum in de trail, en de run-samenvatting telt op. Een run
waarvan de agentkosten niet zichtbaar zijn, is een run waarvan niemand kan besluiten of het
zwaardere model het waard was.

## Wat er misgaat als de agents fout zitten

Een agent die een gebrek verkeerd clustert, kost de auditor tijd bij het nakijken. Een agent die
een oordeel velt dat de auditor bevestigt, kost de audit zijn waarde. Het ontwerp is op dat
tweede geval gericht: parallel, geen onderlinge invoer, harde verwijzingscontrole, geen status,
en een concept dat een mens moet aanraken voordat het telt.
