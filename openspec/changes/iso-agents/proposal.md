# Vier ISO-agents, gescheiden door hun bronregel

## Waarom

Het portaal kan een audit draaien, maar het kan geen vraag beantwoorden. De auditor die wil
weten "welk bewijs hebben wij voor 8.24?" moet zelf door 295 documenten, 1371 clausule-matches,
de bevindingenhistorie en 83 Jira-punten.

Het patroon bestaat binnen Conduction: de **Platform-assistent** op
`platform.commonground.nu/assistant` — "antwoorden komen uit het technisch handboek, mét
bronvermelding. De assistent kan alleen lezen." Eén corpus, altijd bronvermelding, geen
schrijfrechten.

Maar één assistent is hier te grof. Een auditor stelt vragen die fundamenteel verschillen in
wát een geldig antwoord is:

- "Welk bewijs hebben wij voor 8.24?" — te beantwoorden uit **onze** documenten, en uit niets
  anders.
- "Wat eist 8.24 eigenlijk?" — te beantwoorden uit de **norm**, waar Conduction geen bron voor
  is.
- "Wat ontbreekt er nog voor hoofdstuk 8?" — vraagt **beide**, en levert een constatering.
- "Schrijf een cryptografiebeleid" — komt uit **geen enkele bron**; dat is opstellen.

Eén bronregel kan die vier niet dragen. Antwoordt de assistent overal uit modelkennis, dan
staat er onnatrekbare tekst in een audittool. Antwoordt hij nergens uit modelkennis, dan kan
hij niet uitleggen wat een clausule eist en niets opstellen.

**Daarom scheiden we op bronregel, niet op onderwerp.** Vier agents, elk met één bron en één
bevoegdheid, en de grens tussen ze is het ontwerp.

## De vier agents

| agent | bron | genereert | rol in de trail |
|---|---|---|---|
| **Bronbevrager** | alleen ons corpus | nee | aanwijzing naar bewijs |
| **Normuitlegger** | `data/normteksten` | nee — parafraseert | context bij een clausule |
| **Gap-analist** | normteksten × ons bewijs | nee — constateert | bevinding-in-wording |
| **Opsteller** | modelkennis | ja | **nooit bewijs** |

**Bronbevrager.** Antwoordt uit de vier bronnen van de organisatie: documentenlandschap
(`documents_fts`, `clause_matches`), bevindingen en audithistorie, Jira-opvolgpunten, en de
normteksten. Staat het er niet in, dan zegt hij dat. Geen modelkennis, ook niet gemarkeerd.

**Normuitlegger.** Legt uit wat een clausule eist, geparafraseerd uit
`data/normteksten.lookup()`. Die catalogus heeft per clausule `normtekst` (verkort),
`interpretatie` en `bewijslast` — een lijst van wat een auditor als bewijs verwacht. Dat laatste
veld is precies wat deze agent bruikbaar maakt: hij kan zeggen wát er nodig is zonder iets over
Conduction te beweren.

**Gap-analist.** Zet `bewijslast` per clausule naast wat er in het landschap gekoppeld is en
constateert wat ontbreekt. Hij **hergebruikt de bestaande classificatie** en velt geen eigen
oordeel — anders is er een tweede classificatiepad met een ander antwoord op dezelfde vraag.

**Opsteller.** Schrijft beleidsstukken, een risicoregister of een Verklaring van
Toepasselijkheid uit modelkennis. Het nuttigste en het gevaarlijkste van de vier.

## De regel die de Opsteller draagbaar maakt

Wat het tool opstelt, **telt nooit als bewijs**. Het krijgt een merkteken dat meereist, en de
classificatie negeert het tot een mens het aantoonbaar heeft overgenomen.

Zonder die regel: de Opsteller schrijft een cryptografiebeleid, dat belandt in Drive, en de
classificatiepipeline leest het als bewijs voor 8.24. Het tool auditeert dan zijn eigen output.
Voor ISO 27001 raakt dat de onafhankelijkheid van de interne auditfunctie, en een certificerende
instantie vraagt daarop door. Dat is geen theoretisch bezwaar — Conduction ís gecertificeerd,
en `Afwijking 20250605_247` staat in het landschap.

## De catalogus komt uit de repo, niet van buiten

Als inspiratie lag er een ISO 27001-skill (`iso27001.skill`) met vier workflows en een
controlecatalogus. De **workflows** zijn overgenomen als agentindeling — gap-analyse,
normuitleg, opstellen — want die indeling klopt en is in de praktijk beproefd.

De **catalogus niet**, om twee redenen. Auteursrechtelijk leunt zo'n controlelijst met
beschrijvingen tegen ISO/IEC 27002-materiaal aan, en deze repo houdt bewust verkorte eisen aan.
Belangrijker: hij is niet nodig. `data/normteksten` heeft al 93 clausules voor 27001 — exact het
aantal Annex A-controls van 2022 — en 28 voor 9001, met een `bewijslast`-veld dat de skill niet
heeft. De eigen catalogus is rijker dan de geleende.

## Wat er niet komt

**Geen schrijfrechten op de audit.** Geen van de vier maakt een bevinding aan, doet een
triage-suggestie of raakt de werkset aan. De auditor-spiegel is de capability die dit tool
draagt: op vaste punten houdt een mens het oordeel.

**Geen gesprek.** Eén vraag, één antwoord. Elk antwoord staat los natrekbaar in de trail.

**Alleen de auditor.** Zelfde auth-gate. Openstellen is een publicatiebesluit over
auditbevindingen en interne memo's, met een eigen afweging.

**Geen nieuwe zoekindex.** `documents_fts` bestaat al met triggers; `clause_matches` maakt
"welke documenten raken 8.24" een query in plaats van een zoekopdracht.

## Capability-impact

Versterkt de **auditor-spiegel** in zijn scherpste vorm: bevraagbaar zijn zonder
oordeelsbevoegdheid. De scheiding op bronregel is precies wat dat afdwingbaar maakt — een agent
die niet uit ons corpus put, kan ook niet per ongeluk als bewijs gelden.

Versterkt **patroondetectie**: de Gap-analist vertrekt vanuit `bewijslast` per clausule in
plaats van vanuit de documenten die er zijn, en vindt daarmee wat er *niet* is. Dat is een
andere zoekrichting dan de pipeline heeft.

Raakt **onafhankelijke bronnen** niet — de agents lezen wat er al is.
