# Interview voorstellen waar bewijs alleen uit een mens komt

## Waarom

Sommige eisen zijn niet uit documenten te halen. "Is het personeel bewust van het
informatiebeveiligingsbeleid" staat in geen enkel bestand; dat blijkt uit een gesprek. Het tool
ziet die clausules nu als ongedekt en zegt niets over hoe je er wél bewijs voor krijgt.

Gemeten op 2026-08-22 in de eerste volledige run: **86 van de 121 clausules** (9001 + 27001) zijn
geraakt door minstens één document. De rest is ongedekt — en voor een deel daarvan is dat geen
tekortkoming maar een verkeerde bronverwachting: het bewijs is er wel, het zit in iemands hoofd
of in een handeling die niemand heeft opgeschreven.

Dit is een klantwens en het sluit aan op wat er al staat: `interview.py` heeft een CLI-flow met
gap-detectie (`_haal_gaps_op`) en een `interviews`-tabel per clausule. Wat ontbreekt is de brug:
van "clausule X heeft geen documentbewijs" naar "dit gesprek, met deze persoon, over deze
punten".

## Wat de meting deed met dit voorstel

Het oorspronkelijke idee was: markeer per bewijslast-item of een mens het kan bevestigen, en stel
daar interviews voor. **Gemeten op 2026-08-22: van de 481 bewijslast-items zijn er ongeveer drie
die een waarneming beschrijven.** De catalogus is vrijwel volledig artefact-gericht — "notulen
directiebeoordeling", "toegangsrechtenmatrix", "versiehistorie". Dat is voor een auditwerktuig
ook logisch: papier is navraagbaar en een gesprek niet.

Twee wegen daaruit, en de eerste is niet de mijne om te nemen:

1. **De catalogus verrijken** met waarneembare bewijslast per clausule. Dat is inhoudelijk
   ISO-werk — vaststellen wát als bewijs telt — en dat is een auditoroordeel, geen
   implementatiekeuze. 481 items markeren zou betekenen dat dit tool zijn eigen bewijsstandaard
   verzint.
2. **De vraag omdraaien.** Niet "welk bewijs kan een mens bevestigen", maar: "we vinden dit
   artefact niet — bestaat het, en waar?" Dat is precies wat een auditor in een interview vraagt,
   het is volledig af te leiden uit de bestaande catalogus, en het antwoord is een **aanwijzing
   naar bewijs**, geen vervanging ervan.

Dit voorstel volgt weg 2. Weg 1 blijft openstaan als aparte, inhoudelijke change.

## Wat er verandert

**Een voorgesteld interview per ongedekte clausule.** Per clausule: welke artefacten de norm
verwacht, welke daarvan niet in het landschap zitten, en per ontbrekend artefact één vraag —
"waar is dit vastgelegd, of waarom bestaat het niet?". De vragen komen uit de norm-catalogus,
niet uit modelkennis over hoe je interviewt.

**Een rol in plaats van een naam.** Het voorstel noemt wie erover gaat als rol
("verwerkingsverantwoordelijke", "beheerder toegangsrechten"), niet als persoon. Het tool weet
niet wie dat bij Conduction is, en een verzonnen naam in een auditplanning is erger dan een lege.

**Inplannen als aparte, expliciete handeling.** Het voorstel staat los van het versturen. Wie
inplant, plant in met één druk — maar dat is een handeling naar buiten met een eigen
bevestiging, geen bijproduct van een run.

## Wat er niet verandert

**Een gesproken antwoord vervangt geen document.** Het interview wijst naar bewijs; het is
zelf geen bewijs voor een clausule die om een artefact vraagt. Wat de geïnterviewde zegt, wordt
vastgelegd als wat het is: een aanwijzing, en soms de constatering dat het artefact niet bestaat
— wat op zichzelf een bevinding is die de auditor maakt, niet het tool.

**Het tool voert het interview niet.** Er is een `interview.py`-CLI waarin de auditor zelf
antwoorden vastlegt; dat blijft. Een agent die het gesprek doet, maakt van bewijs uit een mens
weer bewijs uit een model.

**Een voorgesteld interview is geen bevinding.** Het staat naast de werklijst, niet erin.

**Geen automatische planning bij een run.** Een run die ongevraagd agenda's vult, is een run die
niemand meer durft te starten.

## De blokkade die eerst op tafel moet

`notification.stuur_calendar_uitnodiging` werkt via de **`gws`-CLI**, en die authenticeert met
een persoonlijke OAuth-sessie. Twee gevolgen: de binary zit niet in het container-image, dus
inplannen kán vandaag niet vanuit het portaal, en zolang het via die CLI loopt hangt de
capability aan één medewerker — precies wat change `iso-portal` 7.x wil opruimen.

Inplannen vraagt dus eerst een org-credential met een agenda-scope. Dat is een beslissing over
credentials, niet over code, en hij staat vóór de implementatie van het inplannen. **Het
voorstellen van interviews kan wel zonder**: dat schrijft niets naar buiten.

## Capability-impact

Versterkt de **auditor-spiegel**: het tool zegt niet alleen "hier is geen bewijs" maar ook "dit
soort bewijs komt uit een gesprek, en dit zou je dan vragen". Dat is de spiegel gebruiken in
plaats van alleen een gat aanwijzen.

Raakt **onafhankelijke bronnen** aan de rand: een interview is een bron die het tool zelf
uitlokt. Daarom blijft het antwoord van de mens leidend en legt de auditor het vast — het tool
vult niets in.
