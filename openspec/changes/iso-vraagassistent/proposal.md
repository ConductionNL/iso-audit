# Vraagassistent die alleen over ISO gaat, en alleen uit onze eigen bronnen antwoordt

## Waarom

Het portaal kan een audit draaien, maar het kan geen vraag beantwoorden. De auditor die wil
weten "welk bewijs hebben wij voor 8.24?" of "staat er al een actie op dit punt?" moet nu zelf
door 295 documenten, 1371 clausule-matches, de bevindingenhistorie en 83 Jira-punten. Dat is
precies het werk waar het landschapsscherm al bij helpt, maar alleen als je weet waar je moet
kijken.

Het patroon bestaat al binnen Conduction. De **Platform-assistent** op
`platform.commonground.nu/assistant` doet dit voor het OpenWoo-platform, met drie eigenschappen
die het bruikbaar maken in plaats van riskant:

> "Stel een vraag over het platform. Antwoorden komen uit het technisch handboek, mét
> bronvermelding. De assistent kan alleen lezen — wijzigingen lopen altijd via een pull
> request."

Eén afgebakend corpus, altijd bronvermelding, en geen schrijfrechten. Die drie zijn hier nog
belangrijker, want de output van dit tool gaat naar een certificerende instantie.

### Waarom niet gewoon een chatbot met ISO-kennis

Het model kent ISO 27001 en 9001 uit zijn training. Een assistent die daaruit antwoordt is
makkelijker te bouwen en voelt nuttiger — en is voor dit tool het verkeerde ding. Een antwoord
dat niet naar een bron van Conduction verwijst, is voor een audit waardeloos: je kunt het niet
natrekken, en het lijkt op bewijs terwijl het dat niet is. Dat is dezelfde valse-dekkingsvorm
die deze repo op drie andere plekken al heeft moeten weghalen (de hardcoded planning-sheet, de
Drive-locatie die geen map is, de modellen die stil nul bevindingen gaven).

Daarom: **staat het niet in het corpus, dan zegt de assistent dat.** Geen antwoord uit
modelkennis, ook niet gemarkeerd. Dat is saaier en het is verdedigbaar.

## Wat er komt

Eén scherm in het portaal — één vraag, één antwoord, geen gesprek — dat antwoordt uit vier
bronnen die alle vier al doorzoekbaar zijn:

| bron | waar | wat het beantwoordt |
|---|---|---|
| Normteksten | `data/normteksten.lookup(norm, clausule)` | "wat eist 8.24?" |
| Documentenlandschap | `documents` + `documents_fts` (FTS5) + `clause_matches` | "welk bewijs hebben wij?" |
| Bevindingen en historie | `bevindingen`, `decisions` | "wat vonden we hier eerder?" |
| Jira-opvolgpunten | de opvolgpunten uit `sources/opvolgpunten.py` | "staat er al een actie op?" |

Elk antwoord verwijst naar de bron: clausule-ID, documentnaam en een link naar het document in
het landschapsscherm. **De assistent citeert niet** — hij parafraseert en verwijst. Voor
normtekst is dat een auteursrechtelijke keuze (de repo houdt bewust verkorte eisen aan, geen
letterlijke ISO-tekst); voor eigen documenten is het consistentie, zodat er één regel is in
plaats van twee.

Spreken bronnen elkaar tegen — een document claimt dekking terwijl een eerdere bevinding NC
zegt — dan **benoemt de assistent de tegenspraak en kiest niet**. Dat is geen tekortkoming maar
de bedoeling: zo'n tegenspraak is vaak zelf de interessantste bevinding, en het oordeel blijft
bij de auditor.

Vraag en antwoord gaan **append-only in de audittrail**, naast `decisions` en
`classifications`. Wat de auditor het tool vroeg is onderdeel van hoe het oordeel tot stand
kwam, en dat is precies wat een certificerende instantie mag navragen.

## Wat er niet komt

**Geen schrijfrechten.** De assistent stelt geen bevinding voor, doet geen triage-suggestie en
raakt de werkset niet aan. Dat is niet uit voorzichtigheid maar omdat de auditor-spiegel de
capability is die dit tool draagt: op vaste punten houdt een mens het oordeel. Een assistent
die een concept-NC oppert, schuift dat oordeel richting het model — en een concept dat er al
staat, wordt bevestigd.

**Geen gesprek.** Eén vraag, één antwoord. Elk antwoord staat los natrekbaar in de trail; bij
een gesprek is een antwoord alleen te begrijpen mét de voorgaande vragen, en dan is de trail
niet meer per regel te lezen.

**Geen antwoorden uit modelkennis**, ook niet gemarkeerd als zodanig. Een markering die
vandaag klopt, klopt over een jaar niet meer — en dan staat er onnatrekbare tekst in een
audittool.

**Alleen de auditor.** Zelfde auth-gate als het portaal. Openstellen voor medewerkers of
externen is een publicatiebesluit over auditbevindingen en interne memo's, en dat is een eigen
change met een eigen afweging.

**Geen nieuwe zoekindex.** `documents_fts` bestaat al, met triggers die hem bijhouden. Een
vector-store erbij zou een tweede administratie zijn die uiteenloopt met de eerste.

## Capability-impact

Versterkt de **auditor-spiegel**: het tool wordt bevraagbaar zonder oordeelsbevoegdheid te
verschuiven. Dat is de scherpste vorm waarin die capability zich laat bouwen — nuttig zijn
zonder te beslissen.

Versterkt **patroondetectie** langs een nieuwe weg: een auditor die een vraag stelt en een
tegenspraak terugkrijgt, vindt patronen die geen classificatierun oplevert, omdat de vraag uit
de mens komt en niet uit de pipeline.

Raakt **onafhankelijke bronnen** niet — de assistent leest wat er al is en voegt geen bron toe.
