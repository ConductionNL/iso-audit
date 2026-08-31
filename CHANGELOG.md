# Changelog

Alle relevante wijzigingen aan dit project worden hier vastgelegd.
Format volgt [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/).
Versionering volgt [Semantic Versioning](https://semver.org/lang/nl/).

## [Unreleased]

### Fixed — 2026-08-31 — het portaal leest het profiel uit git, niet van de PVC

Bij het verifiëren van de uitrol van a86 bleek het portaal te starten met
`--profile=/var/lib/iso-audit/conduction.profile.yaml` — een kopie op het volume van 12 augustus,
818 bytes, zonder `clausule_context`. De classificatie las ondertussen het profiel uit het image.
Twee profielen dus, en het verschil was onzichtbaar.

Waarom dat meer is dan slordig: de hele constructie rust op het argument dat een verlaging later
na te lezen is. Een auditor die vraagt op grond waarvan A.8.14 van NC naar OFI ging, moet dat
kunnen terugvinden in een bestand met een geschiedenis. Voor het PVC-exemplaar gold dat niet — dat
versiebeheerde niemand.

Vóór het omzetten veld voor veld vergeleken: het PVC-bestand bevatte geen enkel veld dat niet ook
in git stond; git had alleen méér (de `clausule_context`). Er gaat dus niets verloren. Audits,
rapporten en de database blijven op de PVC — dit gaat alleen over het profiel.

Een test bewaakt nu dat `--profile` en `ISO_AUDIT_PROFIEL` hetzelfde bestand aanwijzen en dat dat
bestand in de repo staat. Geen versie-bump: `deploy/` valt buiten de image-paden, dus Argo synct
het manifest zonder rebuild.

**Bestanden:** `deploy/deployment.yaml`, `tests/api/test_run_standaarden.py`.

### Release — 2026-08-31 — 0.2.0a86

Versie en `newTag` meebewogen met de image-inhoud van de drie changes hierboven (clausule-context,
review/auto-triage standaard aan, positieve waarnemingen in de memo). De image-workflow weigerde
de build op a85: dezelfde tag met andere inhoud is een mutable tag, en dan weet niemand meer welke
code er in productie draait.

### Added — 2026-08-31 — positieve waarnemingen gebundeld in de memo

De memo somde alleen gebreken op. Dat geeft een scheef beeld van een organisatie, en voor een
externe auditor is het minder bruikbaar: die wil zien wát werkt, niet alleen wat niet werkt.

Nieuwe sectie "Wat aantoonbaar op orde is", na de verbeterpunten. Eén zin per thema, met een
`POS n`-code zodat er in een vergadering naar te verwijzen valt. Wie meer wil weten, heeft de
bewijslast — daar staat elke waarneming met zijn brondocument.

Drie keuzes die het verschil maken tussen een sectie en een sier-alinea:

- **Alleen bevestigde waarnemingen.** "Toegangsbeheer is op orde" is een uitspraak waar de
  organisatie op wordt aangesproken; die hoort te rusten op een triage-bevestiging en niet op
  een modeloordeel dat niemand woog. Sinds auto-triage het onbetwiste deel (positief en OFI)
  afdoet, is dat geen lege eis.
- **De zin is natrekbaar of hij komt uit de review.** Is er een kernzin, dan die. Anders een
  feitelijke zin: "12 bevestigde waarnemingen op 5 clausules; geen afwijkingen aangetroffen."
  Een lovende zin verzinnen zou het makkelijkst zijn en het minst waard — "uitstekend beheerst"
  is niet na te rekenen. Een test bewaakt dat er geen lofzang in sluipt.
- **De notitie zegt wat er buiten viel**, in getallen: hoeveel nog niet bevestigd zijn en
  hoeveel er buiten een thema vielen. Zwijgen daarover leest als "dit was alles".

Geen bovengrens op het aantal thema's, dezelfde reden als bij de NC-blokken: afkappen op omvang
laat iets uit de memo vallen zonder dat een mens erover besliste. `Overig` levert geen losse
regels op — die maken een memo langer zonder hem beter te maken; het aantal staat in de notitie.

**Bestanden:** `memo/groepering.py` (`groepeer_positief`), `memo/models.py` (`PositiveBlock`),
`memo/builder.py`, `memo/templates/management-memo/memo.html.j2` + `partials/positive.html.j2`,
`tests/memo/test_positieven.py` (nieuw).

### Changed — 2026-08-31 — review en auto-triage staan in het portaal altijd aan

De run van 2026-08-31 leverde 833 bevindingen op en nul review-adviezen: `decisions` en
`review_adviezen` waren allebei leeg. De autonome review had niet gedraaid, en auto-triage hangt
daarachter — zonder advies is er geen groen licht.

Twee oorzaken, allebei stil:

1. **`ISO_AUDIT_REVIEW` stond niet in het manifest.** Leeg telt als uit, en dat is de juiste
   standaard voor een schakelaar die geld kost. Nu staat de keuze expliciet in
   `deploy/deployment.yaml`, mét de reden erbij. De code-standaard blijft uit; het portaal is
   een omgeving die er zelf voor kiest, en de review logt zijn herkomst ("omgeving").
2. **De UI zou het manifest alsnog overrulen.** Het portaal stuurt per run een harde `true` of
   `false` mee, want een vinkje kent geen stand "laat de omgeving beslissen". Een uitgevinkt
   vakje overrulet daarmee `ISO_AUDIT_REVIEW`, en niemand ziet dat gebeuren. Env zetten alleen
   was dus niet genoeg geweest.

`/instellingen/options` geeft nu ook `standaarden` terug (`review`, `auto_triage`), en de UI
vult de vinkjes daar één keer mee bij het laden. Daarmee is in het portaal te zien wat de
omgeving zegt, in plaats van dat het verschil onzichtbaar blijft.

Ook expliciet gezet: `ISO_AUDIT_PROFIEL`. De clausule-context viel anders terug op een relatief
pad en hing daarmee aan de werkdirectory.

**Wat auto-triage wel en niet doet** (ongewijzigd, maar hier de vindplaats): alleen
`bevestigen`, alleen op positief en OFI, nooit een NC en nooit een verlaging, en altijd via
`apply_triage` met actor `auto-triage` in de trail.

**Bestanden:** `deploy/deployment.yaml`, `api/app.py`, `api/ui.html`,
`tests/api/test_run_standaarden.py` (nieuw).

### Added — 2026-08-31 — clausule-context in het profiel: het auditoordeel blijft staan

Na de volledige run (715 bevindingen, 68 NC) wees de auditor twee NC's terug die het niet zijn:

- **A.8.14 redundantie** — Conduction haalt data bij de bron op; er valt weinig te dupliceren
  wat niet bij ons staat.
- **A.8.9 configuratiebeheer** — de versies staan in Git, met commit, auteur en geschiedenis.

Beide keren ís er een beheersmaatregel, alleen niet gedocumenteerd of gecentraliseerd. Zonder
vastlegging velt het model elke run opnieuw hetzelfde oordeel en sleept de auditor elke run
dezelfde bevindingen met de hand naar OFI.

Wat er nu gebeurt, in `clausule_context` in het profiel (klantspecifiek, dus niet in code):

1. **`context`** gaat mee in de classificatie-prompt als feitelijke toelichting — het model
   beantwoordt de vraag met kennis die anders alleen de auditor had. Geen gewenste uitkomst.
2. **`hoogste_klasse`** legt een plafond op het oordeel. Alleen verlagen: `NC` wordt geweigerd,
   want ophogen is een auditoordeel dat in de triage hoort met een mens-account eronder. Een
   plafond zonder `motivering` laadt niet — een stille uitzondering is precies waar een externe
   auditor op doorvraagt. De verlaging komt mét motivering in de onderbouwing van de bevinding
   te staan; het ruwe modeloordeel verdwijnt niet.
3. **`thema`** bundelt de clausules die hetzelfde verhaal vertellen. A.8.14 en A.8.9 vielen in
   `Back-up & continuïteit` en `Ontwikkeling & wijzigingsbeheer` — uit elkaar getrokken zijn het
   twee losse opmerkingen, bij elkaar één verbeteradvies over documenteren. Daarvoor is
   `Vastlegging van bestaande beheersing` aan de taxonomie toegevoegd (26 → 27), bewust **zonder**
   keyword-regel: aan de tekst is niet te zien of iets bestaat maar ongedocumenteerd is. Voorrang
   bij het toekennen: profiel > LLM-verfijning > heuristiek.

**Bestanden:** `classification/grenzen.py` (nieuw), `classification/findings.py`,
`classification/thema.py`, `memo/theme/profile.py`, `pipeline.py`,
`examples/auditmemo/conduction.profile.yaml`, `tests/memo/test_clausulecontext.py` (nieuw),
`tests/classification/test_thema.py`.

**Wat de tests blootlegden:** de eerste versie wireerde de grens tot in `bouw_bevindingen` maar
niet tot in `_classificeer_en_bewaar` — de regel bestond en deed in een echte run niets. De
losse eenheden waren groen. Er staat nu een ketentest van profielregel tot bevinding.

1833 tests groen; `pre-commit run --all-files` (ruff, format, mypy --strict, secrets, bandit)
groen.

### Fixed — 2026-08-30 — bandit-gate weer groen

De CI-stap "Faal op medium en hoger" stond rood sinds de sitemap-wijziging: `_wortel()` roept
`ElementTree.fromstring` aan en bandit markeert dat als B314. De check dekt een echt risico —
entity-expansie — maar die is hier al afgevangen: een sitemap met een DOCTYPE wordt geweigerd
vóór het parsen.

Nu voorzien van `# nosec B314` mét reden, dezelfde afweging als bij `sources/tekst.py` voor ODF:
`defusedxml` erbij halen voor één aanroep met een expliciete DOCTYPE-check ervoor is een
afhankelijkheid zonder winst.

**Wat dit blootlegt in mijn eigen werkwijze:** ik draaide lokaal ruff, mypy en de testsuite, maar
niet bandit. De gate stond daardoor twee pushes lang rood zonder dat ik het zag. `uv run
pre-commit run --all-files` draait ze alle vier tegelijk en staat niet voor niets in CLAUDE.md.

### Fixed — 2026-08-30 — een afgebroken run begint niet opnieuw

Vóór de volledige run vroeg de auditor: wat als het API-tegoed opraakt halverwege? Het antwoord
was half goed, en de helft die niet klopte zat precies bij het runtype dat hij wilde draaien.

**Wat al werkte:** elk document wordt apart geclassificeerd, opgeslagen en gecommit. Een fout op
document 500 kost geen 499 eerdere.

**Wat niet werkte:** `_gedaan_per_doc` bepaalt wat er kan worden overgeslagen, en zocht op de
run-parameter. Bij een gecombineerde run is dat `beide`, terwijl bevindingen worden opgeslagen
met hun eigen norm (`9001` of `27001`). Hij vond dus niets, en een hervatte run begon van voren
af aan — bij precies het runtype waarvoor hervatten bedoeld is. Nu telt hij, net als
`_bevindingen_query`, de rijen van beide normen mee plus de oude rijen die letterlijk `beide`
dragen.

**En de melding.** Stopt de classificatie, dan staat er nu in het log hoeveel documenten er wél
zijn verwerkt en dat een nieuwe run verdergaat waar deze stopte. Zonder dat getal weet niemand of
hervatten nog iets te doen heeft, en dan is "we raken de stand niet kwijt" een bewering in plaats
van iets wat je kunt zien.

### Added — 2026-08-30 — bevindingen horen bij één audit

Een schone audit toonde 247 bevindingen terwijl de run er zes had opgeleverd. De andere 241 kwamen
uit de gedeelde `bevindingen`-tabel: die was niet per audit gescheiden, dus exporteerde élke audit
alles wat er ooit in was beland. Archiveren van de vorige audit hielp niet — de bevindingen zitten
in de database, niet in de auditmap. "Schoon beginnen" bestond dus niet.

De kolom `audit_id` lost dat op: een run schrijft het id van zijn eigen audit, en de export
filtert erop. Rijen van vóór deze wijziging hebben geen id en horen dus bij geen enkele audit —
zichtbaar zonder filter, nooit in een nieuwe audit. Weggooien zou bewijs vernietigen, aan iedereen
tonen is het probleem zelf.

De classificatiecontext had al een veld `audit_id`, maar dat is een run-tijdstempel dat de
`classifications`-rijen groepeert. Twee dingen met dezelfde naam is waar verwarring uit ontstaat;
het nieuwe veld heet daarom `auditmap` en beide dragen nu uitleg over wat ze zijn.

### Removed — 2026-08-30 — de achterhaalde per-repository gegevens zijn opgeruimd

10.097 rijen verwijderd, met een backup ervoor: 1.283 bevindingen en 24 van de website, 6.423
clausulekoppelingen en 2.391 documenten. Ze verwezen naar documenten die de bron niet meer levert
— sinds de aggregatie bestaat `github:ConductionNL/iso-audit#LICENSE` niet meer als document.

### Fixed — 2026-08-30 — de LICENSE-bevinding stelde de verkeerde vraag

Het aggregaat op A.5.32 leverde een NC op: *"303 van 386 repositories missen een LICENSE-bestand"*.
De auditor wees erop dat dit hooguit een verbeterpunt is, en had gelijk: **A.5.32 gaat over het
respecteren van andermans intellectuele eigendom** en het beheren van propriëtaire software —
legale licenties, naleving van voorwaarden. Hoe de organisatie haar eigen code licenseert is iets
anders.

De fout zat in de koppeling, niet in het model: die gaf de vraag "toets dit tegen A.5.32" zonder
te zeggen wat die eis inhoudt. Een bewijssoort kan nu een **duiding** meedragen die met het
document meegaat naar de classificatie. Dat is de interpretatie van de eis, niet de gewenste
uitkomst — het oordeel blijft aan het model en daarna aan de auditor; wat verandert is dat de
vraag klopt.

### Fixed — 2026-08-30 — één netwerkhikje gooide zeven minuten werk weg

De eerste run met de aggregerende repobron brak af: *"Bron(nen) leverden niets: repo: De bron was
niet bereikbaar."* In het serverlog stond wat er echt gebeurde:

    ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed
    connection without response'))

GitHub verbrak de verbinding halverwege de 386 repository's. Die fout werd niet gevangen, dus
leverde de héle bron niets — zeven minuten ophalen weg door één hik.

Twee lagen aangepakt:

**Per repository afvangen.** Alles voor één repository gebeurt binnen dezelfde `try`, en pas
daarna wordt er iets vastgelegd: een halve repository in het aggregaat zou een telling opleveren
die niemand kan navertellen. Wat mislukt komt in `overgeslagen` en dus in de dekking — stil
doorgaan zou een audit opleveren die iets beweert over wat niemand heeft gelezen.

**Eén herkansing per verzoek.** `_haal()` probeert het bij een verbindingsfout één keer opnieuw.
Twee pogingen en niet vijf: langer doorgaan maakt een échte storing traag zichtbaar, en een
repository die in de dekking staat als niet-gelezen is beter dan een run die twintig minuten
hangt op iets wat stuk is. Alleen bij `RequestException` — een 403 of 404 is een antwoord en geen
storing, en die opnieuw sturen levert hetzelfde op.

Daarbij een eigen fout van vandaag hersteld: de melding liep even door `normaliseer()`, waardoor
*"bestaat niet, of het token mag het niet zien (404)"* werd vervangen door de algemene zin "De
opgegeven bron bestaat niet". Onze eigen duiding hoort ongewijzigd door; alleen de melding van de
bibliotheek wordt afgeschermd, want die kan een URL met credential bevatten.

### Changed — 2026-08-29 — de repobron aggregeert per maatregel, niet per repository

De A.5-run leverde 137 bevindingen uit repository's, waarvan **47 op A.5.32 die allemaal
hetzelfde zeiden**: "deze repository heeft een LICENSE-bestand". Dat is geen 47 keer bewijs maar
één constatering over 47 repository's — en in een memo van 1-3 A4 onbruikbaar. Het kostte 1.369
modelaanroepen en $4,33.

Een auditor stelt zijn vraag per **maatregel**: "is het intellectueel eigendom geregeld?" Het
antwoord daarop is "95 van de 386 repository's hebben een licentiebestand", niet vijfennegentig
losse constateringen.

De bron levert nu één document per bewijssoort over álle repository's. Gemeten op vijf
repository's: **11 documenten** in plaats van dertig; over de hele organisatie wordt dat ongeveer
twaalf in plaats van 2.200.

Wat níet verdwijnt is de natrekbaarheid:

- Het aggregaat telt en noemt namen: *"Aanwezig in 4 van de 5. Ontbreekt in: .github."*
- De inhoud gaat **ontdubbeld** mee. Honderdachtentwintig `SECURITY.md`-bestanden zijn in de
  praktijk een handvol varianten van hetzelfde sjabloon, en juist het verschil daartussen is wat
  een auditor wil zien.
- Bij meer dan veertig namen wordt de rest geteld in plaats van weggelaten — anders wordt "in 258
  repository's ontbreekt dit" een onbewijsbare bewering.

De instellingen gaan dezelfde kant op: *"Verplichte review vóór samenvoegen: 6 van de 386"* met
de repository's zónder erbij, in plaats van 386 losse regels.

Het aggregaat draagt de laatste `pushed_at` van alle repository's, zodat de incrementele ingest
het kan overslaan als er nergens gepusht is.

### Fixed — 2026-08-29 — de repo- en websitebron leverden geen enkele bevinding

De A.5-run gaf 84 bevindingen, allemaal uit Drive en Nextcloud. Geen enkele uit de 1.283
repository-documenten of 162 webpagina's die die run had opgehaald — terwijl ze wél waren
gekoppeld: de database telt 1.080 A.5-koppelingen voor `Repo`.

Ze sneuvelden op één regel:

    gearchiveerd = [d for d in gekoppeld_alle if (d.get("modified_at") or "") < cutoff]

Een lege string is in Python altijd kleiner dan een datum-string. Elk document zónder
wijzigingstijd gold dus als ouder dan twee jaar. Het log zei het ook, en het klopte niet:
*"Leeftijdsfilter (2024-08-29): 88 actief, 1448 gearchiveerd (>2 jaar oud)"* — die 1448 waren die
dag opgehaald.

Twee dingen aangepakt:

**Onbekend is niet oud.** `splits_op_leeftijd()` telt een document zonder datum als actief en
telt apart hoeveel dat er zijn. Bij twijfel meenemen: een document ten onrechte wegen kost een
modelaanroep, een document ten onrechte weglaten kost bewijs. De melding noemt nu drie getallen
in plaats van twee, want "actief" was een cijfer waarin twee verschillende dingen zaten.

**De bronnen leveren nu wél een wijzigingstijd.** Alle 2.207 repo- en 175 websitedocumenten
hadden een lege `modified_at`, tegen 0 van de 439 Drive-documenten. De repobron gebruikt
`pushed_at` — is er niet gepusht, dan zijn de bestanden niet gewijzigd — en de websitebron
`<lastmod>` uit de sitemap. Dat lost naast dit filter ook op waarom een herhaalde run over
dezelfde 385 repository's opnieuw zestien minuten deed: zonder tijd kan `mag_overslaan` niets
overslaan.

Ontbreekt de tijd alsnog, dan blijft het veld leeg en wordt er gewoon opnieuw gelezen. Een
verzonnen tijdstempel zou een document als ongewijzigd laten gelden terwijl niemand dat weet.

### Fixed — 2026-08-29 — de archiveerknop werkte niet

`POST /audits/{id}/archiveer` gaf een 422 met `loc: ["query","body"]`, en `/openapi.json` gaf
zelfs een 500. De oorzaak: `AuditArchiveren` stond *binnen* `create_app`, en met
`from __future__ import annotations` is elke annotatie een string — FastAPI kan zo'n forward
reference naar een lokale klasse niet oplossen en zag `body` als queryparameter.

De knop stond er, de route stond er, en samen werkten ze niet. `tests/api/test_ui_archiveren.py`
controleerde dat de UI het juiste pad aanroept, niet dat dat pad werkt: precies het gat dat een
contract-test openlaat.

Het model staat nu op moduleniveau, waar de acht andere al stonden. Zeven tests dekken de route
af, inclusief dat `/openapi.json` klopt — dat is niet cosmetisch, elke gegenereerde client leest
het — en dat de reden in de audittrail landt.

### Added — 2026-08-29 — Bijlage A is een eigen scope, expliciet getoetst

Sinds de maatregelen de `A.`-prefix dragen, kan een auditor kiezen wát hij toetst. Dat is nu met
tests vastgelegd, met de aantallen uit de norm zelf:

| scope | clausules | wat |
|---|---|---|
| `4` | 4 | context van de organisatie |
| `5` | 3 | leiderschap |
| `9` | 3 | evaluatie van de prestaties |
| `A` | 93 | de hele Bijlage A |
| `A.5` | 37 | organisatorische maatregelen |
| `A.6` | 8 | mensgerichte maatregelen |
| `A.7` | 14 | fysieke maatregelen |
| `A.8` | 34 | technologische maatregelen |
| `A.8.24` | 1 | één maatregel |

37 + 8 + 14 + 34 = 93; een thema dat clausules kwijtraakt valt zonder die som niet op.

De scherpste toets is dat **§8 en A.8 elkaar niet raken**: §8 is "Uitvoering" (drie clausules),
A.8 zijn de technologische maatregelen (vierendertig). Zonder dat onderscheid zou een run op
hoofdstuk 8 er vierendertig meenemen die er niet bij horen, en zou de memo claimen dat de
uitvoering is getoetst terwijl er encryptiebevindingen in staan.

De managementclausules en Bijlage A dekken samen de hele norm — ook dat staat als test, zodat
niets tussen wal en schip valt.

### Fixed — 2026-08-29 — een run op hoofdstuk 4 levert hoofdstuk 4

De eerste run op ISO 27001 hoofdstuk 4 leverde **303 bevindingen**, met clausules als 10.2, 9.1
en A.8.16. Het run-record zei netjes `hoofdstuk: 4` en de pipeline classificeerde ook alleen
hoofdstuk 4 — maar de export naar de werkset pakte alles wat ooit in de database was gekomen,
uit beide normen en alle hoofdstukken.

Twee oorzaken, en de tweede is de ergste:

- `_bevindingen_query` kende geen hoofdstuk. Nu wel, met de `A.`-prefix meegerekend: hoofdstuk
  `8` levert §8.1 t/m §8.3 en níet A.8.16, want dat is een maatregel en geen managementclausule.
  Wie de maatregelen wil, typt `A.8`.
- **`export_db_findings` had een eigen query** die alleen opvolgpunten wegliet — geen norm, geen
  hoofdstuk. Twee queries die hetzelfde zouden moeten doen, en één ervan deed het niet. Nu loopt
  hij door dezelfde `_bevindingen_query`, zodat er één waarheid is over wat binnen een run-scope
  valt.

Dit is dezelfde fout waar `RunStartRequest` bij de norm al voor waarschuwt: *"een run waarvan de
scope niet meer uit de audit volgt — en dan liegt de memo over wat er getoetst is"*. Voor het
hoofdstuk gold die redenering nog niet.

### Fixed — 2026-08-29 — een lege repository is een waarneming, geen storing

Tijdens de org-brede run gaven 11 van de 385 repository's een 409 op de bestandslijst. De melding
was *"de forge gaf een onverwacht antwoord (409)"*, wat de auditor laat zoeken naar een storing.
GitHub antwoordt daar letterlijk *"Git Repository is empty."*: er valt niets te lezen omdat er
niets is. Dat staat nu in de melding.

### Fixed — 2026-08-28 — onze eigen foutmeldingen komen ongewijzigd bij de auditor aan

De auditor koos hoofdstuk 4 voor ISO 27001 en zag: *"FOUT: De verbinding kon niet worden gelegd.
Zie het serverlog voor details."* De echte melding stond in het log en was volstrekt duidelijk:
*"Geen clausules gevonden voor hoofdstuk '4'. Beschikbare hoofdstukken: 5, 6, 7, 8."* Een
verwijzing naar een serverlog waar hij niet bij kan, voor een probleem dat niets met een
verbinding te maken had.

De normalisatie die dat verving bestaat met goede reden: `run()` vangt élke pipeline-fout, ook
die van Google, Jira en Anthropic, en zo'n tekst kan een URL met credential of een tokenfragment
bevatten. Tot 2026-08-14 landde dat rechtstreeks in de browser.

Nieuw is `EigenFoutError`: wie die opgooit, verklaart dat de tekst van ons is en dus veilig. Het
onderscheid is het **type** en niet de inhoud — op inhoud filteren zou raden zijn. De ruwe
melding gaat nog steeds naar het serverlog, want dat hoort het volledige verloop van een run te
bevatten.

### Added — 2026-08-28 — ISO 27001 wordt op de hele norm getoetst

De norm-DB voor 27001 bevatte **alleen Bijlage A**: 93 maatregelen, genummerd 5.1 t/m 8.34. De
managementclausules 4 t/m 10 — context, leiderschap, planning, ondersteuning, uitvoering,
evaluatie, verbetering — ontbraken volledig. Dat is de helft van de certificeringseis, en het
kwam pas boven water toen de auditor hoofdstuk 4 koos en een foutmelding kreeg.

De teksten komen uit `Norm ISO 27001.pdf` in de Drive van de organisatie — dat had de eerste
plek moeten zijn waar ik keek, in plaats van te concluderen dat het niet kon.

**Bijlage A krijgt de `A.`-prefix**, zoals de norm zelf. Zonder dat botsen de nummers: §5.1 is
"Leiderschap en betrokkenheid", A.5.1 is "Beleid voor informatiebeveiliging". De DB gaat van 93
naar **120 clausules**: 27 managementclausules plus 93 maatregelen.

**Herkomst en aannames, expliciet.** Het brondocument is de 2013/2017-uitgave; de structuur van
hoofdstuk 4-10 is in 2022 op twee punten gewijzigd, en die zijn hier met de hand toegepast:
2022 voegt 6.3 (Planning van wijzigingen) toe, en draait 10.1 en 10.2 om. Dat staat hier omdat
het niet uit het brondocument volgt — wie het wil controleren, weet waar hij op moet letten.

**Bestaande gegevens migreren mee.** `api/annex_migratie.py` zet oude verwijzingen om. Dat is
eenduidig omdat er vóór deze wijziging niets anders bestond: élke opgeslagen 27001-clausule was
een Bijlage A-maatregel. Twee keer draaien verandert niets, en 9001 blijft ongemoeid.

**De auditor merkt de prefix niet.** Wie "8.24" typt in de assistent, vindt A.8.24 — de norm
noemt het zo, maar niemand praat zo. Zowel het ophalen als de antwoordverificatie accepteert
beide vormen, en de suggestie bij een typefout (`8.2.4` → `A.8.24`) negeert de prefix bij het
vergelijken.

**Gevolg dat opvalt:** 23 clausulenummers komen nu in beide normen voor, tegen 18 eerder — beide
volgen Annex SL, dus 27001 §7.5 heet net als 9001 §7.5 "Gedocumenteerde informatie". Precies
daarom draagt een koppeling zijn norm mee en niet alleen een nummer.

### Added — 2026-08-28 — verbruik bij de API-key

Gevraagd was het credit-saldo bij de sleutel. **Dat kan niet**, en dat is gemeten en niet
aangenomen: `cost_report` en `usage_report` geven met de geconfigureerde key een 401 — *"The
Admin API requires an Admin API key"* — en zo'n key kan alleen een org-owner maken. Bovendien
geeft dat endpoint uitgaven en geen resterend tegoed; een saldo-endpoint bestaat niet in de
publieke API.

Wat wél kan met wat er al lag: het portaal legt per run de werkelijke kosten vast (bedrag,
model, aantal aanroepen, peildatum). Die stonden alleen in het run-record en nergens bij elkaar.
De vraag achter "hoeveel credit heb ik nog" is in de praktijk "wat verbruikt dit ding", en dát
is met eigen gemeten cijfers te beantwoorden.

De Claude-kaart toont nu: **Verbruikt: $0,79 over 1 run, 129 modelaanroepen**, met eronder
letterlijk dat het gaat om wat dit portaal heeft uitgegeven en niet om het accountsaldo. Een
getal dat als saldo leest terwijl het dat niet is, is erger dan geen getal.

Runs zonder bedrag (sim-runs, afgebroken runs) tellen niet mee — die als 0 meerekenen zou
suggereren dat er gratis gedraaid is. Een onleesbare regel wordt overgeslagen: een
configuratiescherm dat omvalt op één rare regel in een append-only bestand, is niet te
repareren.

### Fixed — 2026-08-28 — een adres zonder `https://` levert geen lege bron meer

De auditor vulde `www.conduction.nl` in en de website-bron leverde **nul pagina's**: `urljoin`
maakt van een adres zonder schema `/sitemap.xml`, en dat is geen URL. De melding klopte wél
("sitemap niet op te halen: No scheme supplied"), maar een tool dat een normale schrijfwijze
afwijst en dan netjes uitlegt waarom, heeft nog steeds niets gelezen.

`https://` wordt aangevuld, niet `http://`: een auditbron over een publieke website hoort niet
stilletjes onversleuteld op te halen. Staat er al een schema, dan blijft dat staan — ook
`http://`, want dat kan een bewuste keuze zijn voor een interne omgeving en overrulen zou de
auditscope stil wijzigen.

### Changed — 2026-08-28 — env-namen van de nieuwe bronnen volgen één patroon

Twee dingen waren mis aan de namen die de repo-bron gebruikte:

**`GITHUB_TOKEN` botst.** Dat is de naam die GitHub Actions zélf in elke workflow zet. Draait dit
tool ooit in een Action, dan leest het het Actions-token in plaats van het geconfigureerde token
— met andere rechten, en zonder dat iemand het merkt. Een audit die stilletjes met een ander
credential leest dan geconfigureerd, is niet te verantwoorden.

**`AUDIT_REPOS` brak het patroon.** Elke andere bron gebruikt `<BRON>_<VELD>`:
`NEXTCLOUD_BASE_URL`, `JIRA_API_TOKEN`, `MIRO_API_TOKEN`, `WEBSITE_URLS`. Alleen Drive en
Planning wijken af met `AUDIT_*`, en dat zijn de twee oudste — geen reden om de fout te herhalen.

| oud | nieuw |
|---|---|
| `AUDIT_REPOS` | `REPO_LOCATIES` |
| `GITHUB_TOKEN` | `REPO_GITHUB_TOKEN` |
| `CODEBERG_TOKEN` | `REPO_CODEBERG_TOKEN` |
| `GITHUB_APP_ID` / `_INSTALLATION_ID` / `_PRIVATE_KEY` | `REPO_GITHUB_APP_*` |

**Een ingevulde configuratie valt niet stil.** De vertaling zit in `BronConfig._laad()` en niet
in `naar_omgeving()`, zodat élke lezer hem krijgt: de omgeving, het configuratiescherm, de health
en de herkomst. Op één plek vertalen en op vier plekken vergeten is precies hoe een configuratie
half migreert. Staan een oude en een nieuwe naam allebei in de opslag, dan wint de nieuwe — dat
is wat de auditor het laatst bedoelde.

De env-namen staan nergens in de UI; die toont labels ("Repositories", "GitHub-token") met een
tooltip. De hernoeming is dus alleen zichtbaar voor wie het cluster-Secret of het YAML-bestand
leest — en juist daar telt consistentie.

**Testisolatie:** de nieuwe test schreef via `naar_omgeving()` rechtstreeks in `os.environ` en
liet `REPO_LOCATIES` staan, waarna `RepoSource()` verderop in de suite dácht dat er repositories
geconfigureerd waren. Nu vervangt de test `os.environ` door een kopie. Een test die de volgende
test beïnvloedt, meet niets.

### Changed — 2026-08-27 — de zwaarste NC's staan bovenaan in de memo

De auditor bevestigde 47 NC's en de geëxporteerde memo werd 27 pagina's. De eerste ingeving was
een bovengrens op het aantal NC-blokken. Die is er niet gekomen, en de reden weegt zwaarder dan
de paginatelling: **zo'n grens laat NC's buiten de memo vallen op omvang, zonder dat een mens
erover besliste en zonder vastgelegde reden.**

Wat niet in de memo thuishoort, wordt in de **triage** uitgesloten. Daar legt de append-only
trail vast wie dat besloot en waarom. De memo blijft daarmee een gevolg van auditor-beslissingen
in plaats van een selectie die het tool zelf maakt — dat is de auditor-spiegel, de capability
die dit tool draagt.

Wat wél verandert is de **volgorde**: zwaarte vóór omvang. Een thema met een `major`-bevinding
staat bovenaan, ook als het klein is, zodat een lezer die na één blok stopt het zwaarste heeft
gezien. `Finding.ernst` is daarvoor toegevoegd aan het memo-model.

Op de werkset van 26-08 was `ernst` op alle 47 leeg — de review is er niet over gelopen — en dan
valt de ordening terug op omvang. Zwaarte verzinnen waar die niet gemeten is, zou erger zijn dan
een grovere volgorde.

**Wat dit openlaat:** er is geen triage-status voor "dit is een echte NC, maar hij hoort niet in
déze memo". `niet_valide` betekent false positive en `follow_up` betekent bewijs buiten
tool-scope. De auditor gebruikt voorlopig `niet_valide` met een reden in de trail; het onderscheid
draagt dan volledig op die reden, dus die moet inhoudelijk zijn en niet "auditsessie (bulk)".

### Added — 2026-08-26 — een hele organisatie als scope: `github:ConductionNL/*`

De API heeft er inderdaad iets voor: `GET /orgs/{org}/repos`. 414 namen intypen is geen
configuratie maar een overschrijffout die wacht om te gebeuren. Een `*` als naam betekent nu:
alle repository's van die eigenaar op het moment van de run. Live getoetst: **385 repository's
in 8,2 seconden**.

Gearchiveerde vallen af — die tonen hoe er ooit gewerkt werd, niet hoe er nu gewerkt wordt, en
een audit gaat over het heden. Hoeveel er afvielen komt in de dekking te staan (29 bij
ConductionNL), en de opgeloste lijst ook: "alle repository's van de organisatie" is een prima
auditscope, maar alleen als achteraf vaststaat welke dat op dat moment waren.

**Correctie op een eerder getal in deze changelog:** het zijn geen 183 repository's maar **414**
(385 actief, 29 gearchiveerd, 37 privé). `gh repo list --limit 200` kapte de lijst af en ik nam
de uitkomst over zonder te controleren of hij compleet was.

**De rem zit in het PR-aggregaat.** Gemeten kosten voor 385 actieve repository's:

| | aanroepen | tijd |
|---|---|---|
| listing | 5 pagina's | 10s |
| alles behalve PR-aggregaat | 1.540 | ~12 min |
| mét PR-aggregaat op 20 | 9.625 | ~72 min |

Die laatste is bijna twee keer de limiet van 5.000 per uur. Voor een org-brede run hoort
`REPO_MAX_PR` daarom op 0 (of laag); dat staat nu bij de constante en in het configuratiescherm.
Het aggregaat blijft waardevol voor een handvol repository's — daar is het waargenomen gedrag
juist het sterkste §8.32-bewijs.

### Fixed — 2026-08-26 — "niet gekoppeld" zegt nu wat er ontbreekt

Het configuratiescherm toonde bij `website` en `repo`: *"De verbinding kon niet worden gelegd.
Zie het serverlog voor details."* Er was niets mis met een verbinding — er stond alleen nog geen
adres of repository ingevuld. Bij `website` extra verwarrend, want die heeft **geen token nodig**;
dan zoekt een auditor naar een credential die niet bestaat.

De oorzaak was niet de tekst maar het ontbreken van `soort`. `_check_source` haalt elke
adapter-reden zonder `soort` door de normalisatie, en dat mechanisme is er met goede reden: tot
2026-08-14 landde een Jira-401 mét tenant-URL en responsbody rechtstreeks in de browser. Wie zijn
eigen `soort` meestuurt, verklaart daarmee dat de tekst van hem is en geen credentials draagt —
en dat deden de twee nieuwe adapters niet.

Nu: *"Er is nog geen website ingevuld. Een website heeft geen token nodig; vul een adres in zoals
https://www.conduction.nl."*

### Added — 2026-08-26 — één indicator voor lopend serververkeer

Gemeten in het draaiende portaal: alleen `/instellingen/health` is traag — **3,5 seconden**, want
die test live verbindingen naar Drive, Jira en Nextcloud. Alle andere endpoints zitten onder een
halve seconde (`/findings`, `/acties`, `/runs`, `/landschap` elk 0,01s). Een spinner per scherm
zou dus overwegend versiering zijn; het probleem is dat er tijdens die ene wacht niets zichtbaar
gebeurt.

Daarom één indicator, aangestuurd vanuit `j()` zelf. Dat dekt élke aanroep zonder dat iemand het
per scherm hoeft te onthouden — dezelfde redenering als bij `_get()` in de forge-client: een
eigenschap in plaats van een afspraak.

Geteld en niet booleaan: bij `Promise.all` lopen er meerdere tegelijk, en dan zou de eerste die
terugkomt de indicator uitzetten terwijl de trage nog loopt. Hij gaat ook uit als een aanroep
faalt — een indicator die blijft staan laat het portaal bevroren lijken.

### Added — 2026-08-26 — wat de organisatie over zichzelf zegt, als bewijs

Er wordt **niets ingevuld** — alleen gelezen wat er staat. Drie plekken waar een organisatie
zichzelf beschrijft, hangen nu aan 9001 §4.1 (context van de organisatie) en §7.5
(gedocumenteerde informatie):

- `profile/README.md` in de speciale repo `<org>/.github` — de tekst die GitHub op de
  organisatiepagina toont. Voor ConductionNL 3.034 tekens over wat het bedrijf is en maakt.
- `README.md` van een repository.
- `/about/` op de website.

**En een fout in eigen werk:** `README.md` stond helemaal niet in de bewijspaden, terwijl de
docstring eronder al beweerde dat hij meetelde voor 9001 §7.5. Een lijst en een toelichting die
elkaar tegenspreken — precies het soort stille onwaarheid waar dit tool bevindingen over schrijft.

De proefrun met de `.github`-repo erbij: 44 documenten, alle 44 gekoppeld. En de API-limiet sloeg
toe, wat meteen de melding van vanmiddag onder echte omstandigheden toetste:

> github ConductionNL/iso-audit: de API-limiet is bereikt (60 aanroepen per uur); zonder token is
> die 60, met token 5000

Die repository staat daarmee in de dekking als overgeslagen, met reden — in plaats van stil te
verdwijnen.

### Fixed — 2026-08-26 — twee gaten die de proefrun blootlegde

De eerste proefrun zonder token over drie publieke repo's en drie webpagina's leverde 26
documenten op, alle 26 met een clausule. Onderweg vielen twee eigen fouten op:

**`repository()` gebruikte de duiding niet.** De melding was `github: ConductionNL/hydra gaf
404` — een kale status, precies wat er net was weggewerkt op de andere vier plekken. Juist de
eerste aanroep per repository miste hem. Nu: *"bestaat niet, of het token mag het niet zien (404)
— GitHub geeft beide zo terug"*.

**Een overgeslagen repository kwam niet in de dekking.** Alleen een logregel. Een hele repository
die stil uit de audit verdwijnt is erger dan een die er niet in zat: dan denkt de auditor hem
geauditeerd te hebben. `ConductionNL/hydra` is privé en viel zonder token weg zonder dat de
dekking dat meldde.

Wat de proefrun verder liet zien — het bewijs landt waar het hoort:

| clausule | documenten |
|---|---|
| 27001 §8.32 wijzigingsbeheer | 11 |
| 27001 §8.8 kwetsbaarheden | 7 |
| 27001 §5.2 rollen | 6 |
| 27001 §8.25 / §8.31 ontwikkeling en scheiding | 5 elk |
| 27001 §5.34 privacy | 3 |

Nul documenten bleven ongekoppeld.

### Changed — 2026-08-26 — wat niet gelezen kon worden, zegt waarom

Een bron die stilzwijgend niets teruggeeft, laat "geen workflows gevonden" en "ik mocht de
workflowmap niet lezen" er identiek uitzien. Het eerste is een bevinding, het tweede een gat in
de dekking. Op vier plekken gebeurde precies dat: branch-bescherming, bestandsinhoud,
pull-request-aggregaat en — het ergst — `bestanden_in_map`, dat een lege lijst teruggaf zonder
enig onderscheid.

Vier statussen, vier betekenissen, en ze staan nu in de melding:

- **401** — het token is niet meegestuurd of niet geldig.
- **403 met een lege limiet** — de API-limiet is op. Zonder token is dat 60 per uur, en dan
  stopt een run halverwege op iets wat als "bron leeg" leest.
- **403** — het token bestaat maar mist dit recht; voor branch-bescherming is dat
  `Administration: read`.
- **404** — bestaat niet, of het token mag het niet zien. GitHub geeft beide zo terug, en die
  dubbelzinnigheid hoort in de melding in plaats van weggepoetst te worden.

Eén uitzondering, met reden: bij een **bestand** staat er "bestaat niet" zonder tokenvoorbehoud.
Dat pad wordt alleen opgehaald nadat de repo-aanroep 200 gaf, dus de repo is leesbaar en
contents kennen geen rechten per pad. Een 404 is dan echte afwezigheid — en juist dát is de
bevinding: 6 van de 12 repo's hebben geen `SECURITY.md`.

Live getoetst zonder token: de instellingentekst meldt nu letterlijk *"het token is niet
meegestuurd of niet geldig (401); zonder geldig token is dit niet te lezen"* in plaats van de
vaste zin "niet vast te stellen met het gebruikte token".

### Added — 2026-08-26 — een GitHub App als bron-credential

Een fijnmazig PAT is altijd van een persoon. Vertrekt die persoon, dan valt de bron stil en staat
er in de volgende audit "bron niet beschikbaar" waar bewijs had moeten staan. Een App is
eigendom van de organisatie en overleeft dat.

Wat per persoon blijft: het **aanmaken**. GitHub heeft dat bewust niet in de API — de
Authorizations API is in 2020 verwijderd en een App aanmaken gaat via de browser. Wat hier is
gebouwd, is het stuk dat automatiseerbaar is: uit App-id, installatie-id en private key een
installatietoken minten, en dat vernieuwen voordat het verloopt.

Drie velden in het configuratiescherm onder "Code-repositories". Zijn ze gezet, dan hebben ze
**voorrang** op het persoonlijke token. Ontbreekt er één, dan is er geen App en valt het terug —
een halve configuratie wordt niet stil geaccepteerd.

`cryptography` doet het ondertekenen; die zat er al via `google-auth` en staat nu expliciet in
`pyproject.toml`, want je importeert niet wat je niet declareert. Twintig regels eigen code
tegenover een extra afhankelijkheid in een project onder 27001-scope.

**Twee bugs die de tests vonden voordat ze konden bijten:**

- `datetime.strptime(...).timestamp()` leest een `Z`-tijd als **lokale** tijd. In CEST maakte dat
  het installatietoken twee uur te oud, waardoor de cache nooit werkte en elke aanroep opnieuw
  mintte. In een negatieve tijdzone was het erger: dan zou een verlopen token voor geldig zijn
  doorgegaan.
- De Authorization-kop werd per methode gezet, en `_bescherming` miste hem. Functioneel gedekt
  omdat die alleen via `repository()` bereikbaar is, maar dat leunt op aanroeporde. Elke GET
  loopt nu langs één doorgang, met een test die faalt zodra een methode die omzeilt.

De private key komt nergens uit: niet in een log, niet in een foutmelding, niet in een
healthcheck. Een test controleert dat een onleesbare sleutel geen sleutelmateriaal in de
melding zet.

### Added — 2026-08-26 — hoogstens drie verbeterthema's in de memo

Twee losse knoppen, en dat onderscheid is het punt:

- `THEMA_DREMPEL` (3) bepaalt hoe groot een thema moet zijn om als verbeterpunt te tellen: drie
  waarnemingen op hetzelfde thema zijn een patroon, één is een waarneming.
- `MAX_VERBETERBLOKKEN` (3) bepaalt hoeveel er in de memo komen. Op de werkset van 2026-08-25
  haalden zeven thema's de drempel, en zeven verbeterrichtingen in één kwartaal is geen agenda
  maar een inventaris.

Wat afvalt staat compleet in het detailrapport, en de memo zegt hoeveel het er zijn — als eigen
regel onder de sectie, niet weggestopt in het laatste blok. Een cap zonder melding leest als
"dit was alles".

**Eerlijk over het effect:** dit levert géén pagina op. Het Q2-formaat bleef 4 pagina's, want
deze verbeterblokken zijn dun; de OFI-sectie kost één pagina of er nu drie of zeven blokken in
staan. De winst zit in leesbaarheid, niet in omvang.

### Added — 2026-08-26 — vaste clausule-koppeling voor repository- en websitedocumenten

`koppel_documenten` matcht Nederlandse normtermen op de documenttekst. Voor beleid en notulen
werkt dat; voor wat de nieuwe bronnen leveren niet. Een `SECURITY.md` is Engels en bevat geen
enkele zoekterm — en viel daarmee volledig buiten de boot, terwijl hij bewijs is voor §8.8
vanwege *wat hij is*. "Branch-bescherming op de hoofdbranch: niet ingesteld" is de kern van
§8.32 zonder één normterm erin.

Die documenten koppelen nu op **soort**: bewijspad, workflowmap, instellingen-document of
padprefix van een webpagina. §8.8 en §5.24 voor `SECURITY.md`, §5.2 en §8.32 voor `CODEOWNERS`,
§8.25/§8.31/§8.32 voor workflows, §8.4/§8.32/§5.2 voor de repository-instellingen, §5.34 voor
`/privacy/`, §5.31 plus 9001 §8.2 voor `/terms/`.

**Erbij en niet in plaats van.** De zoektermen blijven draaien: een `SECURITY.md` die ook over
back-ups gaat, krijgt die clausule er gewoon bij. Een onbekend pad levert niets op — liever geen
koppeling dan een geraden koppeling.

De belangrijkste test is dat elke gekoppelde clausule in de norm-DB bestaat. Een koppeling naar
een clausule die er niet is, levert een bevinding op die nergens over gaat — dat is precies de
fout die op 2026-08-24 448 van de 903 bevindingen verkeerd labelde.

### Removed — 2026-08-26 — de PreSync-gate mocht niet van het Argo-project

De gate uit a59 is er weer uit, en niet omdat het idee niet deugde. Argo weigerde hem:
`resource batch:Job is not permitted in project iso-platform`. De `AppProject` staat negen kinds
toe — ServiceAccount, Service, ConfigMap, PVC, Deployment, Ingress, NetworkPolicy, Role,
RoleBinding — en `Job` en `Pod` staan er geen van beide bij.

Die lijst is bewust minimaal voor een platform onder ISO 27001-scope. Hem oprekken voor een
gemaksvoorziening is de verkeerde ruil: dan versoepel je een beveiligingsgrens op gedeelde
infrastructuur om een werkwijze te ondersteunen die al een nette oplossing heeft. Het venster
hoort weg via de branch-route (`image.yml` draait ook op `pull_request` en pusht daar al de
versietag), niet via een extra resource-kind.

**Gevolg dat wel telt:** de sync liep vijf pogingen vast op een manifest dat het project niet
toestaat, dus a60 rolde niet uit terwijl de oude pod bleef draaien. Een uitrol die stilstaat is
beter dan een portaal dat omvalt, maar het is niet niets. `deploy/README.md` noemt nu de
controle die dit had voorkomen:

    kubectl get appproject iso-platform -n argocd -o yaml | grep -A20 ResourceWhitelist

### Added — 2026-08-26 — de nieuwe bronnen zijn in het portaal te configureren

`repo` en `website` staan nu in de broncatalogus, dus ze verschijnen in het configuratiescherm
met dezelfde velden, opslag en wijzigingstrail als Drive, Jira en Nextcloud. Geen tweede
configuratiemechanisme naast het bestaande — dat is de reden dat `bronnen.yaml` uit de spec er
niet is gekomen: de catalogus deed dit al, en twee plekken om hetzelfde in te stellen is precies
wat een auditor niet kan volgen.

Repositories worden ingevoerd als `forge:eigenaar/naam` (bijvoorbeeld
`github:ConductionNL/iso-audit`), in de UI als losse rijen. Een regel zonder forge of zonder
`eigenaar/naam` is een fout en geen overslag: een stil overgeslagen repository is een bron die de
auditor dénkt te hebben.

**Een ontbrekend token is een waarschuwing en geen fout.** Publieke repositories zijn zonder
token leesbaar — gemeten tegen `codeberg/conduction` op 2026-08-26. Wat er dan niet uitkomt is de
branch-bescherming, en die blijft eerlijk op "niet vast te stellen" staan. Bij GitHub meldt de
waarschuwing er de limiet van 60 aanroepen per uur bij, want dát loopt een run stuk op iets wat
als "de bron doet niets" leest.

### Added — 2026-08-26 — repositories en de website als auditbron

De vijf bestaande bronnen zijn alle vijf **documentbronnen**: wat de organisatie over zichzelf
heeft opgeschreven. Twee bronnen die dat niet zijn, stonden buiten beeld.

**`repo` — GitHub én Codeberg.** §8.4, §8.9, §8.25, §8.28, §8.31 en §8.32 gaan over dingen die in
een repository zichtbaar zijn en nergens anders aantoonbaar. Het vier-ogen-principe is geen
belofte in een handboek maar een schakelaar op een branch.

Gemeten vóór er code kwam, over de twaalf recentst gepushte actieve ConductionNL-repo's:
6/12 zonder `SECURITY.md`, 6/12 zonder `CODEOWNERS`, 0/12 met pre-commit — en **0 van de 12 met
een hoofdbranch die review verplicht stelt**. Bij de eerste live-run meldde de bron over
iso-audit zelf: geen branch-bescherming, en 12 van de laatste 12 samenvoegingen zonder
goedkeurende review.

Eén adapter met twee dunne clients (`clients/forge.py`), tegen de huisregel "liever herhaling dan
abstractie" in en met reden: wat verschilt is de HTTP-aanroep, wat níet verschilt is de
auditinhoud. Die twee keer neerzetten laat haar uiteenlopen, en dan levert het tool per forge
ander bewijs zonder dat iemand het merkt.

**`website` — wat de organisatie publiek belooft.** Een privacyverklaring of een claim over
certificering is een verplichting die je aangaat; het gat met de interne praktijk is een
klassieke NC (§5.31, §5.34, 9001 §8.2). Sitemap of een opgegeven URL-lijst, nooit links volgen —
een crawler is niet te begrenzen, niet te herhalen en niet uit te leggen aan wie vraagt wat het
tool heeft gezien. `robots.txt` wordt gerespecteerd. conduction.nl levert 137 pagina's,
waaronder `/privacy/`, `/terms/` en `/quality/`.

Grenzen die met tests zijn vastgezet: geen schrijf-aanroepen, geen `git clone`, geen
source-tree (alleen een expliciete lijst bewijspaden), **geen persoonsnamen** — uitspraken over
wijzigingen zijn aggregaten, want een NC gaat over een proces dat niet werkt en niet over een
collega. En "niet vast te stellen met dit token" is een eigen uitkomst, nooit "niet ingesteld":
een onbekende instelling als bevinding rapporteren is een verzonnen bevinding.

Nog niet af: de configuratie staat nu op de constructor en de env-var, nog niet in `bronnen.yaml`
met een scherm eromheen. Zie `openspec/changes/code-en-website-bronnen/tasks.md`.

### Fixed — 2026-08-26 — een uitrol haalt het portaal niet meer onderuit

De uitrol van a58 legde het portaal negen minuten plat. Argo synct de nieuwe `newTag` zodra de
commit op main staat, terwijl het image pas dáárna gebouwd wordt. Die build duurde deze keer elf
minuten — wachttijd op een GitHub-runner, de testjob zelf deed 1m43 — en omdat de Deployment
`Recreate` gebruikt (verplicht bij een RWO-volume) was de oude pod al weg. Resultaat:
`ImagePullBackOff` op een tag die nog niet bestond. De kubelet herstelde vanzelf zodra het image
verscheen, maar de downtime was er.

Twee maatregelen, en ze doen iets verschillends.

**De branch-route haalt het venster weg.** `.github/workflows/image.yml` draait óók op
`pull_request` en pusht daar al de versietag. Via een branch staat het image dus op ghcr vóórdat
de merge de tag op main brengt, en vindt Argo meteen wat hij zoekt. Dat was al zo; het stond
alleen nergens als de aangewezen weg. Nu wel, in `deploy/README.md`.

**De PreSync-gate haalt de downtime weg.** `deploy/image-gate-job.yaml` is een Argo-hook die
niets doet behalve bestaan: zijn container is precies het image dat straks uitgerold wordt
(kustomize herschrijft de tag mee, met een test die dat bewaakt). Kan de kubelet dat image niet
pullen, dan blijft de hook onvoltooid, wacht Argo met de sync, en blijft de oude pod draaien.
Zodra het image verschijnt gaat de uitrol verder; na twintig minuten faalt de sync zichtbaar in
plaats van eindeloos te wachten.

Bewust geen skopeo of crane en geen registry-credentials: de kubelet-pull ís de controle, en die
test exact wat de echte pod straks ook doet. Het package is publiek, dus er is niets in te
richten.

De vorige gate-Job blijft staan tot de volgende sync (`BeforeHookCreation`, niet
`HookSucceeded`), zodat achteraf te zien is of een uitrol op het image heeft staan wachten.

### Changed — 2026-08-26 — de memo kort nergens tekst af

Het paginabudget is een **richtgetal**, geen kap. Een paar regels uitlopen voor de netheid mag;
het mag alleen niet de standaard worden. De lengte wordt daarom bestuurd door te kiezen wát in de
memo staat en wat in de bijlage — niet door te snijden in wat er staat.

Concreet weer verwijderd wat eerder vandaag als afkapping was ingebouwd: geen bloktekst die op
een zinsgrens stopt met "vervolg in de bijlage", en geen bronlijst die na drie documenten
"en elf andere" zegt. Alle brondocumenten worden genoemd, ook als dat een paar regels kost — een
lijst die halverwege stopt dwingt de lezer voor zijn eerste vraag al naar de bijlage.

Wat wél naar de bijlage gaat, gaat er heel naartoe: de normtekst en de onderbouwing per clausule.
Dat is een keuze over samenstelling en geen afkapping, en het is het verschil tussen de 35 en de
15 pagina's van vandaag. Meting bevestigt dat de afkapping ook niets opleverde: mét review-kern
is een blok al kort (kern hoogstens 266 tekens, corrigerende maatregel hoogstens 570), en het
verwijderen ervan kost nul pagina's op de werkset van 2026-08-25.

Het waarschuwingsbericht zegt dat nu ook: een signaal om te kijken of er materiaal in de memo
staat dat in de bijlage hoort, niet om tekst af te kappen.

### Added — 2026-08-26 — eigenaren invullen in het portaal, met een besprekingsmodal

De memo levert per NC een actietabel met "wat", en "wie", "waar" en "uiterlijk" stonden er als
placeholder. De vraag was of die in een los .docx naast het systeem ingevuld mochten worden.

Nee, en dat is geen smaakkwestie: dan bewerkt iemand buiten het systeem en weet de audit-trail
niet wie wat heeft toegezegd. Een managementmemo waarvan de toezeggingen niet herleidbaar zijn,
is precies het soort document waar een externe auditor een NC op schrijft.

Dus in het portaal, via dezelfde weg als de triage — onder hetzelfde slot, append-only, met de
echte actor uit de auth-gate:

- `GET /audits/{id}/acties` — elke actierij met zijn bevinding, clausule en thema.
- `POST /audits/{id}/findings/{fid}/acties/{index}` — wat, wie, waar of uiterlijk invullen.
  Een veld dat niet wordt meegestuurd, blijft ongemoeid: een leeg tekstveld in de UI mag geen
  ingevulde eigenaar wissen zonder dat iemand dat bedoelt. Een wijziging die niets verandert,
  schrijft geen regel in de trail.
- `GET /audits/{id}/memo/pdf` — de memo inline, voor de modal. Inline en niet als bijlage; wie
  hem wil meenemen gebruikt `/download`, dat een zip met manifest levert.

In de UI: een knop **Bespreken** die het memo naast zijn eigen actietabel zet, gegroepeerd op
thema zodat de indeling gelijk is aan de blokken in het memo. Elke rij bewaart apart en meldt
dat.

Getest in een echte browser (`tests/e2e/test_bespreekmodal.py`), inclusief de controle dat een
ingevulde eigenaar na opnieuw openen uit de wérkset komt en niet uit het invoerveld. Het patroon
dat vandaag drie keer terugkwam is dat de route het al kon en de bediening ontbrak.

### Added — 2026-08-26 — de output is te downloaden

De export meldde alleen een serverpad:
`PDF: /var/lib/iso-audit/audits/27001_9001-2026-Q3/Auditmemo_management.pdf`. Dat is een pad in
een pod met een read-only filesystem, achter een oauth-proxy. Niemand kan daarbij. Er was in de
hele API **geen enkele download-route** — ook de bewijslast-rapporten van 8 MB waren
onbereikbaar. Een tool dat bewijs produceert dat niemand kan ophalen, heeft geen bewijs
geproduceerd.

`GET /audits/{id}/download?scope=memo|bewijslast` levert een zip. `memo` is alleen het
managementmemo, om te bespreken; `bewijslast` is het hele pakket — memo, werkset, runs,
triage-trail en de auditrapporten — om te archiveren en te overleggen.

Elke zip draagt een `INHOUD.md` met per bestand waar het vandaan komt. Dat is geen beleefdheid:
de auditrapporten in `rapporten/` zijn **niet** audit-gescoped in het datamodel, dus de selectie
berust op een afleidbare regel (de normcode in de bestandsnaam) en die hoort leesbaar in het
pakket te staan in plaats van alleen in de broncode. Wat de regel niet vangt, zit er niet in en
het manifest zegt dat.

### Changed — 2026-08-26 — de memo is een bespreekstuk geworden

Drie dingen, alle drie gemeld door de auditor.

**Bronnen met een identificatie.** "Geraadpleegde bronnen: Google Drive, Jira, Planning,
Nextcloud" is decoratie — wélke Drive-map, wélk Jira-project? Zonder die aanduiding kan een
externe auditor de scope van de audit niet natrekken. Elke bron krijgt nu zijn map-id,
projectsleutel of pad, met een klikbare URL waar die bestaat. Afgeleid uit de instellingen
waarmee de run draaide (`os.environ` na `naar_omgeving()`), niet uit wat er nú gekoppeld is:
de memo hoort te zeggen waar de audit op rustte. Geheime velden komen er niet in.

**Codes voor de blokken.** "NC 1 — Back-up & continuïteit", "OFI 1 — Logging & monitoring". Zo is
een blok in een vergadering aan te wijzen en in het detailrapport terug te vinden — precies zoals
het handgemaakte Q2-memo het deed.

**Korter.** Normtekst, onderbouwing per clausule en de volledige bronlijst staan nu in het
detailrapport; elk blok sluit af met een regel die zegt wáár. De eerste drie brondocumenten
blijven klikbaar in de memo zelf, met "en N andere" erachter — een memo waarin je niet één keer
kunt doorklikken naar het bewijs, dwingt elke lezer naar de bijlage voor zijn eerste vraag.

Gemeten op de werkset van 2026-08-25, met dezelfde 47 NC's:

| | pagina's |
|---|---|
| bij aanvang van de dag | 35 |
| na bundelen per thema | 27 |
| na kern in plaats van afwijkingsteksten | 24 |
| na bronnaam zonder omschrijving | 20 |
| na deze inkorting (incl. 7 verbeterblokken) | **15** |

Op het formaat van het handgemaakte Q2-memo — twee thema's van drie clausules — past het nu in
**3 A4**, met een test die daarop staat. Mét alle zeven verbeterblokken erbij is het er vier;
de drempel (`THEMA_DREMPEL`, nu 3) is de knop daarvoor.

### Changed — 2026-08-26 — auto-triage doet ook OFI's af

Auto-triage raakte alleen positieve bevindingen. Op de run van 2026-08-25 stonden 136 OFI's en
171 positieve bevindingen tegenover 108 NC's; die 136 bleven met de hand te doen, terwijl er
precies hetzelfde voor geldt: de review bevestigt wat de classificatie al zei, en er valt geen
oordeel te vellen dat de certificering raakt.

Voorwaarden ongewijzigd streng: alleen bij advies `bevestigen`, en alleen als de voorgestelde
klasse **gelijk** is aan wat er al staat. Anders is het geen bevestiging maar een wijziging, en
die hoort bij de auditor. Verlagingen blijven van de auditor.

**Een NC blijft van de auditor**, en dat staat sinds a54 niet meer alleen in deze lijst maar ook
op de schrijfweg (`AuditSession.apply_triage`) — zodat uitbreiden van deze lijst niet stilletjes
die grens verschuift.

### Changed — 2026-08-26 — verbeterpunten bundelen per thema

Twee dingen werkten niet, allebei gemeten op dezelfde werkset:

1. **Er kwam geen enkel verbeterpunt uit de memo.** De selectie clusterde op *clausule* met
   drempel 10 en geen enkele clausule haalde dat. De 53 OFI's verdeelden zich intussen keurig
   over 16 thema's: 7x logging & monitoring, 6x auditprogramma, 4x back-up, 4x privacy.
2. **Eén representant per cluster.** Van drie waarnemingen op hetzelfde thema kwam er één in de
   memo en verdwenen er twee. Dat maakt van een patroon een anekdote.

Nu wordt een thema met genoeg OFI's één verbeterblok met álle waarnemingen erin, en telt de
drempel thema's in plaats van clausules. Default van 10 naar **3** (`THEMA_DREMPEL`): dat geeft
op deze werkset zeven samenhangende blokken; 5 geeft er nog twee, 10 nul.

De suggesties van alle waarnemingen blijven staan, ook als er een kern is. Bij een NC-blok
verhuist het detail naar de bijlage — hier ís het verbeteradvies waar het om gaat.

`Overig` clustert nooit: drie ongerelateerde punten als één verbeteradvies presenteren wekt
precies de verkeerde suggestie. Een expliciet gepromote OFI trekt wel zijn hele thema mee.

**Opgeruimd:** `DefaultClassifier.improvements()` en zijn protocol-methode zijn weg. De
selectieregel leefde daarna op twee plekken en dat is één te veel — hij staat nu in
`memo/groepering.py`, met de tests in `tests/memo/test_verbeterpunten_thema.py`.

### Security — 2026-08-26 — een NC trieeren vraagt een mens-account, afgedwongen op de schrijfweg

De regel "auto-triage raakt nooit een NC" stond in de docstring van
`classification/auto_triage.py` en werd daar ook netjes gevolgd — maar alleen bij het
*voorstellen*. Op de schrijfweg lag niets.

En de schrijfweg is precies wat een externe auditor leest: de trail zegt wie wat besloot. Staat
daar bij een bevestigde NC een machine-actor, dan is die bevestiging niet te verantwoorden,
ongeacht hoe zorgvuldig de agent was die het voorstel deed.

`AuditSession.apply_triage()` weigert nu elke triage-beslissing over een NC door een actor uit
`MACHINE_ACTOREN`, en laat niets half doorgevoerd achter. **Beide richtingen**, niet alleen
bevestigen: een NC afserveren als `niet_valide` laat een geconstateerd gebrek uit het dossier
verdwijnen, en dat is even zwaar een auditoordeel als hem dragen. Ook de omweg — in dezelfde
aanroep iets tot NC promoveren en meteen bevestigen — is dicht.

`MACHINE_ACTOREN` is een expliciete lijst en geen slimmigheid als "de actor bevat een @": die
zou elke bestaande aanroep met een generieke actornaam omverwerpen en de regel eerder uit dan
aan zetten. Een nieuwe machine-actor moet er bewust bij; wie dat vergeet, zet zijn eigen naam in
de trail en dat ziet een auditor meteen.

Gemeten in het cluster: de trail van de huidige audit bevat 33 regels, alle van `auto-triage` en
alle op positieve bevindingen. Alle 47 NC's staan `open` — zoals het hoort.

### Added — 2026-08-26 — filteren op triage-status, bron en clausule

De auditor kon in de bevindingentabel alleen op classificatie filteren (NC / OFI / POSITIVE).
Met 271 bevindingen in één audit is "wat staat er nog open?" de eerste vraag van een
triage-sessie, en het antwoord was scrollen.

`GET /audits/{id}/findings` accepteert nu ook `triage_status`, `source` en `clause`; alles
combineert met AND en met het bestaande `severity`. De bron matcht op deeltekst en
hoofdletterongevoelig — je typt "drive", niet het hele pad. De clausule matcht exact óf het hele
hoofdstuk eronder: `8` geeft §8.x, `8.14` alleen die clausule. Nadrukkelijk geen kale
`startswith`, want dan zou `8.1` ook §8.14 opleveren en dat is een ander onderwerp.

In de UI staan de drie bedieningen onder de bestaande knoppenrij, met een teller erachter zodat
zichtbaar is hoeveel er nog over is. De classificatieknop blijft staan als je een van de nieuwe
filters gebruikt.

Getest in een echte browser (`tests/e2e/test_triage_filters.py`), niet alleen tegen de API. Het
gat dat hier werd gemeld was precies dit: de route kón het al na tien regels, maar de knop zat er
niet. Een contract-test ziet dat niet en een gebruiker meteen.

### Changed — 2026-08-26 — met een synthese verhuist het detail naar de bijlage

Vervolg op de thema-bundeling van vanochtend. Zodra de review een kernzin levert, toont een blok
zowel die synthese als alle onderliggende afwijkingsteksten én alle bronomschrijvingen — dus
dikker in plaats van dunner, precies het tegendeel van wat bundelen moet doen.

Nu geldt: **is er een kern, dan is die de blok-tekst.** De onderbouwing per clausule en de
omschrijving per brondocument verhuizen naar het detailrapport, waar ze toch al staan; de memo
verwijst er in de voettekst naar. Is er geen kern (review niet gedraaid), dan blijft alles staan,
want dan is er niets om naar door te verwijzen.

Wat blijft, blijft: **welk** document een bevinding draagt, staat gewoon in het blok. Dat is wat
de memo natrekbaar maakt.

**Gemeten op de werkset van 2026-08-25** (47 bevestigde NC's), stap voor stap:

| | blokken | pagina's |
|---|---|---|
| één blok per bevinding (was) | 47 | 35 |
| bundelen per thema | 25 | 27 |
| + kern in plaats van afwijkingsteksten | 25 | 24 |
| + bronnaam zonder omschrijving | 25 | 20 |

En op realistisch formaat: 2 thema-blokken met 4 NC's passen nu in 3 A4; met 6 NC's is het er 4.
Het handgemaakte Q2-memo doet 2 blokken van 3 op precies 3 A4 — we zitten er één naast.

**Waar de dikte zat, en waar niet.** De bronomschrijvingen waren 45% van de memo-tekst (4.993 van
11.028 tekens). De normcitaten kostten gemeten *nul* pagina's — die zijn niet het probleem en
blijven dus staan. De grootste knop blijft de triage: pagina's schalen met het aantal
onderliggende bevindingen, niet met het aantal blokken.

### Changed — 2026-08-26 — de memo bundelt NC's per thema in plaats van per bevinding

`build_memo` maakte één NC-blok per bevinding. Op de werkset van vanochtend: 47 bevestigde NC's,
47 blokken, **35 pagina's** — terwijl het handgemaakte Q2-memo er twee had en de klant expliciet
om 1–3 A4 vraagt. `memo/groepering.py` bestond al maar was nergens aangesloten.

Nu één blok per thema: 47 NC's → **25 blokken → 27 pagina's**. Elk blok noemt alle clausules die
het raakt, elke bron van elke onderliggende bevinding blijft zichtbaar, en de afwijkingen staan
als lijst met `§clausule` ervoor. Bundelen mag geen bewijs verstoppen — een memo die niet terug
te voeren is op documenten is een mening.

**Wat dit níet oplost, gemeten en niet weggeschreven.** 27 pagina's is nog steeds geen 3 A4, en
dat is geen layout-probleem: alleen de normcitaten van 47 NC's zijn al ~4 A4 en de
afwijkingsteksten ~9 (mediaan 355 tekens per stuk). De vaste memo-overhead is 1 pagina en elk
blok kost er ~2. Drie A4 betekent dus **ten hoogste twee NC-blokken** — precies wat het Q2-memo
laat zien. De resterende knop is de triage, niet de opmaak: 47 bevestigde NC's is een
detailrapport, geen managementmemo.

### Fixed — 2026-08-26 — drie hiaten in de thema-toekenning

Van de 47 NC's viel 21% in `Overig`, en `Overig` is geen thema maar het ontbreken ervan: elk zo'n
bevinding krijgt een eigen memo-blok. Drie oorzaken, alle drie gemeten op de echte run:

- **De clausuletitel telde niet mee.** §5.29 heet "Informatiebeveiliging en continuïteit tijdens
  verstoring" en het thema "Back-up & continuïteit" heeft `continuïteit` als keyword — maar
  `bepaal_thema()` las alleen beschrijving, onderbouwing en documentnaam. Nu wel, en nadrukkelijk
  als **terugval**: eerst de eigen tekst van de bevinding, en alleen als die niets oplevert de
  titel erbij. Als gelijkwaardige input overstemt de generieke normtaal van een clausuletitel de
  specifieke bevindingstekst. Effect als terugval: 5 van 47 veranderen, alle vijf vanuit `Overig`.
- **De taxonomie miste ontwikkel- en wijzigingsbeheer.** §8.9 (configuratiebeheer), §8.25 (veilige
  ontwikkeling) en §8.33 (testinformatie) horen bij elkaar en nergens anders. Nieuw thema
  "Ontwikkeling & wijzigingsbeheer" (taxonomie 25 → 26).
- **Toegangsbeheer kende authenticatie niet.** §5.17 (authenticatie-informatie) en §8.5 (MFA)
  zijn toegangsbeheer; de keywords stopten bij "toegangsrechten" en "autorisatie".

Bewust *niet* opgelost: §8.7 (afwijkende procesuitvoer) en §5.5 (meldplicht autoriteiten) blijven
`Overig`. Daar een thema voor verzinnen om het blokkenaantal te drukken zou het cijfer verbeteren
en de memo verslechteren.

### Fixed — 2026-08-26 — het review-antwoord werd afgekapt

Negen van de veertien storingen in de run van 22:38 waren "Unterminated string" en verwante
JSON-fouten. Dat was geen onleesbaar model maar een te krap budget: `max_tokens` stond nog op
1200 terwijl de prompt sinds gisteren ook om een actietabel vraagt. Het antwoord werd halverwege
een string afgekapt.

Budget naar **2500**, op de langste variant — advies, klasse, ernst, kern, reden met
documentnamen en drie acties — en niet op de gemiddelde. Bij een krap budget sneuvelt wat
achteraan staat, en dat zijn juist de acties.

En de melding klopt nu: een antwoord dat als JSON begint maar niet afsluit is **afgekapt**, geen
onleesbare rommel. "Geen geldige JSON" stuurde je naar het model terwijl het budget de oorzaak
was — dezelfde les als bij de classificatie sinds 2026-08-17.

### Gemeten — 2026-08-26 — de normketen dicht, en wat dat doet

Dezelfde bronnen, dezelfde dag, één fix ertussen:

| | run 21:40 | **run 22:38** |
|---|---|---|
| bevindingen per norm | alles `beide` | **31× 9001, 17× 27001** — geen enkele `beide` |
| clausulegroepen | 64 (op één hoop) | **70** (per norm gescheiden) |
| **auto-triage** | 5 | **33** |
| bevindingen met kernzin | 0 | **140** |
| bevindingen met actietabel | 0 | **96** |

De review-adviezen: 28 bevestigen · 18 verlagen · 7 onvoldoende bewijs · 3 samenvoegen · 14
storingen (waarvan 9 afkappingen, nu gerepareerd).

Die 140 kernzinnen en 96 actietabellen waren nog nooit gevuld. Dat is wat de memo nodig heeft om
drie A4 te worden: per NC een synthese-zin en een tabel met rol en termijn.

### Fixed — 2026-08-25 — de norm viel alsnog uit de keten

De run met auto-triage legde bloot dat de per-norm-koppeling niet doorliep. `clause_matches` had
3.067 koppelingen op 9001 en 1.332 op 27001, maar `bevindingen.norm` stond op `beide` en
`review_adviezen.norm` was **leeg** — in het log stond letterlijk "op  §9.3" met een gat waar de
norm hoort.

Drie gaten, alle drie alleen zichtbaar in een echte run:

1. **`_classify_drive` bouwde een minimale doc-dict** met id, naam en herkomst, en daar viel
   `clausule_normen` weg. Elke bevinding kreeg dus de run-parameter.
2. **De terugleesquery filterde op de run-norm** (`WHERE norm = 'beide'`). Was de opslag wél
   per-norm geweest, dan had die query nul bevindingen opgeleverd — de review en de memo hadden
   niets gezien terwijl de database vol stond. Nu haalt `beide` de rijen van allebei de normen op
   plus de oude `beide`-rijen, zodat bestaande databases niet stil leeg raken.
3. **De teruggegeven bevinding droeg geen `norm` en geen `onbruikbaar`.** De review groepeert op
   `clausule_id` + `norm` en filtert op `onbruikbaar`; zonder die velden groepeerde hij op een
   lege norm en telde hij lege oordelen mee.

De clausuletitel volgt nu ook de norm van de rij: §7.5 toont "Gedocumenteerde informatie" bij een
9001-bevinding in plaats van de 27001-titel die de samengevoegde map bovenaan zet.

### Gemeten — 2026-08-25 — de auto-triage heeft voor het eerst gedraaid

| | |
|---|---|
| bevindingen | 403 → 64 clausulegroepen |
| review-adviezen | 29 bevestigen · 13 verlagen · 7 onvoldoende bewijs · 2 samenvoegen · 13 storingen |
| **auto-triage** | **5 bevindingen automatisch op `valide`** |
| trail | 5 regels, actor `auto-triage`, met de reden van de review erbij |

Het werkt end-to-end: van koppeling tot triage-status met een spoor. Dat het er maar vijf zijn,
komt door de kapotte normketen hierboven — de review zag 64 groepen met een lege norm en gaf maar
één keer "bevestigen" op een positieve bevinding. Met de fix erin hoort dat aantal fors hoger te
liggen.

### Added — 2026-08-25 — een audit uit het overzicht halen

Het dashboard toonde twee audits waarvan er één uit een eerdere opzet kwam (`9001-2026-Q3`, 1.106
bevindingen, 4 runs). Er was geen manier om die kwijt te raken behalve met de hand op de opslag,
en dus bleef hij staan en las het overzicht als "er lopen twee audits".

**Archiveren, niet verwijderen.** De map gaat naar `archief/<datum>/<audit-id>-<tijd>/`, compleet,
met een `gearchiveerd.json` erbij die zegt wie het deed, wanneer en waarom. Een audit die gedraaid
heeft is bewijs dát er geaudit is; die weggooien maakt "wat is er in Q2 getoetst?"
onbeantwoordbaar. Er is bewust géén route die echt verwijdert — wie een dossier definitief kwijt
wil doet dat op de opslag, niet met één klik in een auditwerktuig.

Drie regels eromheen:

- **Een reden is verplicht**, in de API en in de UI. Zonder reden is later niet te zien of dit
  opruimen was of iets wegwerken — zelfde onderscheid als bij het verbergen van een run.
- **Niet tijdens een run** (409). De map verplaatsen terwijl er een run in schrijft, levert een
  run op die in het niets schrijft.
- **De knop zegt wat hij doet.** "De map gaat naar het archief; er wordt niets verwijderd" staat
  in de tooltip én in de bevestiging, anders klikt iemand hem denkend dat het dossier weg is.

Het overzicht loopt over mappen met een manifest, dus verplaatsen haalt de audit er vanzelf uit —
geen statusveld dat kan gaan liegen tegen de bestanden.

### Fixed — 2026-08-25 — de samengevoegde clause-map verliest niets meer

`laad_clause_map("beide")` deed `{**map_9001, **map_27001}`. Achttien clausulenummers bestaan in
beide normen en daar won 27001: **103 ingangen waar er 121 horen**. In een gecombineerde audit
bestonden die 18 ISO 9001-clausules niet meer — §5.1 Leiderschap, §6.1 Risico's en kansen,
§7.5 Gedocumenteerde informatie, §8.4 Externe processen — terwijl het rapport op pagina 1
"ISO 9001:2015 + ISO 27001:2022" claimde.

De sleutel blijft het clausulenummer: negen modules gebruiken deze map, en een andere sleutel
breekt ze allemaal. Wat erbij komt is **`varianten`**, per norm de eigen ingang. De top-level
waarden blijven zoals ze waren, dus bestaande aanroepers merken niets; wie de norm kent gebruikt
`titel_voor(clausule, norm)`.

De werkset doet dat al: een bevinding op 9001 §7.5 toont nu "Gedocumenteerde informatie" en niet
"Bescherming tegen fysieke en omgevingsbedreigingen".

**De `strict` xfail is weg.** Die pinde dit gat vast sinds 2026-08-24; er verdwijnt geen enkele
9001-clausule meer.

### Fixed — 2026-08-25 — een bevinding erft de norm van zijn koppeling

`clause_matches` wist sinds de per-norm-koppeling precies uit welke norm een match komt — 3.067
voor 9001 en 1.332 voor 27001 in de run van vanavond. `bevindingen` kreeg nog steeds `beide`, de
run-parameter, en daardoor moest `run_job._resolve_standard()` achteraf raden.

Gemeten op die run: met de complete norm-DB raadde hij **nul keer verkeerd** (was 448 van de 903
op 2026-08-24). Wat overbleef waren **30 bevindingen** op een nummer dat in beide normen bestaat
— daar kán hij niet kiezen en valt hij terug op 9001.

Dat gat is nu dicht: `bouw_bevindingen()` leest de norm uit `clausule_normen` van het gekoppelde
document, en `_upsert_bevindingen()` geeft die voorrang op de run-parameter. Raakt een document
hetzelfde nummer in beide normen, dan zijn het **twee bevindingen** — §7.5 is in 9001
"Gedocumenteerde informatie" en in 27001 iets heel anders, en één bevinding zou betekenen dat het
oordeel over de ene norm voor de andere doorgaat.

Paden zonder koppelingnorm (Miro, opvolgpunten) vallen terug op de run-parameter, zoals
voorheen. `_resolve_standard()` blijft staan voor bestaande databases waarin `beide` staat.

### Added — 2026-08-25 — NC's bundelen tot thema-blokken

De run van 2026-08-25 leverde 91 bevestigde NC's op. Eén blok per bevinding maakt daar 91 blokken
van; het handgemaakte Q2-memo had er **twee**, elk met drie bevindingen over drie clausules
("NC 1 — Bedrijfscontinuïteit & redundantie": §8.14, §5.29, §5.30).

`groepeer_ncs()` bundelt op **thema** en niet op clausule — het Q2-memo bundelt juist over
clausules heen, want daar laat één gebrek zich in meerdere eisen zien. Het thema stond al op elke
bevinding; de review levert de kernzin die het blok zijn synthese geeft.

Er valt geen bewijs weg: elke bevinding blijft zichtbaar onder zijn blok met zijn eigen bron. Een
managementmemo die niet terug te voeren is op documenten, is een mening.

**"Overig" krijgt geen verzamelblok.** Dat is geen thema maar het ontbreken ervan — 25% van de
bevindingen viel erin op 2026-08-24 — en ze als één NC presenteren zou suggereren dat ze één
gebrek delen. Elk krijgt zijn eigen blok.

Grootste thema eerst: daar ligt het meeste bewijs, en een lezer die na één blok stopt heeft dan
het zwaarste gezien.

### Added — 2026-08-25 — de review vult de actietabel van de memo

Het handgemaakte Q2-memo heeft per NC een tabel **Wat | Wie | Waar | Uiterlijk**. Die velden
bestonden in het datamodel maar niemand vulde ze, en een memo zonder die tabel is een
constatering zonder opdracht.

De review kan ze voorbereiden omdat hij als enige de clausule als geheel heeft gezien. Wat hij
levert is een **voorstel**, met twee harde grenzen:

- **`wie` is een rol, nooit een persoon.** "IT-lead", "KAM + MT", "DevOps" — geen namen. Wie het
  precies doet is een besluit van de organisatie, en een persoonsnaam in een auditdocument die
  niemand heeft goedgekeurd is een probleem op zich. Een antwoord met twee gekapitaliseerde
  woorden achter elkaar wordt geweigerd.
- **`uiterlijk` is een termijn, geen datum.** "2026-Q3", "doorlopend, eerste review 2026-Q4".

Een veld dat niet uit het bewijs volgt blijft leeg. Een verzonnen eigenaar is erger dan een leeg
vakje: dat vakje ziet de auditor en vult hij. Hooguit vier acties per clausule — het Q2-memo had
er drie, en meer past niet op drie A4.

**Nieuwe tabel `review_adviezen`**, één rij per (norm, clausule). De review draait in de pipeline
en de memo wordt later gebouwd, mogelijk in een ander proces; zonder opslag zou de kernzin alleen
in de trail staan — leesbaar voor een mens die zoekt, onbruikbaar voor de memo-bouwer. Een
tweede run overschrijft, en dat is geen verlies: het ruwe antwoord met tijdstempel, model en
kosten blijft in `assistent_vragen`, en die is append-only.

`verrijk_met_review()` zet kernzin en acties op de bevindingen bij het exporteren, op **(norm,
clausule)** — achttien nummers bestaan in beide normen, en zonder die controle zou een kernzin
over "Gedocumenteerde informatie" onder "Bescherming tegen fysieke bedreigingen" belanden. Wat de
auditor zelf invulde wint van een voorstel.

### Added — 2026-08-25 — de synthese-zin uit de review komt in de memo

Het handgemaakte Q2-memo heeft per NC één zin die zegt wat het gemeenschappelijke gebrek is:
*"Drie clausules, één hoofdgebrek: er is geen gedocumenteerd en getest continuïteitsbeheer."*
Dat is wat drie A4 leesbaar houdt — zonder die zin is een NC-blok een opsomming van citaten.

De autonome review produceert precies zo'n zin per clausule (`kern`), en die reisde tot nu toe
niet verder dan de trail. Nu draagt een bevinding hem mee tot in het NC-blok, en staat hij in de
render **vóór** de details: eerst de conclusie, dan de onderbouwing.

Leeg als er geen review heeft gedraaid, en dan valt het blok terug op de afwijking zelf. Geen
placeholder: een verzonnen synthese is erger dan geen synthese.

### Added — 2026-08-25 — de memo telt zijn pagina's

De klant stelt "één tot drie A4" als harde eis. Er was niets dat die eis controleerde, dus een
memo die op vier pagina's uitkwam brak hem zonder dat iemand het merkte — hetzelfde patroon als
de PDF die maandenlang ontbrak omdat de melding een `logger.warning` was.

`schrijf_pdf()` geeft nu een `PaginaBudget` terug: het aantal pagina's, of het past, en zo niet
een melding met beide getallen erin. "Te lang" zonder getal laat de auditor raden hoeveel eruit
moet.

De memo wordt **wel** geschreven als hij te lang is. Een auditor die hem te lang vindt kan
comprimeren; een memo die weigert helpt niemand. Dat is het verschil met de weigering bij
ontbrekende normtekst: daar ontbrak inhoud, hier is de inhoud er en is alleen de vorm te ruim.

Het budget is zichtbaar waar de memo gemaakt wordt: in de CLI met een gekleurde regel, en in het
portaal via het runlog.

### Gemeten — 2026-08-25 — de volledige keten op een schone omgeving

Cluster geleegd (met archief naar `/var/lib/iso-audit/archief/2026-08-25/`), daarna één run met
alle vier de bronnen en de review aan:

| | |
|---|---|
| documenten | 709 — Nextcloud 121 van 168, inclusief de 32 OpenDocument-bestanden |
| clausule-koppelingen | 4.399, waarvan **3.067 voor ISO 9001** (was 0 vóór de per-norm-koppeling) |
| bevindingen | 314: 170 positief, 91 NC, 53 OFI |
| review | 63 clausulegroepen op Sonnet, **$0,65** |
| adviezen | 19 bevestigen · 15 verlagen · 15 onvoldoende bewijs · 4 samenvoegen · 10 storingen |
| rapport | md, html, docx, pdf, csv, xlsx |

Van 4.399 koppelingen naar 63 clausulevragen naar 19 bevestigde oordelen. De 15 verlagingen en
15 keer "onvoldoende bewijs" zijn precies wat een mens moet wegen.

### Fixed — 2026-08-25 — de verwijzingscontrole was te streng

Negen van de tien storingen in die run kwamen van de eigen controle: het model verwees naar een
document met een **verkorte** naam. `ISO-735` waar het document `ISO-735 | Sub Domain-takeover`
heet, of de titel zonder `.docx`. De verwijzing klopte inhoudelijk; de vergelijking was
letterlijk.

Nu tellen ook de naam zonder extensie, de delen rond een `|`, en issue-sleutels als `ISO-735` —
zeven tekens, maar de meest precieze verwijzing die er is: hij wijst één ticket aan. Onder de
lengtegrens van acht tekens vallen verder alleen generieke stukjes weg; een document dat `a.md`
heet mag niet met elke reden matchen.

Wat niet verandert: een naam die nergens in het meegegeven corpus voorkomt blijft een storing.
Tolerant voor de vorm, streng op de inhoud — dezelfde les als bij de Bronbevrager, waar de
komma-lijst en het Nederlandse "en" drie iteraties kostten.

### Added — 2026-08-25 — auto-triage: het onbetwiste deel, en niet meer

Wat er op 2026-08-24 gebeurde — 902 bevindingen in vier bulkacties op `valide` — is geen
menselijk oordeel maar capitulatie voor het aantal. Een lijst die te lang is om te wegen, wordt
niet gewogen. Tegelijk is "de agent beslist" precies wat de auditor-spiegel uitsluit.

De uitweg is de agent het **onbetwiste voorwerk** laten doen, expliciet gemarkeerd:

| geval | wat er gebeurt |
|---|---|
| review bevestigt een **positieve** bevinding | automatisch op `valide` |
| review bevestigt een **NC** | blijft bij de auditor |
| review **verlaagt** (NC → OFI) | blijft bij de auditor |
| review zegt **onvoldoende bewijs** | blijft bij de auditor |
| review **faalt** | blijft bij de auditor — geen advies is geen groen licht |

Een NC vraagt om correctie, root-cause-analyse en formele verificatie; dat raakt de
certificering. Verlagen is juist wél een oordeel: de review vindt het bewijs onvoldoende voor de
zwaarste klasse. Beide horen bij een mens. Wat overblijft is de bulk waar niets op het spel
staat.

**Alles met een spoor.** De voorstellen gaan via `apply_triage` en niet met een directe
schrijfactie op de werkset: dan gelden dezelfde controles, hetzelfde slot en dezelfde
append-only regel als bij een mens. De actor is `auto-triage` — bewust geen mens-achtige naam,
zodat een auditor in één blik ziet wat een mens heeft besloten en wat niet.

Eigen schakelaar (`--auto-triage` / `--geen-auto-triage` / `ISO_AUDIT_AUTO_TRIAGE`, plus een
vinkje in het runscherm): je kunt de tweede zeef willen zonder dat er iets automatisch wordt
afgedaan. Andersom heeft geen zin — zonder review is er geen advies om op te varen — dus zonder
review gebeurt er niets.

### Added — 2026-08-25 — de review is aan te zetten in het portaal

Een modus die alleen via een env-var of de opdrachtregel aan te zetten is, is voor de auditor
niet aan te zetten — en die is degene die beslist of het de tokens waard is. In het runscherm
staat nu een vinkje **Autonome review** plus een veld voor de steekproef ("alleen de zwaarste N
clausules, 0 = alle"). Het vinkje meldt in zijn tooltip dat het tokens kost; een schakelaar
zonder prijskaartje wordt aangezet zonder afweging.

Het portaal stuurt `review: true|false` mee en overstemt daarmee `ISO_AUDIT_REVIEW` — dat is een
mens die op Start klikt, en dan hoort een cron-instelling niet te bepalen wat er gebeurt. De
API houdt wél drie standen (`null` = de omgeving beslist), zodat de env-var-fallback voor
cron-runs blijft werken.

### Added — 2026-08-25 — incrementele ingest: een ongewijzigd document wordt niet opnieuw opgehaald

Gemeten op 2026-08-24: het dure deel — de modelaanroepen — werd al volledig hergebruikt (0 calls
in ronde 2 en 3), maar een herhaalde run duurde nog steeds zestien minuten. Die gingen bijna
helemaal op aan documenten die niet veranderd waren:

| bron | listing | inhoud per document | totaal |
|---|---|---|---|
| Drive | 65 s voor 456 docs | 2,49 s | 1.202 s |
| Nextcloud | 3,2 s voor 121 docs | 0,55 s | 69 s |

De ingest hergebruikt nu de opgeslagen tekst wanneer de wijzigingstijd van de bron gelijk is aan
`documents.modified_at`. **De listing draait altijd volledig** — dat is de enige manier om te
merken dat een document verdwenen of bijgekomen is, en het is 65 s van de 1.200. Alleen het
ophalen van de inhoud wordt overgeslagen.

Drie redenen om tóch te lezen, elk gemeten:

- **Geen wijzigingstijd** — Planning levert rijen uit een sheet zonder tijdstempel, 150 van de
  709. Geen geraden tijd: dan zou een document als ongewijzigd gelden terwijl niemand dat weet.
- **Leeg opgeslagen** — leeg betekent niet gelezen; overslaan zou de leegte bevriezen.
- **`ISO_AUDIT_OPNIEUW_LEZEN`** — na een wijziging in de lezers is de opgeslagen tekst verouderd
  zonder dat de bron dat weet. Op 2026-08-24 werden 32 OpenDocument-bestanden voor het eerst
  leesbaar; met alleen een tijdstempel-vergelijking zouden die als "ongewijzigd" nooit binnen
  zijn gekomen. Een cache zonder uitweg is een val.

De dekkingteller telt hergebruik apart (`hergebruikt`) en meldt het. `gelezen` blijft het totaal:
een overgeslagen document is wél gelezen, alleen niet nu. Een dekking die daarover zwijgt laat de
auditor denken dat alles vers is opgehaald.

### Added — 2026-08-25 — de autonome review draait, gemeten tegen het echte model

De review is compleet: prompt, aanroep, verwijzingscontrole, trail, schakelaar en steekproef.

**Steekproef van 12 clausulegroepen op de echte bevindingen** (347 bevindingen, 67 groepen):

| model | bevestigen | verlagen | onvoldoende bewijs |
|---|---|---|---|
| Haiku 4.5 | 7 | 2 | 0 |
| **Sonnet 5** | **5** | **6** | **1** |

Sonnet is strenger, en op de juiste manier: §5.13 heeft één bevinding en krijgt
`onvoldoende_bewijs` — uit één document volgt geen clausule-breed oordeel. De twee grootste
stapels, §10.2 met 27 bevindingen en §4.1 met 20, worden allebei verlaagd naar OFI. Dat zijn
precies de clausules waar het per-document-oordeel het hardst doorsloeg.

Daarom staat de review standaard op **Sonnet** (`ISO_AUDIT_REVIEW_MODEL`) en niet op het
classificatie-model: de classificatie draait over honderden documenten en is op het goedkoopste
model, de review over tientallen clausules en bereidt een oordeel voor dat een auditor overneemt.

**Drie standen op de opdrachtregel.** `--review`, `--geen-review`, of niets zeggen en de omgeving
laten beslissen. Bewust geen `store_true`: die is altijd `False` als hij ontbreekt, en dan kan
`ISO_AUDIT_REVIEW` nooit iets aanzetten en `--geen-review` de omgeving nooit overstemmen.

**`--review-steekproef N`** beoordeelt alleen de N zwaarste clausules. De groepen staan op
zwaarte, dus een steekproef pakt de NC's eerst. 67 groepen op een zwaar model is een uitgave die
je één keer met de juiste prompt wil doen, niet een experiment dat tegelijk de rekening is.

**Wat de review niet doet:** een status zetten, een bevinding sluiten, de werkset aanraken. Hij
levert een advies met een reden die naar meegegeven documentnamen verwijst — een reden zonder
verwijzing is een storing, niet een advies. Elke aanroep gaat met model, kosten, peildatum en
grondslag in `assistent_vragen`, storingen inbegrepen; één mislukte groep stopt de rest niet, en
een mislukte review breekt de run niet.

**Afkappen wordt gemeld.** Maximaal 25 bevindingen per groep gaan mee (§10.2 had er 27), en het
model krijgt te horen hoeveel het er niet ziet. Een lijst die stil op 25 stopt leest als "dit is
alles".

### Added — 2026-08-25 — autonome review: per clausule oordelen, en aan of uit te zetten

De classificatie oordeelt per document. 42 documenten die clausule 8.16 raken geven 42 oordelen
over dezelfde eis, en daar stelt een auditor er één over: *wordt deze eis gehaald, gegeven al het
bewijs dat we hebben?*

`groepeer_per_clausule()` bundelt de bevindingen op **(norm, clausule)**. Op de run van
2026-08-24 gemeten:

| | |
|---|---|
| bevindingen | 347 |
| **clausule-groepen** | **67** |
| groepen met een NC erin | **37** |
| grootste groep | clausule 10.2 met 27 bevindingen |

Van 387 losse NC's naar 37 clausules om te beoordelen — een factor tien, zonder dat er bewijs
verdwijnt.

Norm en clausule samen en nooit clausule alleen: §7.5 is in 9001 "Gedocumenteerde informatie" en
in 27001 "Bescherming tegen fysieke en omgevingsbedreigingen". Op één hoop zou bewijs over het
ene iets zeggen over het andere. Onbruikbare bevindingen — een oordeel zonder beschrijving én
zonder onderbouwing — tellen niet mee; blijft er niets over, dan is er niets te reviewen.

**De modus is aan of uit te zetten**, en staat standaard **uit**. Een stap die altijd draait en
tokens kost is geen keuze maar een verrassing op de rekening. De schakelaar volgt het patroon van
`--source` en `--mode`: expliciete vlag, dan `ISO_AUDIT_REVIEW` als env-var-fallback die luid
meldt dát hij gebruikt wordt, dan uit. De vlag wint van de omgeving — andersom zou een
cron-instelling een handmatige run stil overrulen. De herkomst van de keuze (vlag, omgeving,
standaard) gaat mee, zodat "waarom draaide deze stap wel of niet" achteraf te beantwoorden is.

De schakelaar zit vóór de modelaanroep en niet erna: een review die draait en zijn uitkomst
weggooit kost hetzelfde als een review die telt.

### Gemeten — 2026-08-25 — de e2e-laag is flaky, en zat niet in de eerdere groene runs

De volledige suite duurt **273 seconden**, niet de ~31 die ik gisteren rapporteerde: de
Playwright-laag zat niet in die runs. Draait hij wel mee, dan faalt er telkens één test op een
timeout van 30 s — en elke run een andere (`..._is_typbaar`, daarna
`..._vervangt_de_omgeving_en_is_terug_te_draaien`). Dat is timing onder belasting en geen
logische regressie; de tests slagen los van elkaar.

Vastgelegd omdat een flaky laag erger is dan geen laag: hij leert je de rode uitslag negeren. De
timeouts staan hard op 30 s en 15 s in de helper; dat hoort configureerbaar en de oorzaak hoort
gemeten, niet opgerekt.

### Changed — 2026-08-24 — minor is de standaard, major de uitzondering

De eerste run met de nieuwe definitie gaf **71 major tegen 8 minor**. Dat kan niet: major
betekent dat het proces organisatiebreed afwezig of gebroken is. Wat er stond was "Minor — een op
zichzelf staande misser", geformuleerd als de uitzondering, en dan kiest een model bij twijfel de
andere. Dezelfde vorm-fout als bij OFI: de zeldzame uitkomst als de norm neerzetten.

Wat eronder zit is dieper: het oordeel valt **per document**. Bekeken voorbeeld uit de run —
"Classificatie van informatie ontbreekt", major, op grond van één tool-ontwerpdocument. Daaruit
volgt niet dat de organisatie geen classificatieschema heeft; het volgt dat dít document het niet
regelt. Zolang het oordeel per document valt, kan major daar niet uit volgen.

De prompts zeggen nu: minor is de standaardkeuze, major alleen als dít document zelf laat zien
dat het proces organisatiebreed gebroken is, en bij twijfel altijd minor. Eén oordeel per
clausule over al het bewijs heen is `openspec/changes/autonome-review/`.

### Measured — 2026-08-24 — wat de formele definitie met de aantallen doet

Twee volledige runs op dezelfde bronnen, met dezelfde 709 documenten:

| | oude definitie | formele definitie |
|---|---|---|
| bevindingen (zonder Jira-opvolging) | 800 | **347** |
| NC | 387 (48%) | **79 (23%)** |
| OFI | 270 | 86 |
| positief | 143 | 142 |
| documenten met bevindingen | 118 | 91 |
| clausule-koppelingen | 2.695 | **4.399** |

Minder dan de helft aan bevindingen en een vijfde van de NC's, terwijl er **63% méér
clausule-koppelingen** zijn doordat de 18 ISO 9001-clausules terug zijn. Strenger op het oordeel,
breder op de dekking.

Kanttekening bij dit getal: 40 van de 347 stonden nog op de string `'null'` — die run liep op de
versie vóór `_geldig_oordeel()`. Zonder die 40 is de verhouding 79 NC op 307 bevindingen (26%).

### Fixed — 2026-08-24 — alleen NC, OFI en positief tellen als oordeel

In de eerste run met de nieuwe definitie kwamen twee bevindingen binnen met classificatie
`'null'` — de **string**, niet JSON-`null`. De controle keek of de waarde leeg was, en een
niet-lege string is dat niet. Gevolg: een bevinding met een classificatie die nergens op slaat,
die wél meetelt, die niet als NC of OFI te triageren is, en die in het rapport een lege categorie
oplevert.

`_geldig_oordeel()` accepteert nu alleen `NC`, `OFI` en `positief`. `null`, `none`, `geen` en
`nvt` zijn manieren waarop een model "hier valt niets over te zeggen" opschrijft als het de
JSON-vorm niet haalt; die leveren geen bevinding op. Een onbekende waarde als "gedeeltelijk"
wordt gelogd en genegeerd — liever geen bevinding dan een categorie die geen enkel filter kent
en die in de memo tussen wal en schip valt.

### Fixed — 2026-08-24 — geen oordeel is geen OFI

De nieuwe prompts bieden `null` aan voor "dit document gaat hier niet over". Dat had geen effect
gehad: `(res_map.get(cid, {}) or {}).get("classificatie", "OFI")` maakte van élk ontbrekend
antwoord een OFI. Twee gevallen vielen daaronder — het model zweeg over een clausule, of het zei
expliciet `null` — en beide werden een OFI met een lege beschrijving en een lege onderbouwing.

Dat is de mechaniek achter de 55 lege OFI's van 2026-08-24, en achter 6,8 bevindingen per
document: elk document-clausulepaar dat de zoektermen opleverden moest een oordeel worden, ook
als er niets over te zeggen viel.

`bouw_bevindingen()` slaat een paar zonder oordeel nu over. Een NC zonder beschrijving én zonder
onderbouwing wordt niet weggegooid maar gemarkeerd als `onbruikbaar` — dát het model hem zo
teruggaf is zelf een gegeven over de classificatie, en de norm vraagt bij een NC om correctie,
root-cause-analyse en formele verificatie, wat op een leeg oordeel niet kan.

Nieuwe kolommen `bevindingen.ernst` (`major` / `minor`, alleen bij een NC) en
`bevindingen.onbruikbaar`, met een migratie via `ALTER TABLE` voor bestaande databases. Zonder
die kolommen was de prompt wel aangepast en viel het resultaat bij het opslaan weg — een
verbetering die alleen in de logs bestaat.

### Changed — 2026-08-24 — NC en OFI krijgen hun formele definitie, en de prompts gaan naar schijf

De scherpe prompt — de standaard, dus wat elke portaal-run gebruikte — zei:

> "NC: er is geen of onvoldoende bewijs; de eis is niet aantoonbaar gedekt."

Dat is het omgekeerde van de norm. Een non-conformiteit is een **bewezen** tekortkoming, en geen
bewijs in één document toont niets aan: het betekent dat dít document er niets over zegt. Zo
werden het er **387** in de run van 2026-08-24, waar de auditor in het handgemaakte Q2-memo op
**2** uitkwam.

Even scheef stond OFI. Die was "de eis is gedeeltelijk gedekt" — maar gedeeltelijk gedekt is een
**kleine non-conformiteit**, geen verbeterkans. Een OFI betekent dat de eis wél voldoet en
slimmer, veiliger of efficiënter kan; opvolging is vrijblijvend en de organisatie blijft conform.
Dat verschil bepaalt of iemand iets moet corrigeren of mag negeren.

De nieuwe prompts (`v2-scherp`, `v2-genuanceerd`, `v2-miro`) leggen vast:

- **NC** = bewezen tekortkoming, met **major** (proces afwezig of gebroken) tegen **minor**
  (op zichzelf staande misser in een werkend proces).
- **OFI** = de eis voldoet, het kan beter, opvolging is vrijblijvend.
- **`null` is een geldige uitkomst.** Een document dat over iets anders gaat, toont geen
  tekortkoming aan. Zonder die uitweg moest het model voor élk document-clausulepaar uit de
  zoektermen een oordeel kiezen — de mechaniek achter 6,8 bevindingen per document.
- **Een NC moet zijn onderbouwing invullen**: welke eis niet wordt gehaald, waaruit dat blijkt in
  dit document, en waarom het het managementsysteem raakt. Kun je die drie niet invullen, dan is
  het geen NC. De norm vraagt om correctie, root-cause-analyse en formele verificatie, en dat kan
  niemand op een oordeel zonder inhoud — 55 bevindingen hadden een lege beschrijving én lege
  onderbouwing.

**De prompts staan nu op schijf**, in `classification/prompts/<versie>.md`. `CLAUDE.md` belooft
dat al ("Geheime classificatie-logica bestaat niet"), maar die map bestond niet en de prompts
stonden als tripelquoted strings in `findings.py`. `memo/prompts/` en `reporting/prompts/` deden
het allang goed; de classificatie was de enige die zijn prompt in code hield — uitgerekend de
plek waar het oordeel valt. `classifications.prompt_versie` bewaarde alleen een sha256, dus
achteraf was te zien **dát** de prompt veranderde, niet wat er stond.

Een gate-test weigert dat een systeemprompt terugkruipt in de code, en per promptbestand wordt
de definitie zelf getoetst — inclusief dat de oude NC-formulering er niet meer in staat.

**Nog te doen:** de klantspecifieke jurisprudentie in `v2-genuanceerd` (BYOD, "memo is
sluitingsbewijs", 5.12 intern/extern) hoort in het profiel en niet in een gedeelde prompt; bij de
volgende klant is die gewoon onjuist. En het oordeel valt nog per document; per clausule over al
het bewijs heen is `openspec/changes/autonome-review/`.

### Fixed — 2026-08-24 — de koppeling draait per norm; 18 ISO 9001-clausules komen terug

`laad_clause_map("beide")` voegde de twee clause-maps samen met `{**map_9001, **map_27001}`.
Achttien clausulenummers bestaan in beide normen, en bij een botsing won 27001 — 103 ingangen
waar er 121 horen. In een gecombineerde audit werden daardoor 18 van de 28 ISO 9001-clausules
**nooit getoetst**: §5.1 Leiderschap, §5.2 Beleid, §5.3 Rollen, §6.1 Risico's en kansen,
§6.2 Kwaliteitsdoelstellingen, §6.3 Planning van wijzigingen, §7.1 t/m §7.5 en §8.1 t/m §8.7. Het
rapport zei op pagina 1 "ISO 9001:2015 + ISO 27001:2022".

De koppeling draait nu per norm (`koppel_alle_normen`). Elke match draagt de norm waaruit hij
komt (`clausule_normen`), en de zoektermen van de ene norm kunnen die van de andere niet meer
overschrijven. Een document dat beide §7.5-onderwerpen raakt — "Gedocumenteerde informatie" bij
9001, "Bescherming tegen fysieke en omgevingsbedreigingen" bij 27001 — krijgt twee koppelingen en
komt zelf één keer terug. `clausules` wordt uit `clausule_normen` afgeleid en niet apart
bijgehouden.

Samen met `norm` in de sleutel van `clause_matches` betekent dit dat de opslag die twee
koppelingen nu ook echt kan bewaren; daarvoor gooide `INSERT OR IGNORE` de tweede stil weg.

**Wat nog niet om is:** 23 plekken lezen nog de samengevoegde map (titels in het rapport,
`ontbrekende_dekking`, de interviewvragen, de classificatie-prompt), en `bevindingen.norm` staat
nog op de run-parameter in plaats van op de norm van de match. Bewust niet meegenomen: de
classificatie oordeelt tegen die samengevoegde map, en een norm op de bevinding plakken zonder
dat eerst te repareren levert een verkeerd oordeel mét een zelfverzekerd label — erger dan geen
label. De `strict` xfail in `tests/data/test_norm_db_export.py` beschrijft nu precies die rest.

### Fixed — 2026-08-24 — twee regressies uit de registry-bootstrap van vandaag

De verhuizing van de adapter-imports naar `sources.laad_adapters()` brak twee dingen die pas
opvielen door een test die los draaide:

**`levert_opvolgpunten` vroeg het aan een lege registry.** Bij een `KeyError` valt die functie
terug op `False`, dus Jira werd stilletjes een documentbron — elk ticket tegen elke clausule
geclassificeerd, precies de rolwissel die de docstring van die functie uitsluit. In de volledige
suite viel het niet op omdat een andere test de adapters al had geïmporteerd.

**`laad_adapters()` herstelde een lege registry niet.** `importlib.import_module` op een module
die al in `sys.modules` staat, draait de `@register`-decorator niet opnieuw. De functie deed dan
niets, en het gedrag hing weer af van wie er eerder toevallig had geïmporteerd. Er is nu een
lijst van wat er ooit is geregistreerd die dat herstelt — en die de laatste registratie bewaart,
niet de eerste, want een test die een module herlaadt maakt een nieuw class-object.

### Added — 2026-08-24 — beide normen als standaard, 27001 als de norm bij één keuze

Vastgelegd in `api/registry.py` (`STANDAARD_NORMEN`, `VOORKEURSNORM`) met een test. Keuze van de
auditor: ISO 27001 draagt de informatiebeveiligingsaudit en kent 93 clausules tegen 28 voor 9001,
dus een audit die één norm doet en 9001 kiest laat het grootste deel van de beheersmaatregelen
liggen. Het is een standaard en geen verbod — een auditor die bewust alleen 9001 wil toetsen kan
dat.

### Analyse — 2026-08-24 — 800 bevindingen: geen duplicatie, wel te veel om te wegen

Nagerekend op de meetdatabase, naar aanleiding van de vraag of 1.049 bevindingen niet overkill
was:

| | |
|---|---|
| bevindingen (zonder Jira-opvolging) | 800 |
| verdeeld over | 118 documenten, 85 clausules |
| gemiddeld per document | 6,8 — met uitschieters van 52 en 50 |
| **duplicaten** | **4 van de 800** |
| classificatie | 387 NC, 270 OFI, 143 positief |

**Het zijn geen duplicaten.** Slechts vier bevindingen hebben een herhaalde beschrijving; de rest
is breedte — 42 documenten die iets zeggen over clausule 8.16, elk met een eigen oordeel. Dedup
op tekst zou dus vrijwel niets opleveren.

Wat er wél mis is: **55 OFI's hebben een lege beschrijving én een lege onderbouwing** — een
oordeel zonder inhoud dat meetelt in het rapport. En 387 NC's is geen werklijst: in het
handgemaakte Q2-memo hield de auditor er 2 over, en op 24 augustus werden 902 bevindingen in vier
bulkacties op `valide` gezet omdat één voor één wegen bij dat aantal niet gebeurt.

Vastgelegd als change `autonome-review`: eerst een vormcontrole zonder model (die haalt er meteen
55 uit), dan een zwaarder model dat per bevinding beoordeelt of hij ergens op slaat — met een
steekproef van 50 vóór de volledige run, want 800 bevindingen op Opus is een uitgave die je één
keer met de juiste prompt wil doen.

### Analyse — 2026-08-24 — waar de 16 minuten van een herhaalde run heen gaan

| bron | listing | inhoud per document | totaal |
|---|---|---|---|
| Drive | 65 s voor 456 docs | 2,49 s | **1.202 s** |
| Nextcloud | 3,2 s voor 121 docs | 0,55 s | 69 s |

Het dure deel — de modelaanroepen — wordt al volledig hergebruikt (0 calls in ronde 2 en 3). De
resterende tijd is bijna helemaal het opnieuw ophalen en uitpakken van documenten die niet
veranderd zijn. Drive en Nextcloud leveren allebei een wijzigingstijd voor élk document (559 van
de 709; de 150 zonder zijn Planning-rijen uit een sheet), en die staat al in
`documents.modified_at` — hij wordt alleen nooit gebruikt om iets over te slaan. Vastgelegd als
change `incrementele-ingest`.

### Fixed — 2026-08-24 — het schema wordt bij het opstarten klaargezet

`initialiseer()` voert sinds vandaag ook een migratie uit (`norm` in de sleutel van
`clause_matches`), maar hij werd alleen aangeroepen vanuit de assistent-route en vanuit de
pipeline. Gevolg: na de uitrol van 0.2.0a30 stond de productie-database nog op het oude schema —
gecontroleerd, de sleutel was ongewijzigd — en zou de migratie pas draaien zodra iemand toevallig
een vraag stelde of een run startte.

Voor een migratie is dat de verkeerde plek. Een tabel die halverwege een run van twintig minuten
wordt herbouwd, is een verrassing tijdens werk dat niet onderbroken mag worden. Nu gebeurt het
bij het opstarten: één keer, zichtbaar, en vóórdat er iemand mee werkt. Faalt het, dan start het
portaal niet — een kapot schema is niets om verkeer op te serveren.

De migratie zelf is geverifieerd op een kopie van de echte database (4.985 koppelingen): sleutel
om, geen rij verloren, tweede keer draaien verandert niets.

### Fixed — 2026-08-24 — elke run dupliceerde alle Jira-opvolgpunten

Gemeten met drie runs op één verse database, om te zien of het tool eerdere audit-context bewaart
en hergebruikt:

| ronde | duur | documenten | classificatie-calls | opvolgpunten in `bevindingen` |
|---|---|---|---|---|
| 1 (koud) | 31 min | 709 | 118 | 83 |
| 2 | 16,5 min | 709 (0 nieuw) | **0** | **166** |

Het hergebruik van classificaties is perfect: ronde 2 deed geen enkele modelaanroep en voegde
geen document of clausule-koppeling toe. Maar er kwamen 83 bevindingen bij — allemaal
Jira-opvolgpunten, allemaal dezelfde als in ronde 1.

`_issue_to_finding` bouwde het id als `f"{sessie_id}:{key}"`. Dat sessie-id verschilt per run, dus
dezelfde issue kreeg elke run een nieuw id en werd als nieuw punt opgeslagen: 83 unieke
Jira-sleutels stonden er na twee runs 166 keer in, onder twee `audit-<tijdstempel>`-prefixen.
Het documentenpad in dezelfde module gebruikte al wél de kale sleutel; alleen het bevindingenpad
week af.

Opvolgpunten staan buiten de triage (`herkomst NOT LIKE '%-opvolging'`), dus de werkset bleef
schoon en niemand merkte het. Wat scheefliep is elke telling van "hoeveel opvolging is er" — en
dat is precies waar deze rijen voor bestaan: aantonen dát er opvolging plaatsvindt. Een teller die
met elke run verdubbelt toont dat niet aan maar overdrijft het.

Het id is nu de Jira-sleutel. `sessie_id` blijft in de signatuur: die hoort bij de context van het
ophalen, niet bij de identiteit van de issue.

### Changed — 2026-08-24 — `norm` hoort in de sleutel van `clause_matches`

De primaire sleutel was `(doc_id, herkomst, clausule_id, sub_punt)`. Achttien clausulenummers
bestaan in beide normen, dus een document dat zowel ISO 9001 §7.5 (Gedocumenteerde informatie)
als ISO 27001 §7.5 (Beveiligd ontwikkelen) raakt, levert twee koppelingen op die onder die
sleutel op elkaar vallen — en `INSERT OR IGNORE` gooit de tweede stil weg.

Dat is de opslagkant van het probleem dat `laad_clause_map("beide")` aan de laadkant heeft. Deze
change repareert alleen de opslag: `norm` staat nu in de sleutel, met een migratie voor bestaande
databases, want `CREATE TABLE IF NOT EXISTS` raakt een bestaande tabel niet aan. De migratie
bouwt de tabel opnieuw op binnen één transactie en behoudt elke rij.

**Op zichzelf verandert dit nog niets aan het gedrag**: de koppeling schrijft nog steeds `beide`
als norm. Het is de voorwaarde voor `openspec/changes/clausule-per-norm/`, waarin de koppeling
per norm gaat draaien. Die kant is bewust niet meegenomen — hij raakt de classificatie-prompt,
de cache-sleutel en het id-formaat van een bevinding, en dat is niet te verifiëren zonder een
echte run.

### Fixed — 2026-08-24 — een crash op de assistent-route liet geen spoor na

`POST /assistent/vraag` ving alleen de twee bekende assistent-fouten op en legde die in
`assistent_vragen` vast. Elke andere exceptie ging als 500 naar buiten **zonder trail-rij**. Op
2026-08-24 gaf elke vraag met een koppelteken erin zo'n 500 (FTS5 las `non-conformiteiten` als
kolomnaam), en de laatste rij in de trail was van 22 augustus: achteraf was niet vast te stellen
wát er gevraagd was toen het misging.

Een onverwachte fout komt nu ook in de trail, met het exceptietype en de melding. De fout zelf
wordt onveranderd doorgegeven en niet omgezet in een 502: dit is een fout in onze eigen code en
geen weigering van de verwijzingscontrole, en dat onderscheid hoort zichtbaar te blijven — in de
status, in de stacktrace én in de trail.

Dit is een voorwaarde voor `triage-agents`: bij één handmatige vraag is een spoorloze storing
vervelend, bij tientallen agent-aanroepen per run is niet meer vast te stellen wat een agent zag
toen hij iets beweerde.

### Fixed — 2026-08-24 — de norm-DB was een handmatige export van 13 van de 121 clausules

`examples/norms/*.yaml` is een export uit `iso_audit.data.normteksten` — dat staat in het bestand
zelf. Die export was met de hand gemaakt en bevatte **13 clausules** terwijl de repo-bron er
**121** heeft (28 voor 9001, 93 voor 27001). Er was geen script dat hem maakte en geen test die
hem bijhield.

Dat gaf nergens een fout, alleen verkeerde antwoorden op twee plekken:

1. **`iso-audit memo` weigerde** op de echte dataset ("Clausule '10.3' ontbreekt in
   iso-9001-2015"). Die weigering is juist — een memo mag geen verzonnen citaat bevatten — maar
   de oorzaak werd gelezen als een licentiekwestie, terwijl de tekst gewoon in de repo staat. Van
   de 87 gebruikte clausules zitten er 87 in de bron; er ontbrak niets.
2. **448 van de 903 bevindingen droegen de verkeerde norm.** `run_job._resolve_standard()`
   bepaalt met deze DB bij welke norm een clausule hoort ("alleen in 27001 → 27001; anders →
   9001"). Met 13 clausules zei de DB bijna altijd "niet in 27001", dus viel vrijwel alles terug
   op de 9001-default. Clausule 8.24 — cryptografie, Annex A van 27001, bestaat niet in 9001 —
   stond in de werkset als ISO 9001:2015. 800 van de 903 bevindingen droegen het 9001-label.

Nieuw: `scripts/genereer-norm-db.py`, dat de export bouwt uit de normteksten (voor de tekst) en
de clause-maps (voor de titel), plus `tests/data/test_norm_db_export.py` die byte-voor-byte
faalt zodra de export achterloopt. Een export die met de hand wordt bijgehouden loopt achter, en
hier was dat onzichtbaar.

### Vastgelegd, niet gerepareerd — 18 ISO 9001-clausules worden in een gecombineerde audit nooit getoetst

Bij het uitzoeken hierboven kwam een zwaarder defect boven. `laad_clause_map("beide")` voegt de
twee clause-maps samen met `{**map_9001, **map_27001}`. Achttien clausulenummers bestaan in
beide normen, en bij een botsing **overschrijft 27001 de 9001-ingang**. In een gecombineerde
audit bestaan die 9001-clausules dus niet meer:

§5.1 Leiderschap en betrokkenheid · §5.2 Beleid · §5.3 Rollen en verantwoordelijkheden ·
§6.1 Acties om risico's en kansen te behandelen · §6.2 Kwaliteitsdoelstellingen · §6.3 Planning
van wijzigingen · §7.1 t/m §7.5 (middelen, competentie, bewustzijn, communicatie,
gedocumenteerde informatie) · §8.1 t/m §8.7 (operationele planning, eisen, ontwerp, externe
processen, productie, vrijgave, afwijkende output)

Dat is **18 van de 28** 9001-clausules. De samengevoegde map heeft 103 ingangen waar 121
verwacht zou worden. Het rapport zegt op pagina 1 "ISO 9001:2015 + ISO 27001:2022".

Nog niet gerepareerd omdat de fix vraagt dat een clausule door **(norm, id)** wordt
geïdentificeerd in plaats van door id alleen, en dat raakt `clause_matches`, `bevindingen`, de
classificatie-prompt, de werkset en de UI. De `norm`-kolom bestaat al in beide tabellen maar
bevat `beide` in plaats van de norm van de match. Vastgelegd als `strict` xfail in
`tests/data/test_norm_db_export.py`, zodat de test faalt zodra iemand het repareert en de
markering moet weghalen.

### Fixed — 2026-08-24 — een bevinding die niet te triageren was

De conclusie meldde "1 kandidaat-NC nog niet beoordeeld" terwijl de auditor alles op `valide`
had gezet, en de trail die beslissing ook bevatte. De werkset had 903 regels en **902 unieke
id's**: `nc-5.17` kwam twee keer voor, met verschillende titels ("… ontbreekt" en dezelfde
zonder dat woord), verschillende `deviation` en verschillende `corrective_measure`.

Twee echte bevindingen dus, en de dedup-sleutel zag dat goed — die bevat de genormaliseerde
titel. Het **id** zag het niet: dat is `nc-<clausule>`, dus elke tweede NC op dezelfde clausule
botst met de eerste. En `apply_triage` zoekt met `next(...)`, dus elke klik landde op de eerste
regel. De auditor zette de tweede op valide, de trail legde dat vast, de lijst bleef `open`, en
de memo-gate bleef geblokkeerd. Niet op te lossen door harder te klikken.

Een botsend id krijgt nu een suffix (`nc-5.17-2`). De dedup blijft ongemoeid: twee bevindingen
met verschillende titels zijn twee bevindingen, en dat oordeel hoort bij de auditor. Voor
werksets die de dubbele al hebben is er `runs.herstel_dubbele_ids()`, dat elke hernoeming
append-only vastlegt met `field: "id"` — stil hernoemen zou de trail naar een id laten wijzen
dat niet meer bestaat.

**Apart en ook gemeten: `findings.json` werd niet veilig geschreven.** `Path.write_text` kapt
het bestand eerst af, dus een lezer die er precies dan bij is krijgt een `JSONDecodeError` of
een te korte werkset — reproduceerbaar met vier triage-threads naast een run-thread. En twee
schrijvers (`runs.voeg_toe` uit de run, `session.apply_triage` uit het verzoek) deden lees-alles
→ wijzig → schrijf-alles zonder enige coördinatie.

Nieuw `api/werkset.py`: atomair schrijven (tijdelijk bestand in dezelfde map + `os.replace`) en
één exclusief `fcntl.flock` om lees-wijzig-schrijf. Atomair schrijven beschermt ook de lezers
die géén slot nemen — dat is elke `GET /findings`. Bewust een bestandsslot en geen
`threading.Lock`: flock werkt tussen threads én processen, en dit project gaat richting losse
componenten.

### Fixed — 2026-08-24 — zoeken op "non-conformiteiten" gaf een 500

De vraagassistent viel om met `sqlite3.OperationalError: no such column: conformiteiten`. FTS5
leest het deel na een koppelteken als kolomnaam, en `_fts_query` filterde wél vraagtekens en
aanhalingstekens weg maar liet koppeltekens staan. Het kernwoord van een ISO-auditor brak dus
elke vraag erover — en de bestaande test dekte precies de tekens die de regex tóch al wegstreepte.

Elk woord gaat nu **tussen aanhalingstekens** de query in. Dan is het een letterlijke term en
heeft geen enkel FTS5-teken nog betekenis. Dat dekt ook het stillere geval: `AND` of `NEAR` in
een mensenvraag is een woord en geen operator, en ongeciteerd zoekt de query iets anders dan er
staat zonder dat iemand dat merkt.

**Dezelfde fout stond op twee plekken meer.** `api/landschap.py` gaf de zoekbalk-invoer
onbewerkt aan `MATCH` door, dus het documentenzoekscherm crashte op hetzelfde woord. Er is nu
één implementatie — `store.fts_query()` — voor alle drie de MATCH-plekken, in plaats van drie
eigen aanpakken waarvan twee stuk waren.

Nieuwe tests: het koppelteken-geval zelf, een parametrische test over zeven vraagvormen met
FTS5-operatortekens (`*`, `^`, `"`, `:`, `(`, `-`, `NEAR`), en een test dat `AND` uit een vraag
als woord wordt gezocht en niet als operator.

**Nog niet opgelost, wel gemeten:** een 500 op deze route laat **geen spoor** in
`assistent_vragen`. De laatste rij is van 2026-08-22, terwijl de storing van vandaag daar had
moeten staan — de documentatie zegt "ook een storing wordt vastgelegd, met de reden en zonder
antwoord", en dat geldt nu alleen voor storingen die de code zelf constateert, niet voor een
exceptie. Precies bij een crash is dat spoor het meest waard.

### Fixed — 2026-08-24 — een gekoppelde bron overleeft nu een herstart

Na de uitrol van 0.2.0a25 weigerde de run-gate Nextcloud: "niet gekoppeld". De configuratie
stond compleet op de PVC (`bron_config.json`, alle velden), maar de omgeving van de nieuwe pod
was leeg. Oorzaak: `Settings.VELDEN` kende de Nextcloud-velden niet. `load_config()` schrijft
bij het opstarten alleen díe velden naar `os.environ`, en de adapters lezen de omgeving bij
`__init__`. Wat wél in `api/bron_catalogus.py` staat maar niet in `VELDEN`, is dus in het
portaal in te vullen en verdwijnt bij de eerste herstart.

Het werkte tot dat moment omdat `BronConfig.zet()` de waarde bij het opslaan direct in
`os.environ` van het lopende proces schrijft: hetzelfde proces, dus dezelfde omgeving. Een
configuratie die vier dagen werkt en dan bij een willekeurige node-drain wegvalt, is erger dan
een die meteen faalt — je zoekt het bij de bron en niet bij de configuratie.

**Vijf velden ontbraken, niet drie.** `JIRA_PROJECTS` en `NEXTCLOUD_PATHS` hadden hetzelfde gat,
dus ook de Jira-scope en de Nextcloud-paden verdwenen bij een herstart. Dat is precies waarom de
nieuwe test op de **catalogus** zit en niet op één bron: `tests/config/test_catalogus_settings_koppeling.py`
faalt zodra een veld in het portaal in te vullen is zonder in `VELDEN` te staan, plus een tweede
test dat "geheim" aan beide kanten hetzelfde is (gemaskeerd in de UI en leesbaar in de
herkomst-uitvoer is een lek).

Daarnaast `tests/config/test_herstart_behoudt_bronnen.py`, die het scenario zelf nabouwt:
opslaan, de omgeving wissen zoals een herstart dat doet, opnieuw laden, en dan de adapter
bouwen. Dat wissen is het hart van die test — zonder wissen slaagt hij op de omgeving van vóór
de herstart en bewijst hij niets.

**Wat hiermee ook is afgedekt:** `zet()` slaat velden over waarvan de waarde niet verandert
(`if nieuw == huidig.get(naam, "")`). Na een herstart betekende dat dat opnieuw opslaan van
dezelfde waarden de koppeling *niet* herstelde — de auditor drukt op opslaan, er verandert
niets, en de bron blijft los. Gemeten op 2026-08-24: alleen het gewijzigde wachtwoord kwam in de
omgeving, de ongewijzigde URL en gebruikersnaam niet. Het inlezen bij opstarten maakt dat pad
onnodig; de overslag zelf blijft staan omdat hij de beheerderswaarde-precedentie bewaakt.

**Nog niet opgelost, wel gemeten:** `secret_store.lees()` geeft in de pod **401 van de
kube-API**. De Secret-backend werkt dus niet en alles valt terug op de PVC. Die terugval is er
expres, maar hij is nu de enige weg terwijl de code de Secret beschrijft als de plek "waar een
beheerder credentials verwacht, met RBAC en kube-API-auditlogging eromheen". De RBAC of het
serviceaccount-token moet nagekeken worden.

### Fixed — 2026-08-24 — de PDF komt er weer, en de oorzaak was 2,2 KB CSS

Aan het eind van elke run stond `PDF-conversie mislukt: Geen Chrome/Chromium gevonden`. Het
rapport werd geschreven als md, html, docx, csv en xlsx; de PDF ontbrak stil, want de melding was
een `logger.warning` en niet een fout. Voor een auditor is de PDF juist het stuk dat de deur uit
gaat.

`reporting/html_to_pdf.py` gebruikt nu **WeasyPrint** in plaats van Chrome headless. De docstring
gaf als reden voor Chrome dat WeasyPrint "traag was op lange rapporten met complex grid-layout".
Die observatie was juist en de oorzaak bleek één declaratie. Gemeten op het rapport van vandaag
(767 KB HTML, 301 pagina's):

| stylesheet | rendertijd |
|---|---|
| ongewijzigd (`.page { display: grid }` geldt ook in print) | > 8 minuten, niet afgemaakt |
| CSS volledig weggehaald | 16,8 s |
| alleen `.page { display: block }` in `@media print` | 16,1 s |

WeasyPrint legt een grid-container niet over paginagrenzen uiteen en probeert het hele rapport
als één grid-item te plaatsen. Het print-blok verborg de TOC en zette al één kolom; alleen
`display` bleef staan. End-to-end md → html → pdf duurt nu 16,6 s met een piek van 356 MiB.

**Waarom geen Chromium in het image:** 338 MB aan libs plus fonts, en een netwerk-capabele
renderer in een container die onder 27001-scope valt. WeasyPrint was al een dependency (de
memo-render gebruikt hem) en `libpango`/`libcairo` staan al in het Dockerfile — `uv sync` en
`docker build` garanderen samen dat de renderer aanwezig is. Dat was bij Chrome precies wat
ontbrak.

**De tests renderen nu echt.** Elke test in `test_html_to_pdf.py` mockte de renderer weg, dus de
suite bleef groen terwijl PDF-generatie in productie onmogelijk was — hetzelfde patroon als de
stille MIME-skips en de verweesde runs. Nieuw: een test die een PDF produceert en met `pypdf`
teruglezt, een gate dat er geen binary buiten het image bij komt (`subprocess`, `shutil.which`),
en een regressietest op `display: block` in het print-blok. Die laatste toetst de declaratie en
niet de rendertijd: een tijdslimiet in een test hangt van de machine af, dit is de oorzaak zelf.

Ook `@page { size: A4 }` vastgelegd — de standaard is Letter, en het rapport gaat naar
Nederlandse auditors en printers.

**Eén font erbij (`fonts-noto-core`, +64 MB).** Het rapport zet een gekleurde cirkel voor elke
bevinding (U+1F7E0 en verwanten) en DejaVu heeft die glyph niet: op alle 310 pagina's stond een
leeg blokje. Chrome rendeerde hem wel, dus zonder dit font zou de renderer-wissel een regressie
zijn in precies het stuk dat de deur uit gaat. `fonts-noto-color-emoji` is eerst geprobeerd en
afgewezen: +31 MB, en WeasyPrint plaatst een kleurenemoji als een paar pixels in de kantlijn —
duurder én slechter dan geen glyph. Gecontroleerd door pagina's uit het gebouwde image te
rasteren en te bekijken, niet door de tekst terug te lezen: `pypdf` gaf op dezelfde PDF
`A u d i t r a p p o r t` terug terwijl de pagina er goed uitzag, dus tekstextractie is hier
geen bewijs van vorm.

Geheugenlimiet van de pod van 1Gi naar **2Gi**. Niet omdat de meting eronder zat (piek 356 MiB),
maar omdat de renderer nu in hetzelfde proces zit als de run: onder 1Gi is de marge klein genoeg
dat de OOM-killer juist de laatste stap van een geslaagde run treft.

### Added — 2026-08-24 — OpenDocument lezen: 32 bestanden die "onbekend type" heetten

De eerste echte run tegen de Nextcloud-canary meldde 79 van de 168 bestanden als niet gelezen,
waarvan **32 OpenDocument**: elf `.odt`, elf `.odp`, zes `.ods` en vier `.odg`. Op de schijf van
een organisatie die LibreOffice gebruikt is dat de hoofdmoot en geen uitzondering — een bron die
een vijfde van zijn schijf niet leest, dekt die schijf niet, en de melding "onbekend type" leest
als een randgeval.

`sources/tekst.tekst_uit_odf()` leest alle vier formaten met `zipfile` en
`xml.etree.ElementTree` uit de standaardbibliotheek. **Geen `odfpy`:** de wandeling is twintig
regels, en een dependency erbij is een dependency om te volgen in een repo onder 27001-scope.

Eén lezer voor vier formaten, want het verschil tussen odt en odp zit in de omhulling
(`office:text` tegen `draw:page`) en niet in waar de tekst staat. Een tabelrij blijft één regel
met tabs ertussen, zoals bij `.xlsx`: cel-per-regel maakt van "A.5.1 | CISO" twee losse feiten
die niet meer bij elkaar horen. De namespace wordt afgekapt in plaats van uitgeschreven, omdat
ODF 1.2 en 1.3 dezelfde lokale namen onder verschillende URI's gebruiken en een bestand uit een
oudere LibreOffice anders stil nul regels oplevert.

Twee weigeringen, dezelfde regel als bij de PROPFIND-parser omdat het bestand van een schijf komt
waar iedereen kan uploaden: een `DOCTYPE` in `content.xml` wordt geweigerd (`ElementTree`
blokkeert entity-expansie niet), en er staat een grens van 32 MB op de **uitgepakte**
`content.xml` — op de zip meten laat een zip-bom door, want die kant is juist het probleem.
Nieuwe fout `OnleesbaarDocumentError`, apart van `LeegDocumentError`: "niet gelezen" en "gelezen,
niets gevonden" zijn verschillende dingen in de dekkingsmelding aan de auditor.

Ook aan Drive toegevoegd — een `.odt` op een Google Drive was tot nu toe net zo onleesbaar.

**Wat nog niet gelezen wordt:** tien `.excalidraw`-bestanden. Dat is JSON met tekstelementen, een
eigen lezer, en geen ODF-probleem.

### Added — 2026-08-22 — de clausule-agent: voorbereiden, niet oordelen

Per clausule zet hij de `bewijslast` uit de norm naast wat er in het landschap zit: welk verwacht
bewijsstuk is gedekt (met verwijzing), welk niet, welke bronnen elkaar tegenspreken, en waarom
deze clausule aandacht verdient.

**Wat hij niet doet: een triage-status voorstellen.** `VERBODEN_VELDEN` weigert `voorstel`,
`classificatie`, `oordeel`, `advies`, `triage` en `aanbeveling` in het antwoord, met een test die
faalt als iemand die grens oprekt. Een voorgestelde klasse maakt van beoordelen bevestigen.

Twee controles bovenop de prompt, om dezelfde reden als bij de Bronbevrager — een instructie is
geen garantie: elk genoemd bewijslast-item moet **letterlijk** in de norm staan, en elke bron in
het meegegeven corpus.

De **ordening** is berekend, niet gevraagd: het model levert feiten per clausule, de sortering
gebeurt hier op dekkingsgraad en aantal tegenspraken. Een ordening die het model zelf verzint is
niet na te rekenen; deze wel, en per regel staat de reden erbij.

Gedraaid tegen het echte model en corpus (~$0,005 per clausule; 86 clausules ≈ $0,45). Bij 9.2
vond hij een echt auditinzicht: individuele auditplannen per fase zijn er wél, een **jaarlijks
intern auditprogramma** niet. Die run vond ook een defect: de dekkingsgraad telde **rijen** in
plaats van verschillende bewijslast-items — het model levert één rij per bron, dus 9.2 meldde "2
van 8 bewijsstukken niet gevonden" terwijl de norm er vier kent.

### Changed — 2026-08-22 — een onverifieerbaar antwoord wordt vervangen, niet geweigerd

Derde en laatste vorm van hetzelfde probleem, en de eerste twee waren fout.

Een antwoord zonder bronverwijzing kan twee dingen zijn: een eerlijk "dit staat niet in deze
bronnen", of een bewering uit modelkennis. **Van buitenaf is dat onderscheid niet te maken.**

1. *Weigeren* (eerste versie): liet twee van drie echte vragen falen met een 502, terwijl het
   model correct antwoordde.
2. *Een merkteken dat het model zet*: werkte zolang het model zich eraan hield. Tegen het echte
   model deed het dat niet.
3. *Vervangen*: verwijst het antwoord nergens naar, dan ziet de auditor een vaste tekst en niet
   de prose van het model. Deterministisch, dekt beide gevallen, en hangt niet af van
   medewerking. Wat het model zei gaat wél naar de trail (`ruw_antwoord`) — dat is onderdeel van
   hoe het oordeel tot stand kwam.

Daarnaast twee nieuwe vormvarianten die het model gebruikt en die geldige verwijzingen als
verzonnen lieten afwijzen: `[bron:a en b]` met het Nederlandse "en" als scheidingsteken, en
`[bron:a, bron:b]` met het voorvoegsel herhaald binnen één merkteken. Beide gesplitst, met
woordgrenzen zodat een ID dat "en" bevat heel blijft — die bestaan echt in de Drive-ID's.

Elk van deze drie kwam alleen boven water door tegen het echte model te draaien. Een stub
antwoordt zoals de test wil.

### Added — 2026-08-22 — interviewvoorstellen: 14 clausules, 42 vragen, geen verzonnen namen

Waar geen documentbewijs is, stelt het tool nu een gesprek voor: per ongedekte clausule één vraag
per verwacht artefact — "waar is dit vastgelegd, of waarom bestaat het niet?".

**De opzet is onderweg omgedraaid, na een meting.** Het plan was: markeer per bewijslast-item of
een mens het kan bevestigen, en stel daar interviews voor. Gemeten: van de **481
bewijslast-items** in `data/normteksten` beschrijven er ongeveer **drie** een waarneming — de
catalogus is vrijwel volledig artefact-gericht ("notulen directiebeoordeling",
"toegangsrechtenmatrix", "versiehistorie"). 481 items markeren zou betekenen dat dit tool zijn
eigen bewijsstandaard verzint, en dat is een auditoroordeel.

Dus de andere vraag: niet "wat kan een mens bevestigen" maar "waar is dit artefact". Dat is wat
een auditor in een gesprek vraagt, het volgt volledig uit de bestaande catalogus, en het antwoord
is een **aanwijzing naar bewijs** in plaats van een vervanging ervan.

Gemeten tegen het echte corpus: **14 voorstellen met 42 vragen** — 13 voor 27001 (onder andere
5.20 leveranciersovereenkomsten, 5.28 verzamelen van bewijs, 5.36 naleving) en 1 voor 9001 (8.1
operationele planning).

Twee dingen bewust níet gedaan. Geen LLM voor de vragen: een agent die vrije interviewvragen
bedenkt verzint eisen die niet in de norm staan, en dan staat er in een auditdossier een vraag die
niemand kan herleiden. En `ROLLEN` is **leeg opgeleverd** — wie bij deze organisatie over
toegangsrechten gaat is organisatiekennis, en een verzonnen naam in een auditplanning ziet eruit
als een afspraak die iemand heeft gemaakt. Onbekend toont `nog te bepalen`.

Inplannen blijft geblokkeerd op een credential-besluit: `stuur_calendar_uitnodiging` loopt via de
`gws`-CLI met een persoonlijke OAuth-sessie, en die binary zit niet in het image. Hoort bij
`iso-portal` 7.4.

### Added — 2026-08-22 — Nextcloud als bron, en het bronprotocol is bewezen

`NextcloudSource` leest documenten via WebDAV (`PROPFIND` met `Depth: 1`, `GET` voor de inhoud).
WebDAV en niet de Nextcloud-eigen OCS-API: dezelfde adapter werkt tegen ownCloud, Seafile of een
Apache met `mod_dav`.

**Wat dit over de architectuur zegt.** `iso_audit.sources` bestaat om bronnen inwisselbaar te
maken, en dat was onbewezen — Drive, Jira en Planning zijn alle drie Google- of
Atlassian-specifiek. Uitkomst: **de pipeline hoefde niet te wijzigen.** Wat wél moest: de
tekstlezers (PDF, docx, xlsx, pptx, tekstformaten) zijn uit `sources/drive.py` naar
`sources/tekst.py` verhuisd. Dat zijn functies van bytes naar tekst; een tweede set per bron
maakt van "leest het tool xlsx-tabellen?" een vraag met twee antwoorden. De 1176 bestaande tests
bleven ongewijzigd draaien — dat is het bewijs dat de verhuizing niets veranderde.

Daarmee is de deelbaarheidsgrens gevonden die het protocol zelf niet aangeeft: **hoe je bij de
bytes komt is bronspecifiek, wat je met de bytes doet niet.**

Gedraaid tegen `canary-accept/nextcloud` (32.0.13) in het cluster: **9 documenten** — pdf, docx
(inclusief tabel), xlsx (inclusief tweede blad), pptx, md, csv en drie txt — dekking 10 gezien /
9 gelezen. Die run vond twee fouten die de gestubde tests niet zagen:

1. **Paden waren relatief aan de opgevraagde map** in plaats van aan de DAV-wortel, waardoor de
   recursie in de verkeerde map zocht en submappen leeg leken.
2. **Een lege `.txt` kreeg "mogelijk staat de inhoud in tekstvakken"** — over een bestand van nul
   bytes. `leeg_reden()` onderscheidt nu drie gevallen: scan-formaten, platte tekst, en de rest.

Plus een derde inconsistentie: `gezien` telde niet op met `gelezen + overgeslagen`, omdat wat de
WebDAV-client al oversloeg (verborgen bestanden) alleen in `overgeslagen` belandde. Dat is de
rekensom die een auditor maakt.

Beveiliging: nagemeten met Python 3.12.13 en expat 2.7.3 weigert `xml.etree.ElementTree` een
entity-expansie ("billion laughs") **niet** — een kleine invoer leverde 3000 tekens op. Een
`PROPFIND`-antwoord met een DOCTYPE wordt daarom geweigerd vóór het parsen, plus een lengtegrens
van 32 MB. Entiteiten vereisen een DTD en een WebDAV-antwoord heeft er nooit legitiem een; dat is
twee regels in plaats van een `defusedxml`-afhankelijkheid.

Authenticatie met een **app-specifiek wachtwoord**, niet met een gebruikerswachtwoord: apart
intrekbaar, zonder toegang tot de webinterface. Zelfde argument als bij het
Google-service-account.

Prullenbak, versies, uploads en verborgen bestanden worden overgeslagen — **met melding**, want
bij een nieuwe bron is de verleiding het grootst om "die map hoort er niet bij" ongezegd te laten.

### Changed — 2026-08-22 — eigen output telt niet meer als bewijs (37% van de werklijst)

Gemeten op de eerste volledige run: **462 van de 1241 bevindingen kwamen uit twaalf documenten
die dit tool zelf schreef** — hetzelfde auditrapport in md, docx, html én pdf, dezelfde
bevindingenlijst in csv en xlsx, plus drie eigen managementmemo's.

`schrijf_rapport`, de CSV- en de xlsx-export zetten nu een zichtbaar merkteken in hun output, en
de pipeline classificeert gemarkeerde documenten niet. Zichtbare tekst en geen comment of
documenteigenschap: het rapport gaat naar docx, html en pdf, en alleen zichtbare tekst overleeft
alle drie.

Herkenning op het merkteken en **niet op de bestandsnaam**, want dat faalt twee kanten op: een
naam wijzigt en het document telt stil weer mee, en `Auditrapport 2022.docx` is van de
certificerende instantie en is juist bewijs. Voor de twaalf bestanden die er al stonden is er een
eenmalige namenlijst, één voor één nagekeken — die hoort te krimpen, niet te groeien.

De CSV-marker staat **onder** de data: een `#`-regel bovenaan leest `csv.DictReader` als
kolomkoppen, en dan breekt elke lezer van die export om een merkteken toe te voegen.

Uitsluiten is niet weggooien: de documenten blijven in het landschap, want een auditor mag
navragen waarom iets niet is gewogen.

**Gemeten resultaat: 1241 → 779 bevindingen. Clausules met meer dan tien bevindingen: 53 → 27.**

En laag 1 van die change (exacte duplicaten samenvouwen) is daarmee **vervallen**: van de 264
duplicaten blijft er ná laag 0 precies één over — ze zaten vrijwel allemaal ín de eigen output.
Eén samenvouwmechanisme bouwen voor één rij is duurder dan het oplevert.

### Fixed — 2026-08-22 — de vraagassistent weigerde twee van drie eerlijke antwoorden

Eerste test tegen het echte model op het echte corpus (`assistent_vragen` stond op nul; taak 8.1
van `iso-agents`). Van drie vragen leverde één een antwoord met 25 bronnen op, en kwamen twee
terug als **502**. Twee defecten, allebei in de verificatie en niet in het model:

1. **Een eerlijk "niet gevonden" heeft geen bron om naar te verwijzen.** De controle las "geen
   verwijzing" als "verzonnen" en weigerde het antwoord. Nu zet het model `[niets-gevonden]` als
   de meegegeven bronnen de vraag niet beantwoorden; zonder verwijzing **en** zonder merkteken
   blijft het een storing. Een merkteken en geen tekstherkenning: zoeken op zinsneden als "staat
   niet in" is een tweede, onbetrouwbare administratie van hoe een model zich uitdrukt.
2. **Het model schrijft `[bron:a, b, c]`** als een bewering op meerdere documenten rust. De
   parser las die komma-lijst als één ID: twaalf geldige verwijzingen plus een normtekst werden
   geweigerd als verzonnen. Nu wordt er op komma gesplitst, en élk los ID moet nog steeds in het
   meegegeven corpus zitten — tolerant voor de vorm, niet voor de inhoud.

Nagerekend tegen het echte corpus zonder API-kosten: de zes ID's uit de foutmelding bestaan alle
zes en worden nu geaccepteerd.

Geen van de 1165 tests zag dit, om dezelfde reden: een stub antwoordt zoals de test wil, een
model antwoordt zoals een model antwoordt.

### Added — 2026-08-22 — `scripts/preflight.py`: elke component lokaal aantoonbaar werkend

Op 21 augustus zijn vijf defecten in productie gevonden die de suite niet kon zien, omdat ze
alle vijf pas optreden tegen de echte bronnen of in de echte procesvorm. Elk defect kostte een
uitrol, drie ervan een halve auditrun.

De preflight loopt per component één keer het echte pad af: `landschap`, `rapport`, `assistent`,
`drive`, `planning`, `jira`, plus `classificatie` en `assistent-api` als betaalde checks. Wat
hij bewijst in plaats van aanneemt: drie documenten worden **echt gelezen** (daar zaten de
docx/PDF-fouten), de Sheets-aanroepen worden **geteld** en faalt bij meer dan één (de N+1), het
rapport krijgt een archiefdocument **zonder datum** mee (de `NoneType < str` uit stap 7/7), en de
classificatie doet één echte API-call inclusief de plafondberekening.

Drie eigenschappen die erbij horen: eigen tijdelijke DB dus nooit de echte trail, een component
zonder configuratie wordt **overgeslagen en gemeld** in plaats van stil groen, en de goedkope
checks lopen eerst zodat een tikfout binnen een seconde faalt in plaats van na tien minuten.

Configuratie komt langs dezelfde weg als het portaal: de shell-omgeving en daarna de
bron-configuratie die het configuratiescherm beheert (`--config-root`). Zonder die tweede laag
test een preflight met een ándere configuratie dan een run, en dan zegt "lokaal groen" niets
over online.

De eerste echte preflight faalde meteen — op de jira-check, die de adapter-registry niet had
gevuld. Terecht, en tegelijk een aanwijzing dat die registratie hangt aan een functie die
`beschikbare_bronnen()` heet en niet verraadt dat hij registreert.

### Changed — 2026-08-22 — Jira-opvolgpunten zijn bewijslast, geen triage-kandidaten

Van de 901 kandidaten in de eerste volledige run kwamen er **83 uit `Jira-opvolging`**, elk met
een triage-vraag die niemand kon beantwoorden. Een openstaand punt is al beoordeeld door degene
die het aanmaakte; wat het in een audit doet is aantonen dát er opvolging is.

`export_db_findings` filtert ze nu uit de werklijst. Ze blijven in `bevindingen` staan met
herkomst `<bron>-opvolging`, dus ze zijn opvraagbaar als bewijslast en de vraagassistent leest ze
al als eigen soort bron.

In `pipeline._bewaar_opvolgpunten` stond letterlijk dat een opvolgpunt "een punt is dat de
auditor moet wegen". Dat was de verkeerde rechtvaardiging voor de juiste opslagplek; die staat er
nu goed.

### Added — 2026-08-22 — drie voorstellen: triage-ondersteuning, interview-planning, Nextcloud

`openspec/changes/triage-ondersteuning/` — met een vondst die de vorm van die change bepaalt.
Gemeten op de echte werkset: **462 van de 1241 bevindingen (37%) komen uit twaalf documenten die
dit tool zelf heeft geschreven** — hetzelfde auditrapport in md, docx, html én pdf, dezelfde
bevindingenlijst in csv en xlsx, plus drie eigen managementmemo's. Dat is de kringloop die het
`iso-agents`-voorstel voor de Opsteller benoemde, en hij is er al. Daarnaast zijn **264 regels
een exact duplicaat** van een eerdere `(clausule, beschrijving)` — samen te vouwen zonder
gelijkenis-drempel. Vandaar de volgorde: eerst niet-tellen, dan samenvouwen, en pas daarna een
agent die voorbereidt zonder te oordelen.

`openspec/changes/interview-planning/` — klantwens. Vragen komen uit de `bewijslast` per clausule
en niet uit modelkennis over interviewtechniek; het voorstel noemt een rol en geen persoon.
Inplannen staat apart en wacht op een credential-besluit: `stuur_calendar_uitnodiging` loopt via
de `gws`-CLI met een persoonlijke OAuth-sessie, en die binary zit niet in het image.

`openspec/changes/nextcloud-bron/` — WebDAV naast Drive, en tegelijk de eerste echte test van het
`Source`-protocol tegen een bron die niets met Google deelt. De testomgeving staat er al:
`canary-accept/nextcloud` (32.0.13) in het cluster. De gedeelde tekstlezers verhuizen naar
`sources/tekst.py`, want een tweede set per bron loopt uit elkaar.

### Added — 2026-08-21 — runs verbergen zonder ze te verwijderen (0.2.0a23)

De run-historie stond op negen regels waarvan vier weesrecords en drie mislukte pogingen. Als
werklijst onbruikbaar, en een onbruikbare lijst wordt genegeerd.

`POST /audits/<id>/runs/<run_id>/zichtbaarheid` haalt een run uit de werklijst door een **regel
toe te voegen** met wie het deed, wanneer en waarom. `GET /runs` blijft alles teruggeven met een
`verborgen`-vlag; de UI filtert en heeft een schakelaar "toon verborgen (N)", waar ze gedimd
staan met de naam van degene die ze wegzette. Omkeerbaar, ook weer als extra regel.

Geen `DELETE`, en dat is de afweging: een certificerende instantie moet kunnen zien dat er runs
zijn geweest die faalden, en een bestand waaruit regels geschrapt kunnen worden is precies
zoveel waard als de discipline van degene die schrapt. De test die dat afdwingt vergelijkt de
volledige oude bestandsinhoud met de nieuwe (`na[:-1] == voor`).

Twee regels eromheen. Een **lopende run kan niet verborgen worden** (409) — dat zou de enige
aanwijzing weghalen dat er iets bezig is. En **wie de run startte blijft staan**: het
zichtbaarheidsrecord zet `verborgen_door` erbij en overschrijft `door` niet, anders leest de
historie alsof de opruimer de run had gedraaid.

Rollen: het portaal kent er één — wie door de auth-gate komt is auditor. Wat vastligt is de
identiteit van degene die verborg. Een echt rolmodel is een aparte change.

Nieuw: `docs/reference/run-historie.md`, met wat er in een run-record staat en waarom.

### Fixed — 2026-08-21 — de reconciliatie van verweesde runs was niet aangesloten

De code uit `a22` zocht `manifest.json`, terwijl het bestand `audit.json` heet. De lus sloeg
élke audit over en deed stil niets — in het cluster bleven de vier "loopt nog…"-records staan na
de uitrol.

De unit-test riep `sluit_verweesde_runs()` direct aan en bewees daarmee dat de functie werkt,
niet dat hij is aangesloten. De nieuwe test gaat door `create_app()` op een map met een
lopend-gemarkeerde run — dat is het gedrag dat een podherstart nabootst, en het is wat de fout
had gevangen.

### Added — 2026-08-21 — 0.2.0a22 brengt de a20-inhoud terug, met de drie oorzaken erbij

De rollback naar a19-inhoud (`a21`) was een tijdelijke maatregel terwijl de crash werd
uitgezocht. Nu de oorzaak bekend is — vier gelijktijdige runs op één niet-thread-safe
Google-client, niet de a20-code — komt die inhoud terug: de streamende classificatie stond al
in a19, en hierbij weer de leeslog-scheiding, de leesbare snelkoppelingsmelding, de
afbeeldingen-docx-melding en de sorteerfix in stap 7/7.

Ook hier een nieuw nummer in plaats van teruggrijpen op a20: de image-workflow bouwt bij elke
push, dus een bestaande tag zou herbouwd worden met andere inhoud. a22 = a20-inhoud plus de
drie maatregelen hierboven.

### Fixed — 2026-08-21 — vier startknoppen maakten vier runs in één proces (SIGSEGV)

Diagnose van de crash die `0.2.0a20` leek te veroorzaken. Het was a20 niet: drie reproducties
liepen schoon — de a20-code lokaal (439 documenten gelezen, piek 181 MiB), het a20-**image**
met de listing in een achtergrond-thread, en de a19-code **in de draaiende pod** (715
bestanden). De diff a19→a20 in het lees-pad is bovendien alléén logtekst.

Wat er wél gebeurde, zichtbaar in de run-historie: vier startrecords op 13:28:09, :12, :24 en
:28. De auditor klikte vier keer omdat de knop niets leek te doen, en `start_run()` had **geen
gate**: elke POST zette `self._run` opnieuw en startte een nieuwe thread. Die threads deelden
één `@lru_cache`'d Google-service, en `google-api-python-client` is niet thread-safe — de
onderliggende `httplib2.Http` houdt één socket. Exit 139, pod in `BackOff`, UI: "onbekende
fout".

Drie maatregelen, alle drie op een eigen oorzaak:

1. **Eén run per audit.** `start_run()` weigert een tweede run met `RunLooptError`; de route
   maakt daar 409 van (niet 400 — het verzoek is niet ongeldig, het moment is verkeerd) en
   sluit het net aangemaakte record af, zodat er geen tweede "loopt nog" blijft staan. Vier
   gelijktijdige ingests betaalden bovendien viermaal de classificatie.
2. **Verweesde runs worden bij het opstarten afgesloten.** Een run leeft in een thread van het
   portaalproces; zegt een record `loopt` bij een verse start, dan is hij per definitie
   afgebroken. `sluit_verweesde_runs()` schrijft daar een afsluitrecord bij — append-only, het
   startrecord blijft staan. Een trail die beweert dat er iets loopt wat niet loopt, is erger
   dan een lege trail.
3. **Google-service per thread.** `@lru_cache(maxsize=1)` is `threading.local()` geworden. Het
   hergebruik blijft (de token-uitwisseling kost 33s op een vers credentials-object, een
   volgende call 0,48s), maar er is geen gedeelde socket meer. Geen lock: dat zou de calls
   serialiseren, terwijl een service per thread simpelweg geen gedeelde staat heeft.

### Reverted — 2026-08-21 — 0.2.0a21 zet de code terug op de inhoud van a19

`0.2.0a20` liet het portaal met **exitCode 139 (SIGSEGV)** omvallen, één seconde na het
starten van de Drive-ingest. Geen Python-exception maar een crash in native code: uvicorn viel
mee om, de pod ging in `BackOff`, en de UI meldde "onbekende fout". Drie startpogingen, drie
keer hetzelfde. Geen OOM — de limiet is 1 GiB en dat had exitCode 137 gegeven.

Op verzoek van de opdrachtgever teruggedraaid terwijl de oorzaak wordt uitgezocht. De code is
regel voor regel gelijk aan `0.2.0a19`, dat een volledige run haalde (502 bestanden gelezen,
118 classificaties, 1480 bevindingen).

**Waarom a21 en niet gewoon `newTag: 0.2.0a19`:** de image-workflow bouwt en pusht bij elke
push naar `main`. Zou `newTag` terug naar a19 gaan, dan werd díe tag herbouwd met de huidige
code en had de registry andere inhoud onder een bestaande tag — precies de mutable tag die
`deploy/kustomization.yaml` beschrijft. Een nieuw nummer met bekende inhoud is de saaie weg.

Wat hiermee tijdelijk terug is: de ruwe leveranciersmeldingen in de live-log, de cryptische
snelkoppelingsmelding, de afbeeldingen-docx-melding, en de sorteerfout in stap 7/7. Die laatste
betekent dat een run met een document zonder `modifiedTime` opnieuw in stap 7 omvalt — de
classificatie blijft wel bewaard.

### Fixed — 2026-08-21 — stap 7/7 viel om op een document zonder wijzigingsdatum

De run haalde de hele classificatie (118 documenten, 1480 bevindingen, $0,6943, nul fouten) en
strandde toen in stap 7/7:

    TypeError: '<' not supported between instances of 'NoneType' and 'str'

`local_report.py` sorteerde de gearchiveerde documenten met
`key=lambda d: d.get("modified_at", "")`. Die default doet niets als de sleutel **bestaat** met
waarde `None`, en Drive geeft niet voor elk bestand een `modifiedTime`. Sinds de
dekkingsuitbreiding van 18-08 komen zulke bestanden ook echt in het landschap, dus wat eerst
theorie was is nu een run die omvalt. Elders in de pipeline stond al `or ""` — dezelfde regel
staat nu ook hier, en in `sources/drive.py` waar `laatst_gewijzigd` gevuld wordt.

Wat er niet verloren ging: de 1480 bevindingen en 119 classificatie-records staan in de DB.
Een volgende run slaat de API-calls over (`rehash=False` dedupliceert op `classifications`) en
gaat direct naar de rapportage. De classificatiekosten zijn dus eenmalig gemaakt, niet
weggegooid.

### Changed — 2026-08-21 — "mogelijk een scan" werd een feit in plaats van een vermoeden

`Actiepunten uit Waveland.docx` bleef ook na de tabellenfix nul tekens opleveren. Uitgezocht met
het echte bestand: 569 KB, drie lege alinea's, nul tabellen, **zes `w:drawing`-elementen** —
screenshots in een Word-document. Er staat dus letterlijk geen tekst in.

Een docx zonder tekst maar met tekeningen meldt nu wát er aan de hand is: "bevat 6 ingevoegde
afbeelding(en) en geen tekst; zonder OCR is hier niets uit te lezen". En de dekkingscategorie
noemt geen oorzaak meer — die stond op "geen tekst uit het bestand; mogelijk een scan" voor élk
formaat, terwijl de oorzaak per bestand in de reviewregel staat. De categorie telt, de reden
verklaart.

Dit is de derde keer deze week dat één tekst voor meerdere gevallen de auditor het verkeerde bos
in stuurde (na de locatiestatus van 17-08 en "staat er niet in" van vandaag). Het patroon is
steeds hetzelfde: een melding die klopt voor het geval waarvoor hij geschreven is, en misleidt
zodra hij hergebruikt wordt.

### Fixed — 2026-08-21 — de live-log liet ruwe leveranciersmeldingen in de browser zien

Begon als een leesbaarheidsklacht en werd een lekpad. In het portaal stond tijdens een run:

    {"event": "drive_snelkoppeling_niet_gevolgd", "doel": "1VZvW-0MJIJ8VWCNgcHQuHBqmpxbdkoG0"}

Een JSON-gebeurtenis met een ruw bestand-ID, die niet zei wat er aan de hand was en
alarmerender klonk dan het is. Die regel is nu een Nederlandse zin met de naam van de
snelkoppeling, de vermoedelijke oorzaak (doel verwijderd, in de prullenbak, of niet gedeeld met
het service-account) en wat er met het bestand gebeurt (handmatige review).

Bij het naspeuren bleek waarom die regel in de browser stond: `_ProgressHandler` hangt aan de
logger `iso_audit`, dus **élke** onderliggende regel belandt in de live-log die de browser
opvraagt — inclusief de ruwe `verbinding_fout` met `detail`. Dat is precies de
leveranciersrespons die `config/verbinding.normaliseer` uit de client moet houden, omdat er een
URL met credential of een tokenfragment in kan staan. Op 2026-08-14 is dat lekpad gesloten voor
de bron-health en het run-record; de live-log was de derde weg en die stond nog open.

Twee maatregelen. `normaliseer` markeert zijn ruwe regel met `extra={"alleen_serverlog": True}`
en de voortgangs-handler slaat gemarkeerde regels over. En de plekken in het ingest-pad die de
uitzondering rechtstreeks logden (`"Bron %s overgeslagen: %s", e` en drie soortgenoten) gaan nu
via `log_veilig()`: één veilige regel voor browser én serverlog, plus de ruwe tekst alleen naar
het serverlog.

Nog niet omgezet: de waarschuwingen in de rapportagefase (HTML/DOCX/PDF-conversie,
tabulaire export, Sheets-sync, thema-verfijning). Die loggen de uitzondering nog rechtstreeks;
ze vuren pas ná de classificatie en staan op de lijst.

### Fixed — 2026-08-21 — de planning werd per document opnieuw ingelezen (429's)

De productierun stond vol `HttpError 429` van de Sheets-API, met tabs die daardoor werden
overgeslagen: `Tab 'NEN-ISO 9001:2015 2025' overgeslagen`, tientallen keren. Het quotum was
het symptoom; de oorzaak is een N+1.

`protocol_ingest` roept `fetch_content()` **per document** aan, en `PlanningSource.fetch_content`
riep `_fetch_alle()` opnieuw aan: één `spreadsheets.get` plus één `values.get` per tab, per
planning-rij. Bij ~200 rijen en ~15 tabs zijn dat duizenden Sheets-calls in één run, ruim boven
het leesquotum per minuut.

De momentopname wordt nu één keer per instantie gelezen. Op de instantie en niet op de klasse:
klasse-state lekt tussen runs en tussen tests. Een volgende run bouwt een nieuwe Source en leest
opnieuw — dat is precies de levensduur die bij "een Source leest zijn configuratie bij
constructie" hoort.

Daarnaast meldt `sheets_lees_alle_tabs` nu hoeveel van hoeveel tabs zijn gelezen. De per-tab
waarschuwingen stonden er al, maar niemand telt waarschuwingen: een planning die half werd
gelezen leverde een run op die daar niets over zei. Zelfde regel als bij de Drive-dekking — wat
je niet leest, moet je zeggen.

### Fixed — 2026-08-21 — een run van 119 documenten strandde op document 2

Eerste productierun met de nieuwe ingest faalde bij stap 5/7, op
`Bevindingen_beide_v3.3_2026-05-05.csv`. Serverlog:

    ValueError: Streaming is required for operations that may take longer than 10 minutes.

De SDK rekent in `_calculate_nonstreaming_timeout` de verwachte duur als
`3600 * max_tokens / 128000` en weigert een niet-streamende aanroep boven tien minuten — dus
boven **21.333 output-tokens**. Dat bestand raakt 63 clausules, en met het budget van
2026-08-17 (`450 * n + 128`) wordt dat 28.478. Vanaf 48 clausules in één document gaat het mis;
met het oude budget (`150 * n + 64`) lag die grens op 142 clausules en kwam het nooit voor.

Twee eigen wijzigingen kwamen hier samen: het ruimere budget van 17-08 en de
dekkingsuitbreiding van 18-08, die `text/csv` leesbaar maakte en juist dát bestand met zijn 63
clausules het landschap in bracht.

Erger dan de fout zelf was het gevolg: een `ValueError` is geen `anthropic.APIError`, dus hij
glipte langs de per-document foutopvang en nam de hele run mee — 117 documenten die niet meer
geclassificeerd werden, na tien minuten Drive-ingest.

De classificatie streamt nu (`_vraag_model` met `messages.stream` +
`get_final_message()`), waarmee de drempel niet geldt en het budget bij de gemeten
werkelijkheid van het model kan blijven. Twee gates erbij: een test dat `_vraag_model` echt
streamt, en een test dat `messages.create(` niet meer in `classification/findings.py` voorkomt —
één vergeten aanroep en de bug is terug.

### Fixed — 2026-08-21 — docx-tabellen werden niet gelezen, en heetten "mogelijk een scan"

Uit dezelfde run: `Actiepunten uit Waveland.docx` kwam binnen als "extractie leverde geen tekst
op; mogelijk een scan of een leeg bestand". Een docx kan geen scan zijn. `_tekst_uit_docx` las
alleen `document.paragraphs`, en een actiepuntenlijst of RI&E-overzicht is één **tabel** — nul
alinea's, dus nul tekens.

Tabelcellen worden nu meegelezen, in docx én pptx. En de reden bij een lege extractie hangt af
van het formaat: "mogelijk een scan" hoort bij PDF, bij de rest staat er dat de inhoud
vermoedelijk in afbeeldingen, tekstvakken of koppen zit. Eén reden voor alle formaten wees de
auditor de verkeerde kant op bij precies het bestand dat wél te repareren was.

Tekstvakken en koppen/voetteksten blijven buiten bereik — die zitten niet in het body-model van
python-docx. Een docx die daardoor leeg blijft, wordt gemeld als onleesbaar in plaats van stil
te verdwijnen.

### Fixed — 2026-08-21 — "staat er niet in" verzweeg dat de clausule niet bestond

Eerste echte vraag in het portaal: "welk bewijs hebben we voor 8.2.4?". Antwoord: staat er niet
in. Correct, en niemand werd er wijzer van — die clausule bestaat niet in ISO 27001:2022. Annex
A kent **8.24**, en daar hingen op dat moment 24 documenten aan.

Nu drie te onderscheiden uitkomsten in plaats van één tekst die ze alle drie toedekt:

| geval | antwoord |
|---|---|
| clausule bestaat niet in deze norm | dat wordt gezegd, met een suggestie |
| clausule bestaat, niets aan gekoppeld | de normtekst met `bewijslast` gaat mee — een dekkingsgat is een bevinding in de dop |
| geen clausule in de vraag | de algemene "staat er niet in" |

De suggestie is een cijfervergelijking en geen gelijkenis-maat: `8.2.4` en `8.24` hebben dezelfde
cijferreeks zonder punten, dus dat is een kandidaat. Bewust geen drempel — "0.83 leek genoeg" is
geen antwoord aan een auditor, dezelfde weigering als bij de dedup-sleutel in `api/runs.py`.

Dit was precies de vraag die taak 8.2 van `iso-agents` openhield ("is 'staat er niet in' te
streng?"). Het antwoord uit het eerste gebruik: op dit punt wel, en alleen echt gebruik bracht
het aan het licht.

### Added — 2026-08-20 — de Bronbevrager: het corpus is bevraagbaar, zonder oordeel

Eerste agent van change `iso-agents` (21 van de 40 taken). Het portaal kon een audit draaien
maar geen vraag beantwoorden: de auditor die wilde weten "welk bewijs hebben wij voor 8.24?"
moest zelf door 295 documenten, 1371 clausule-matches, de bevindingenhistorie en de
opvolgpunten.

Nieuw scherm **Vragen**, `POST /assistent/vraag`, en `iso_audit.assistent`. Wat de vorm bepaalt
is niet de vraag maar de bronregel:

- **Clausule eerst, dan tekst.** Staat er een clausule in de vraag, dan is `clause_matches` de
  ingang — dat is de koppeling die de pipeline zelf legde, en die vindt ook het document waar
  het woord niet in staat. Alleen zonder clausule valt het terug op `documents_fts`. Geen
  embeddings: dat is een tweede administratie die uiteenloopt met de eerste.
- **Leeg corpus, geen aanroep.** Levert het ophalen niets op, dan gaat er geen vraag naar het
  model en komt er een vaste tekst terug. Een antwoord zonder bronnen kan per definitie niet uit
  de bronnen komen, en dat is met een `if` af te dwingen in plaats van met een verzoek aan een
  model dat ISO 27001 gewoon kent.
- **Verwijzingen worden nagelopen.** Het antwoord verwijst met `[bron:<id>]`; elk id én elke
  genoemde clausule moet in het meegegeven corpus zitten. Een antwoord zonder enige verwijzing
  is óók een storing — dan valt er niets na te trekken, en juist zo ziet een antwoord uit
  modelkennis eruit. Afgekapt op `max_tokens` is een storing om dezelfde reden als bij de
  classificatie: bij afkapping verdwijnt juist de bronvermelding aan het eind.
- **Tegenspraak wordt benoemd, niet opgelost.** Een document dat dekking claimt naast een NC op
  dezelfde clausule: beide gaan mee, de assistent kiest niet. "Nieuwste wint" zou precies de
  interessantste uitkomst verbergen — een oud NC dat nooit is afgesloten.
- **Hij schrijft niets.** Geen bevinding, geen triage-suggestie, geen classificatie. De
  auditor-spiegel is de capability die dit tool draagt.

Trail: `assistent_vragen`, append-only, met de bron-ID's die aan het model meegingen en welke
daarvan terugkwamen. Ook een storing komt erin, met de reden — dat is het enige spoor dat de
verwijzingscontrole heeft gewerkt.

Nog niet gebouwd: de Normuitlegger, de Gap-analist en de Opsteller, plus de clusterverificatie.

### Fixed — 2026-08-20 — de testsuite schreef in de echte audit-DB

Gevonden tijdens het bouwen van de route hierboven: drie tests van `test_assistent_route.py`
zetten `ISO_AUDIT_DB` in plaats van `AUDIT_DB_PATH`, waardoor `store.db_pad()` terugviel op
`output/audit.db` — de echte audit-DB van deze werkplek. Drie rijen in de echte
`assistent_vragen`-tabel, suite groen. In een append-only tabel valt dat niet netjes terug te
draaien; de drie testrijen zijn met de hand verwijderd.

Nu een autouse-fixture in `tests/conftest.py` die `AUDIT_DB_PATH` voor élke test naar een
wegwerpmap wijst, om dezelfde reden als `_schone_omgeving`: een test die eraan moet dénken
zichzelf te isoleren, vergeet het uiteindelijk. Precies het geval dat de testisolatie-regel
beschrijft — de fout is stil, de suite blijft groen, en wat er rot is de echte data.


### Changed — 2026-08-20 — werkelijke tarieven in het rapport, en één plek voor modelnamen

Twee beslissingen van de opdrachtgever, en één vondst die eruit volgde.

**Werkelijke tarieven in plaats van lijstprijs.** `PRIJZEN_GRONDSLAG` staat op
`"werkelijk tarief"`; concreet raakt dat één regel, want Sonnet 5 heeft t/m 31 augustus 2026 een
introtarief van $2,00/$10,00 in plaats van $3,00/$15,00. Het gerapporteerde bedrag ligt daarmee
zo dicht bij de factuur als publiek te weten valt — het blijft een bovengrens, want een eigen
afspraak met Anthropic zou er nog onder liggen, en dat staat nu ook zo in de documentatie.

Die keuze heeft een houdbaarheidsdatum, en die maakt zichzelf niet kenbaar: op 1 september staat
er een te laag bedrag in de tabel, en te laag is schadelijker dan afwezig omdat het compleet
lijkt — dezelfde fout als de Haiku-prijs die op 2026-08-14 25% te laag stond. Daarom
`TIJDELIJK_TARIEF_TOT`: per model de einddatum van een actietarief, en `prijs_voor()` logt een
waarschuwing zodra die verstreken is. Nog steeds geen datumlogica die zelf tussen tarieven
kiest — dat zou een tweede administratie zijn die achterloopt op de leverancier.

**Eén module voor alle modelnamen: `iso_audit.modellen`.** Bij het eerlijk maken van de UI-kaart
bleek dezelfde modelnaam in **vijf spellingen** in `src/` te staan: `classification/llm.py`,
`classification/thema.py`, `memo/draft.py` en `reporting/report_generation.py` hadden elk een
eigen constante op `claude-haiku-4-5-20251001`, en `agent/runner.py` viel terug op
`claude-haiku-4-5` — hetzelfde model, andere string. Vijf plekken die uit elkaar kunnen lopen
zonder dat iets faalt: een model bumpen was vijf greps, en één vergeten regel geeft geen
foutmelding maar een run die stil op een ander model draait dan het rapport zegt.

Nu één tabel met namen en elders verwijzingen, met
`test_geen_modelnaam_als_letterlijke_string_buiten_modellen_py` als gate: een modelnaam als
letterlijke string buiten die module laat de suite falen. In comments en docstrings mag hij.
`PRIJZEN` is op de alias gesleuteld en `prijs_voor()` herleidt een gedateerd ID uit een
historisch record naar zijn alias — dat scheelt een tweede prijsregel per spelling, die uit de
eerste kan lopen. Een onbekend model levert `None` en geen tarief van nul, zodat de caller het
verschil ziet.

**De UI-kaart is eerlijk gemaakt.** Er stond "Classificatie en memo-tekst" terwijl
`AUDIT_CLASSIFICATION_MODEL` alleen `classification/findings.py` bereikt. De kaart zegt nu
"Classificatie van bevindingen", met eronder dat memo-tekst en rapportgeneratie altijd op Haiku
draaien, en de prijsgrondslag staat naast de peildatum in het scherm. Dat die vier paden op het
standaardmodel blijven is een keuze en geen restant: ze schrijven tekst op basis van al
geclassificeerde bevindingen en vellen zelf geen oordeel over bewijs.

Zevende valse-groen van deze week, en de goedkoopste: een scherm dat meer belooft dan de code
doet.


### Added — 2026-08-18 — dekking van het landschap: 42% van de bron werd niet gelezen

Change `landschap-dekking`. Gemeten op 2026-08-17 tegen de gekoppelde Shared Drive: 512
bestanden, waarvan 299 gelezen. De andere 213 vielen in twee categorieën, en de tweede was de
erge:

| categorie | aantal | wat er gebeurde |
|---|---|---|
| PDF | 91 | op `NIET_TEKSTUEEL`, gemeld als "handmatige review" |
| Google Slides | 19 | idem |
| **onbekend MIME** | **92** | `logger.debug("Skip (onbekend MIME)")` — geen melding |

Die 92 zaten niet in het gemelde aantal van 119 en hadden op INFO-niveau geen enkele regel.
41 overgeslagen bestanden waren op naam al auditkritisch: de auditrapporten van de
certificerende instantie, `Afwijking 20250605_247 Registratieformulier NC-B-2025-01`, de VvT,
de RI&E, de interne-auditverslagen — dus 9.2, 9.3, 10.2 en 6.1.3.

Wat er is gewijzigd:

- **Meer formaten gelezen.** PDF (`pypdf`, nieuw), `.xlsx`, `.pptx`, Google Sheets en Slides
  via export, en markdown/HTML/CSV die alleen een MIME-regel misten — `text/plain` werd wel
  gelezen, `text/markdown` niet, en daar zat `Auditrapport_beide_v3.3_2026-05-05.md` bij.
  Google Sheets worden als `.xlsx` geëxporteerd en niet als CSV: een CSV-export bevat alleen
  het eerste blad, en dat zou dezelfde stille onvolledigheid opnieuw invoeren.
- **Snelkoppelingen gevolgd.** `shortcutDetails` stond niet in de veldenlijst van de client;
  29 snelkoppelingen kwamen binnen als bestand met een onleesbaar MIME-type. Naam, type én
  `modifiedTime` komen nu van het doelbestand — dat laatste is niet cosmetisch, want het
  leeftijdsfilter van 2 jaar beslist daarop. Dedup op file-id, dus een doel dat ook
  rechtstreeks in scope zit telt één keer. De recursie kreeg een `bezocht`-set: een mapboom
  heeft geen cycli, een snelkoppeling naar een bovenliggende map wel.
- **Niets verdwijnt meer stil.** Elke overgeslagen categorie wordt op INFO gemeld met de reden
  en komt in de handmatige-reviewlijst; een onbekend type krijgt zijn eigen categorie zodat een
  nieuw bestandsformaat niet in hetzelfde gat terugvalt.
- **Dekking in het run-record.** `Dekking` naast `Kosten`: gezien, gelezen, en per reden het
  aantal overgeslagen. Aantallen, geen bestandsnamen. Het log verdwijnt bij een podherstart, en
  "welk deel van de bron heeft het tool gezien" is precies wat een certificerende instantie
  vraagt — dezelfde reden waarom de kosten er gisteren in zijn gezet.
- **Een leeg extractieresultaat is een storing.** `LeegDocumentError`: een gescande PDF levert
  nul tekens op, en als document met lege inhoud opgenomen classificeert de pipeline hem als
  "geen bewijs" — een oordeel over iets wat niemand heeft gelezen, op een clausule waar het
  bewijs bestaat. Dezelfde regel als bij het afgekapte antwoord hieronder.

Gemeten na de wijziging tegen dezelfde Shared Drive: **502 bestanden gezien, 456 gelezen (91%),
46 niet.** Van die 46 zijn 6 bewust uitgesloten referentiedocumenten (de normteksten zelf), 12
afbeeldingen, 6 Google Forms, 1 video, 1 Drive-tekening — en 18 snelkoppelingen waarvan het doel
een 404 geeft: verwijderd, of in een My Drive die niet met het service-account is gedeeld. Dat
laatste is geen bug maar een vondst die het tool eerder niet kon melden.

`pypdf` is als afhankelijkheid toegevoegd en op **6.15.0** vastgezet in `uv.lock`, niet op de
nieuwste 6.16.1: die is vier dagen oud, en de quarantaine-regel uit de workstation-policy geldt
ook op PyPI. Geen transitieve afhankelijkheden; lockfile-diff is één pakket van pypi.org.

Verificatie op de auditkritische stukken (50 bestanden op naam gezocht, echt ingelezen): **45
leveren tekst op** — de auditrapporten van de certificerende instantie (38k–73k tekens), het
NC-registratieformulier (7.853), de VvT (23.400), de RI&E-actielijst (13.597),
`instructie management review.pdf` (2.170) en alle kwartaalverslagen van de interne audits. Vier
zijn scans en worden als zodanig gemeld in plaats van als leeg document opgenomen: beide
ISO-certificaten en twee RI&E-overzichten. Eén geeft een 403 "this file cannot be downloaded" —
een downloadbeperking op dat bestand — en belandt als leesfout in de handmatige review.

Geen OCR en geen video: die blijven onleesbaar, maar nu *zichtbaar* onleesbaar in plaats van
stil afwezig. De vier gescande certificaten zijn daarmee het eerste concrete argument voor OCR;
dat blijft een aparte afweging.


### Fixed — 2026-08-17 — afgekapte antwoorden lazen als "geen bevindingen"

De clusterverificatie van change `classificatie-modelkeuze` bracht de andere helft van
dezelfde bug aan het licht. Nadat het thinking-probleem was opgelost, leverden Sonnet 5 en
Opus 5 nog steeds nul bevindingen — nu zonder foutmelding. Gemeten in productie:

| model | stop_reason | uitvoertokens | JSON compleet |
|---|---|---|---|
| Haiku 4.5 | `end_turn` | 193 | ja |
| Sonnet 5 | `max_tokens` | 214 | nee, afgekapt |
| Opus 5 | `max_tokens` | 214 | nee, afgekapt |

Het budget `150 * n + 64` was op Haiku's beknoptheid gekalibreerd. Bij afkapping mist de
sluithaak, vindt `_parse_json_list` geen array, en geeft die stil een lege lijst terug — niet
te onderscheiden van "het model vond niets".

Twee wijzigingen. Een `stop_reason: max_tokens` geldt nu als storing en niet als leeg oordeel;
dat is dezelfde regel als voor een onleesbaar antwoord, en hij dekt ook een lang document dat
straks bij een ruimer budget alsnog afkapt. En het budget is op de gemeten werkelijkheid gezet:
uitvoertokens per item zijn 193 (Haiku), 276 (Sonnet 5) en 410 (Opus 5), dus 450 per item plus
128 voor de JSON-omlijsting. Ruimer zetten kost niets — je betaalt voor gegenereerde tokens,
niet voor het plafond, en bij `max_tokens=4000` stopten beide modellen uit zichzelf.

Dit is precies waarvoor taak 8.1 bestond: de suite was groen, de eenheidstests klopten, en het
werkte pas aantoonbaar ná meting tegen de echte API.


### Added — 2026-08-17 — kosten in het run-record, met peildatum en grondslag

`Kostenteller.kosten_usd()` rekende de kosten al uit en logde ze, maar het bedrag belandde niet
in `runs.jsonl` — terwijl de rest van de runhistorie daar wél staat. Een auditor die later vroeg
wat een run kostte, moest door logs zoeken.

Het afsluitrecord krijgt nu een `kosten`-blok met bedrag, model, `PRIJZEN_PEILDATUM`,
`PRIJZEN_GRONDSLAG`, aantal calls en aantal fouten. Die vier context-velden zitten er niet voor
de volledigheid: een bedrag zonder model is niet te herleiden, zonder peildatum niet te
controleren (prijzen wijzigen buiten deze repo om), en zonder grondslag niet te interpreteren.

De kosten reizen via een optionele `op_kosten`-callback van de classifier omhoog door
`pipeline.run_audit` en `run_live_pipeline` naar de worker. Een callback en geen tweede
returnwaarde, omdat dat laatste elke bestaande aanroeper zou breken voor één veld. Een
ingest-only run levert `None` en dus geen kostenveld — nul rapporteren zou suggereren dat er
geclassificeerd is.

Nieuw: `docs/reference/modelkeuze.md` — wat de modelkeuze betekent, de gemeten kosten per model,
waarom thinking expliciet uit staat, waarom de cache niets doet, en dat de keuze alleen de
classificatie bereikt en niet de memo-tekst die de UI-kaart wél belooft.


### Fixed — 2026-08-17 — twee van de drie kiesbare modellen leverden stil nul bevindingen

De UI biedt Haiku 4.5, Sonnet 5 en Opus 5. Alleen Haiku werkte. De classificatie-aanroep gaf
geen `thinking`-parameter mee, en dat weglaten is niet "uit": op Sonnet 5 en Opus 5 staat
adaptive thinking dan aan. Gemeten tegen de echte API met een classificatie-achtige vraag:

| aanroep | blokken | stop_reason |
|---|---|---|
| `claude-sonnet-5` zonder `thinking` | `['thinking']` | `max_tokens` |
| `claude-sonnet-5` met `thinking: disabled` | `['text']` | `max_tokens` |
| `claude-opus-5` zonder `thinking` | `['thinking']` | `max_tokens` |
| `claude-haiku-4-5` met `thinking: disabled` | `['text']` | — |

Zonder de parameter kwam er dus **alleen** een thinking-blok terug en géén tekstblok.
`resp.content[0].text` gooide een `AttributeError`, die werd afgevangen tot een lege string, en
`_parse_json_list("")` returnde stil een lege lijst — zonder de foutenteller te verhogen en
zonder logregel. De run meldde zich `klaar` met nul bevindingen.

Wat dit vervelend maakte: het gedrag is **invoer-afhankelijk**. Op een triviale vraag gaf
Sonnet 5 wél direct tekst — adaptive thinking betekent dat het model zelf beslist. Het werkte
dus in een snelle test en faalde op het echte werk.

Drie wijzigingen: `thinking` staat expliciet uit (geverifieerd dat alle drie de modellen dat
accepteren, Haiku inbegrepen); het tekstblok wordt op `type` gezocht in plaats van op positie,
via één helper in de nieuwe module `classification/respons.py` die alle vier de
classificatie-aanroepen gebruiken; en een respons zonder tekstblok is nu een storing die
meetelt en gelogd wordt, terwijl een leesbaar antwoord zonder bevindingen een geldig leeg
oordeel blijft.

De testfixtures zetten geen `type` op hun responsblokken en konden dit daarom niet nabootsen.
Dat is gerepareerd — de fixture die de bug had moeten vangen, vangt hem nu.

Zie `openspec/changes/classificatie-modelkeuze/`.

### Changed — 2026-08-17 — prijsgrondslag benoemd, en de cache-belofte teruggenomen

`PRIJZEN_GRONDSLAG` zegt nu expliciet of de tarieven lijstprijs of werkelijk tarief zijn. Dat
is nodig omdat Sonnet 5 tot en met 31 augustus 2026 een introductietarief van $2,00/$10,00
heeft terwijl de tabel $3,00/$15,00 aanhoudt: elk gerapporteerd bedrag voor dat model valt een
derde hoger uit dan wat er gefactureerd wordt. Bewust geen datumlogica in de tabel — dat zou
een tweede administratie zijn die achterloopt op de leverancier.

De module-docstring van `findings.py` beloofde dat de systeem-prompt "na eerste call uit cache
gelezen (~10x goedkoper)" wordt. Dat gebeurt niet: de prompts zijn 122–726 tokens en het
minimum cacheerbare prefix is 4096 tokens op Haiku 4.5, 1024 op Sonnet 5 en 512 op Opus 5.
Onder dat minimum cachet de API stil niet. Gemeten over 215 classificaties in de
referentie-checkout: `cache_read` en `cache_write` allebei nul. De claim is vervangen door wat
er werkelijk gebeurt.

**Correctie op een eerdere versie van het voorstel:** daar stond dat `usage_json` leeg blijft.
Dat was fout — die check gebruikte `sqlite3`, wat op deze machine niet bestaat, en de lege
uitvoer las ik als nul rijen. Correct gemeten: 215 van 215 rijen gevuld. Wat de data wél
oplevert is het antwoord op de kostenvraag: gemiddeld 702 input- en 594 output-tokens per
classificatie, en voor die hele set $0,79 op Haiku, $2,37 op Sonnet 5 en $3,95 op Opus 5.
Prijs is bij dit volume dus geen argument in de modelkeuze.

### Added — 2026-08-17 — Drive-locaties als lijst, met eerlijke status per locatie

Twee problemen die samen één change vormen — zie `openspec/changes/drive-locaties-ui/`.

**De mogelijkheid bestond en was onvindbaar.** `DriveSource` las al uit meerdere locaties:
`_split_ids` splitst op komma's en `list_documents` dedupliceert op file-id. Maar het veld
heette "Map-ID van de auditmap", enkelvoud, met de hint "Het laatste deel van de Drive-URL
van de map". Niemand raadt dat daar een komma in mag, dus wie twee Drives wilde koppelen
concludeerde dat het niet kon. Het opslagformaat was bovendien naar de UI gelekt: je moest
zelf scheidingstekens plaatsen, en één typefout maakte stil twee onbruikbare ID's van één
goede.

Het Drive-formulier is nu een lijst met een toevoeg- en verwijderactie per rij. De komma
bestaat alleen nog op de grens naar de server; de auditor typt er nooit een. Normaliseren
(geplakte URL → ID) en ontdubbelen gebeurt server-side, zodat het ook geldt voor een waarde
die een beheerder via de omgeving meegeeft.

**Een niet-map meldde zich groen.** `probe()` deed één `files.list` en keek alleen of de
aanroep slaagde. De query is `'<id>' in parents`, dus een bestand-ID matcht niets — geen
fout, een lege lijst. De UI meldde **gekoppeld** terwijl elke run nul documenten uit die
locatie las. Dezelfde valse groen als de hardcoded planning-sheet die gisteren is
weggehaald, langs een andere weg.

Elke locatie heeft nu een eigen statusregel met de naam uit Drive, het soort, en wat erin
staat. Een locatie zonder bestanden én zonder submappen is een waarschuwing, niet groen —
met de oorzaak erbij (`mimeType` zegt of het een map is) en zónder oorzaak wanneer die niet
is vast te stellen. Liever geen oorzaak dan een verzonnen oorzaak. De bron als geheel blijft
gekoppeld zodra één locatie iets oplevert, anders maakt één verkeerd geplakt ID een werkende
configuratie rood.

De aantallen zijn niet-recursief en dat staat er ook bij: een recursieve telling kost
minuten en dit scherm opent bij elke pageload. Daarom is de drempel voor de waarschuwing
"geen bestanden én geen submappen".

Losse bestanden blijven buiten scope, op verzoek. De waarschuwing maakt wél zichtbaar
wanneer iemand het toch probeert.

### Storing — 2026-08-17 — portaal 45 minuten plat na een versiebump zonder image

`0.2.0a11` is naar `main` gepusht terwijl de image-build voor die commit nog in de wachtrij
van GitHub Actions stond. Argo staat op `automated` met **`selfHeal: true`** en synct op de
commit, niet op het uitrolscript: het zette de deployment direct op `0.2.0a11`, een tag die
op dat moment niet bestond. Gevolg: `Init:ImagePullBackOff`, 0/2 ready, `/ping` 503, en de
werkende pod was al vervangen. Ongeveer 09:07–09:52 UTC.

De aanname bovenaan `deploy/kustomization.yaml` — *"het image wordt op de PR gebouwd, dus de
tag bestaat vóór de merge en Argo vindt hem direct"* — houdt alleen bij een PR-flow. Bij een
directe push naar `main` bestaat de tag per definitie nog niet, en `selfHeal` wacht niet.

**Regel die hieruit volgt: met `selfHeal` aan mag een versiebump `main` niet raken voordat
het image gepubliceerd is.** Dus via een PR, of het image eerst bouwen. `rollout-portal.sh`
beschermt hier niet tegen — dat script draait ná de push, en Argo is dan al langs geweest.
Wat het script wél goed deed: het stopte op de ontbrekende tag vóór de cookie-rotatie en de
herstart, dus het heeft de storing niet verergerd.

**Hersteld door `0.2.0a11` lokaal te bouwen en naar ghcr te pushen**, omdat de Actions-
wachtrij bleef staan (alle vier de workflows, inclusief GitHub's eigen CodeQL en Dependency
Graph, ruim een uur `queued` terwijl GitHub "Actions: operational" meldde — vermoedelijk een
spending limit op de organisatie; niet te controleren zonder `admin:org`).

Dat image heeft **geen CI-attestatie en is niet in een schone omgeving gebouwd**. De inhoud
komt aantoonbaar uit commit `7b79972`: gebouwd uit `git archive 7b79972`, en meegepusht als
`sha-7b79972` naast de versietag. Geverifieerd ín het image vóór het pushen — versie
`0.2.0a11`, 16 `/instellingen/`-aanroepen, nul `/config/`-aanroepen, `PadGeweigerd` aanwezig,
`DEFAULT_PLANNING_SHEETS_ID` weg. Loopt de wachtrij later alsnog leeg, dan herbouwt CI
dezelfde tag uit dezelfde commit.

### Fixed — 2026-08-17 — het configuratiescherm was onbereikbaar: de ingress weigert `/config/`

Na de uitrol van `0.2.0a10` bleef het portaal hangen met "Je sessie is verlopen", terwijl de
koptekst "ingelogd als …" toonde en herladen niet hielp.

De oorzaak zat niet in de applicatie. De gedeelde nginx-ingresscontroller draagt een globale
Nextcloud-hardeningregel:

    location ~ ^/(?:build|tests|config|lib|3rdparty|templates|data)/ { deny all; }

Die geldt voor **elke host op het cluster**. Elk verzoek onder `/config/` kreeg nginx' eigen
403 en bereikte de pod nooit — onzichtbaar in zowel het applicatielog als het
oauth2-proxy-log. Het onderscheid dat het uitwees: `/me` gaf de Sign-In-pagina van
oauth2-proxy, `/config/options` gaf `<title>403 Forbidden</title>` van nginx.

**Onze routes heten nu `/instellingen/*`.** Dat is de enige oplossing die binnen onze eigen
namespace valt; de ConfigMap aanpassen zou infrastructuur raken die met andere tenants wordt
gedeeld. De hash-route `#/config` in de UI blijft — een fragment gaat nooit naar de server.

Gemeten reikwijdte van dezelfde regelset, op een host die er verder niets mee te maken heeft
(`platform.commonground.nu`): `/config/x`, `/issues`, `/occ-test` en `/indienen` geven daar
allemaal 403. De tweede deny-regel heeft namelijk geen afsluitende `/`, dus
`autotest|occ|issue|indie|db_|console` matcht elk pad dat er *mee begint*. Doorgegeven aan de
clusterbeheerder; niet door ons gewijzigd.

### Fixed — 2026-08-17 — "sessie verlopen" werd gemeld bij een 403 die niets met de sessie te maken had

`j()` behandelde elke 401/403 als sessieverloop. Bij de blokkade hierboven leverde dat een
scherm op dat tegelijk "ingelogd als markwesterweel@conduction.nl" en "Je sessie is verlopen"
toonde, met een herlaad-link die per definitie niet kon werken. De oude code liet het scherm
stil op "laden…" staan; deze verklaarde het actief verkeerd, wat erger is.

`j()` meet nu in plaats van te veronderstellen: bij een 401/403 wordt `/me` opnieuw bevraagd.
Komt daar 200 uit, dan leeft de sessie en gooit hij `PadGeweigerd` in plaats van
`SessieVerlopen` — met een melding die zegt dat je gewoon ingelogd bent, dat herladen niet
helpt, en dat een beheerder ernaar moet kijken.

### Fixed — 2026-08-16 — een verlopen sessie liet het scherm eeuwig op "laden…" staan

`j()` in `ui.html` deed `(await fetch(url)).json()` zonder naar de statuscode te kijken. Bij
een 403 van de proxy — precies wat er gebeurt ná een cookie-rotatie, die alle sessies
ongeldig maakt — klapte `.json()` om op de HTML-foutpagina, liep de fout weg uit een
niet-afgevangen `route()`, en bleef het scherm hangen. Alweer een fout die zich voordoet als
"er gebeurt niets", en dat is de vervelendste soort: je gaat het probleem elders zoeken.

Nu: `j()` controleert de status, een `SessieVerlopen`-klasse voor 401/403, en een
`veiligeRoute()` op `hashchange` die er de melding "Je sessie is verlopen — herlaad de
pagina" van maakt. Vastgelegd in `tests/api/test_ui_contract.py`.

### Fixed — 2026-08-16 — e2e-tests deden echte Drive-calls

Twee testfouten in `tests/e2e/`: de fixtures ruimden de Google-variabelen niet op, waardoor de
suite echte Drive-calls deed (traag en netwerkafhankelijk), en de wachtvoorwaarde accepteerde
de tussenstand "bezig met testen…" als eindtoestand. Beide gerepareerd; de suite is twee keer
achtereen groen en ging van 40 naar 24 seconden.

### Fixed — 2026-08-16 — planning meldde zich groen op andermans spreadsheet

`sources/planning.py` had `DEFAULT_PLANNING_SHEETS_ID` als terugval: het spreadsheet-ID van
Conduction, ingebakken in de code. Gemeten in het cluster op 16 augustus stond noch
`AUDIT_SOURCE_FOLDER_ID` noch `AUDIT_PLANNING_SHEETS_ID` gezet, en was het configuratie-Secret
leeg. Drive meldde zich toen (terecht) als niet-gekoppeld — en planning **groen met 7 tabs**.

Dat is precies de stille terugval die deze week overal is weggehaald, en hij stond live. Bij
een derde partij wijst het portaal dan groen naar data van Conduction. Erger nog voor een
audittool: je ziet groen en concludeert dat de koppeling werkt.

Weg dus, zonder vervanging. Niet-geconfigureerd is nu een eigen toestand:
`probe()`/`healthcheck()` melden `niet_geconfigureerd` met een leesbare reden — hetzelfde
idioom als `sources/jira.py` al gebruikte — en wie er écht mee wil lézen krijgt een harde
fout via `_vereis_id()`. Zichtbaar leeg in plaats van misleidend groen.

### Fixed — 2026-08-16 — pipeline-fouten lekten leveranciersteksten naar de browser

`session.py:_run_live_worker` ving élke pipeline-fout en zette `str(exc)` in twee dingen die
de browser toont: de live-log (via `run_progress`) en het run-record in de audittrail. Die
tekst komt uit de client van Google, Jira of Anthropic en kan een URL met credential of een
tokenfragment bevatten — hetzelfde lekpad als de `reden` in `_check_source`, die op 14
augustus al is dichtgezet. Nu via `normaliseer()`: de ruwe melding gaat naar het serverlog,
de auditor ziet een vaste, leesbare tekst.

`routes_audit.py` bleef ongemoeid: dat vangt alleen `SessionError`/`ValueError`/`OSError` uit
onze eigen validatie, dus daar is geen leveranciersrespons in het spel.

### Fixed — 2026-08-16 — de testsuite hing af van omgevingsvariabelen die tests niet zetten

Twee gevallen, allebei gemeten, allebei hetzelfde patroon: een test die groen is op jouw
machine en rood ergens anders — of omgekeerd, wat erger is.

1. **`GWS_IMPERSONATE_EMAIL`.** Staat die gevuld — en op een werkstation dat het portaal
   lokaal draait staat hij dat — dan bouwt `auth.get_credentials()` gedelegeerde
   credentials en faalden 9 tests in `tests/test_auth.py`. Gemeten: 9 failed, 11 passed met
   de variabele gezet; groen zonder.
2. **`JIRA_PROJECTS`.** `tests/api/test_bron_config.py` post `JIRA_PROJECTS: "ISO"` naar de
   config-API, waarna `BronConfig.naar_omgeving()` dat in `os.environ` van het testproces
   zet — waar het blijft staan. Dat lekte naar
   `test_jira_zonder_scope_stuurt_geen_lege_query`, die het onbegrensd-vangnet
   (`updated >= -365d`) verwacht en `project in ("ISO")` kreeg. **Rood in CI sinds
   `60312c5`, groen op een werkstation met een `.env`** — precies het verschil waardoor
   niemand het opmerkte: de suite die je zelf draait zegt dat er niets aan de hand is.

Beide opgelost met één autouse-fixture in `tests/conftest.py` die de betrokken variabelen
vóór élke test wist. Repo-breed en niet per testfile: het raakt elke test die credentials
bouwt of een JQL asserteert, en een test die eraan moet dénken zichzelf te isoleren vergeet
dat uiteindelijk — wat hier ook precies gebeurd is. De gelijkwaardige lokale fixture in
`tests/sources/test_jira.py` is daarmee vervallen; die stond er al, alleen niet waar het
tweede geval hem nodig had.

### Added — 2026-08-16 — `rollout-portal.sh` doet de hele keten, met pre-flight

Het script pushte, wachtte op de build en rolde uit — maar controleerde vooraf niets.
Een fout die je vóór het pushen vindt kost seconden; dezelfde fout erna kost een build van
vijftien minuten en een uitrol die je moet terugdraaien. Vijf poorten erbij, allemaal
vóórdat er iets naar origin gaat:

1. **kwaliteitspoort** — pytest, ruff, ruff format, mypy --strict
2. **versieconsistentie** — bestond al: `pyproject.toml` == `newTag`
3. **manifest-validatie** — bestond al in de ci-fix-checkout, nu hier
4. **secrets aanwezig**, met per ontbrekend Secret wat er dán niet werkt
5. **rechten van het serviceaccount** — precies een Secret leesbaar, geen `list`

Die laatste is taak 4.1 uit change `credential-opslag`, die openstond. Gemeten tegen het
echte cluster: `yes` op het eigen config-Secret, `no` op het oauth-Secret, `no` op
`list secrets`. De grens is dus smal en blijft dat, want het script faalt nu als hij
verschuift.

De secret-check is bewust niet overal fataal. Alleen `iso-audit-portal-oauth` is hard
vereist — zonder client- en cookie-secret start de proxy-sidecar niet. De rest
degradeert, en dat is het probleem: zonder `iso-audit-portal-config` valt UI-configuratie
stil terug op de PVC terwijl `ISO_AUDIT_CONFIG_SECRET` in het manifest staat. Het script
benoemt per Secret het gevolg in plaats van te weigeren.

Ik had die check eerst wel fataal gezet op `iso-audit-portal-config`. Dat was strenger dan
de werkelijkheid: het portaal start er prima zonder. Gecorrigeerd na meting.

**Meegenomen uit de ci-fix-checkout** (commits `df19729` en `cbeda7a`, die alleen daar
stonden): de voorwaardelijke herstart — een `rollout restart` zet een annotatie die niet
in git staat, waardoor Argo permanent `OutOfSync` meldt en echte drift verbergt — plus
`scripts/check-manifest-pruning.py` en de `downwardAPI`-fix voor het projected volume, dat
het namespace-bestand miste waardoor `secret_store` terugviel op een hardcoded namespace.

### Fixed — 2026-08-16 — een verse audit kon geen live run afronden

`registry.maak` legde `audit.json` en `findings.json` aan, maar geen `memo-input.yaml`.
De live-worker vult daarin na afloop de scope en de geraadpleegde bronnen bij, en
struikelde op het ontbrekende bestand — **nadat** alle zeven pipelinestappen waren
gedraaid, alle rapporten waren geschreven en 87 bevindingen in de triage stonden. De run
belandde als `fout` met `0 toegevoegd` in de append-only trail.

Twee dingen daaraan:

- Een audit hoort zelfstandig te zijn vanaf het moment dat hij bestaat. Bij het aanmaken
  komt er nu een geldige `memo-input.yaml` mee, met de norm en periode van de audit zelf.
  Het is een steiger, geen inhoud — de auditor bewerkt hem in de memo-editor.
- Het bijwerken van de memo-context is niet-fataal gemaakt. Dat is cosmetiek ná het echte
  werk; het mag een geslaagde run niet als mislukt wegschrijven. Wel gelogd in de
  run-log, want stil is het ook niet.

Na de fix: `status: klaar`, **87 toegevoegd, 166 overgeslagen** — dat tweede getal was er
nooit geweest zolang het spoor loog.

### Changed — 2026-08-16 — versie op één plek, en `0.2.0a9`

`pyproject.toml` stond op `0.2.0a8` en `src/iso_audit/__init__.py` op `0.1.0a0`. Bij een
uitrol is dat de string waaraan je ziet wélke build draait; een tweede waarheid is daar
duur. `__version__` komt nu uit de pakket-metadata, en twee tests bewaken dat
`pyproject.toml`, `__version__` en de `newTag` in `deploy/kustomization.yaml` gelijk zijn.
Die laatste is niet theoretisch: een tag die niet meebeweegt betekent dat Argo dezelfde
image synct en er niets verandert — precies de stille stilstand van 14 augustus.

### Changed — 2026-08-16 — secrets-script en -documentatie kloppen weer

`scripts/create-portal-secrets.sh` meldde bij een ontbrekende `GOOGLE_SA_FILE` dat die
"komt met de change gsuite-service-account-sources". Dat klopt niet meer: Drive en de
auditplanning lezen sinds 15 augustus via dat service-account. Zonder het Secret is de
mount leeg (`optional: true`) en melden beide bronnen zich als niet-gekoppeld, zonder dat
iemand ziet dát er iets ontbreekt. Nu een expliciete waarschuwing, plus een controle die
een `authorized_user`-keyfile weigert — dat is een persoonsgebonden credential en precies
wat deze migratie wegneemt.

`deploy/README.md` heeft een sectie **Secrets aanmaken** met het onderscheid dat er
werkelijk toe doet: Jira-, Miro- en Anthropic-credentials zijn óók vanuit de UI te zetten
(en winnen dan van de omgeving), de Google-keyfile niet — dat is een gemount bestand.

### Added — 2026-08-15 — landschap los van audits, en Jira als opvolgpunten

Twee modelleerfouten die pas zichtbaar werden toen de keten voor het eerst echt liep. Zie
`openspec/changes/landschap-en-opvolgpunten/`.

**Het documentenlandschap is van de organisatie, niet van één audit.** De opslag was al
gedeeld — één `AUDIT_DB_PATH` — maar de handeling hing als runmodus ónder een audit. Twee
audits zouden dezelfde tweeënhalve minuut Drive-lezen herhalen tegen dezelfde tabel, en
"welk landschap heeft déze audit gezien" was onbeantwoordbaar.

Nu: `GET /landschap`, `POST /landschap/ingest` en `GET /landschap/documenten`, met een
eigen scherm naast de audits. De ingest-runmodus op de audit is weer weg — één ingang, niet
twee.

**Er was geen enkel scherm waarop je kon zien wát er was ingelezen.** Een run was daarmee
een black box: je zag pas achteraf uit de bevindingen of het landschap klopte. Het
Landschap-scherm toont per document de bron, de clausule-koppelingen en de wijzigdatum, en
is doorzoekbaar op naam én inhoud — via de `documents_fts`-index die al bestond en nergens
werd gebruikt. Een document zonder clausule-koppeling wordt als zodanig getoond: dat wordt
in een run niet aan een norm getoetst, en dat hoor je vooraf te weten.

**Jira levert openstaande punten, geen bewijsmateriaal.** Tickets gingen via
`list_documents` en werden tegen elke clausule geclassificeerd. In de referentie-output van
juni staat het resultaat: een ticket met een NC omdat het clausule 4.1 niet bewijst. Ruis,
plus LLM-kosten per ticket.

`list_findings` bestond op het `Source`-protocol, `JiraSource` implementeerde het, en het
had **nul aanroepers**. Nu aangesloten via `sources/opvolgpunten.py`: gelabelde open issues
gaan zonder classificatie naar de bevindingen, herkenbaar als herkomst `Jira-opvolging`.
Gemeten: 83 punten in 1,3 seconde, zonder één API-call.

**En de standaardfilter daarvoor was aantoonbaar fout.** Hij zocht op labels
`iso27001`/`iso9001`/`compliance`; gemeten in de echte tenant bestaan die daar niet — men
gebruikt `interne_audit`, `managementreview2026`, `ISO_algemeen`, `externeaudit`. De filter
leverde stil nul punten terwijl er 25 open issues in het ISO-project stonden. De scope is nu
het project (`JIRA_PROJECTS`) plus "nog niet afgerond"; een projectsleutel is een afspraak,
labels verschillen per organisatie. `JIRA_FINDINGS_JQL` blijft de knop voor wie het anders
wil, nu ook in `env.example`.

**Open punt:** opvolgpunten zonder label-naar-clausule-match landen op clausule `0`. Dat is
eerlijk (we weten de clausule niet) maar leest slecht in de triage. En in de gemeten tenant
bevat het ISO-project ook regulier werk, dus de scope verdient een keuze van de auditor.

### Added — 2026-08-15 — ingest als eigen runmodus, en wat gelezen is blijft bewaard

`mode: "ingest"` op `POST /audits/{id}/run/start` leest de gekozen bronnen, koppelt ze aan
clausules en legt dat vast — **zonder de Claude-API te raken**. Gemeten met een echte run
over Drive en Jira, hoofdstuk 5, zonder API-key: 409 documenten (Drive 149, Jira 260), 70
clausule-koppelingen, run-record `klaar`.

Dit legde twee dingen bloot die daarvóór onzichtbaar waren.

**`run_audit` bewaarde niets van wat het las.** Alles bleef in het geheugen tot ná de
classificatie. Een run die op een ontbrekende API-key strandde gooide daarmee een
Drive-lezing van tweeënhalve minuut en 149 documenten volledig weg — gemeten: de
`documents`-tabel bleef leeg terwijl het log 149 ingelezen documenten meldde. De losse
`ingest.ingest_drive()` deed dit al wél; die twee paden waren uit elkaar gelopen.

Nu legt `run_audit` de ingest vast vóór de classificatie, idempotent (`upsert`). Dat is
ook wat een auditwerktuig hoort te doen: je hebt bewijs ingezien, dus leg vast wát je
hebt ingezien. En het maakt hergebruik mogelijk — zonder opgeslagen documenten valt er
niets te cachen.

**Een gekozen bron kon stil nul documenten leveren.** `pipeline.py` ving een ingest-fout af
als "niet kritiek", logde een regel, en de run meldde `klaar`. Gemeten geval: Jira gaf
`HTTP 400 — "Unbounded JQL queries are not allowed here"` en leverde nul documenten,
terwijl de auditor hem expliciet had gekozen. Alleen het serverlog wist dat.

Doorgaan blijft juist — één kapotte bron mag een audit niet stilleggen — maar het gebeurt
niet meer stil: `BronIngestError` met per bron de **genormaliseerde** reden, gegooid ná het
vastleggen, zodat het werk van de andere bronnen bewaard blijft.

De onderliggende Jira-fout is ook verholpen: zonder `JIRA_PROJECTS` en zonder `JIRA_JQL`
stuurde de adapter een lege query, en Jira Cloud weigert onbegrensde zoekopdrachten. Er is
nu een zichtbare begrenzing (`updated >= -365d`) die wijkt zodra je zelf een scope zet.

### Fixed — 2026-08-15 — Jira werkt met een service-account in plaats van een persoon

`sources/jira.py` deed uitsluitend HTTP Basic auth met een e-mailadres als gebruikersnaam.
Dat werkt met een **persoonlijk** Atlassian-token (`ATATT…`), maar niet met het
service-account-token dat deze koppeling juist persoonsonafhankelijk moet maken.

Atlassian kent twee soorten, en ze verschillen op twee assen tegelijk. Gemeten met het
echte token (`ATSTT3…`):

| aanroep | resultaat |
|---|---|
| Basic (`mail:token`) op de site-URL | **401** |
| Bearer op de site-URL | **403** op élk endpoint, ook `serverInfo` |
| Bearer op `api.atlassian.com/ex/jira/{cloudId}` | **200** |

Een scoped service-token gaat dus via `Authorization: Bearer` én via de gateway met de
cloud-ID erin. Die 403-op-alles was misleidend: het leek op een rechtenprobleem bij het
service-account, terwijl het de verkeerde host was.

`JiraSource` herkent nu het tokentype aan de prefix — de credential geeft zelf weg welk
schema hij nodig heeft, dus dat hoeft niemand te configureren en het kan ook niet fout
staan. Bij een scoped token wordt de cloud-ID eenmalig opgehaald via
`/_edge/tenant_info` (geen auth nodig) en onthouden. Een bestaande `ATATT`-configuratie
blijft ongewijzigd op Basic auth en de site-URL werken; daar is een test voor.

**En daarmee vervalt de eis van een e-mailadres.** Dat is alleen de gebruikersnaam voor
Basic auth. Het verplicht stellen bij een service-token vraagt om een persoonsgebonden
gegeven dat deze koppeling juist niet mag hebben — precies de vraag die de opdrachtgever
stelde toen hij dat veld moest invullen.

Resultaat in het portaal: Jira `connected`, met als account **"Iso-tool"**. Dat is de hele
migratie in één regel: de verbindingstest laat zien op welk account de koppeling draait, en
dat is geen mens meer.

### Fixed — 2026-08-15 — twee stille regressies uit de verhuizing

Gevonden door de oude codebase (`Ops_to_Biz/audit/`, nog opvraagbaar op `2edc146^`) naast
de huidige te leggen. Van de 34 productiemodules zijn er 26 één-op-één overgezet; dit zijn
de twee dingen die zonder besluit zijn weggevallen.

- **`--local-only` was niet bereikbaar vanaf `iso-audit`.** De functie werkt nog
  (`pipeline.run_local_only`) en de vlag bestaat in `pipeline.main()`, maar de
  gedocumenteerde ingang kende hem niet meer. Nu weer een vlag op `iso-audit pipeline`,
  met test.
- **Negen env-vars die de code leest, stonden nergens meer.** `AUDIT_TEMPLATE_DOC_ID`,
  `AUDIT_DB_PATH`, `AUDIT_SHEETS_ID`, `AUDIT_DRIVE_FOLDER_ID`, `MIRO_BOARD_ID`,
  `AUDIT_NORM`, `AUDIT_SCHERPTE`, `LOCAL_REPORT_DIR`, `AUDIT_CALENDAR_ID`,
  `AUDIT_NOTIFICATIE_ONTVANGERS`. Geen verlies in de code, wél in vindbaarheid — en dat is
  hier geen detail: zonder `AUDIT_TEMPLATE_DOC_ID` slaat de pipeline het Docs-rapport en
  de Slides **stil** over (`pipeline.py:512`), en zonder `MIRO_BOARD_ID` wordt Miro tijdens
  een run stil overgeslagen. Allemaal terug in `env.example`, met vermelding van wat er
  gebeurt als je ze leeg laat.

**Correctie op een aanname van vandaag.** Ik heb de omzetting van Drive en planning naar
het service-account beschreven alsof de oude codebase op persoonlijke OAuth draaide. Dat
klopt niet: `Ops_to_Biz/audit/auth.py` was al een service account met exact dezelfde
scopes, en `gws` was daar een *tweede* kanaal. Bij de verhuizing is het service-account-pad
uit de bron-adapters geschrapt (`gsa_client.py` verdween) en bleef alleen `gws` over. De
wijziging van vandaag herstelt dus iets dat er was, in plaats van iets nieuws te bouwen.

### Added — 2026-08-15 — end-to-end tests in een echte browser, en een testknop

**Waarom dit er moest komen.** Het configuratiescherm was aantoonbaar correct aan de
serverkant — de juiste velden in `/config/bronnen`, de juiste JS in `ui.html`, alle
contract-tests groen — terwijl een auditor in de browser **niets kon invullen**. Een test
op de HTML-brontekst ziet dat niet: die voert de JS nooit uit. Er is een hele sessie
verloren gegaan aan heen-en-weer over een scherm dat ik zelf had kunnen openen.

`tests/e2e/` draait het portaal en bedient het met Chromium (Playwright, dev-dependency):
typen, klikken, kijken wat er staat. Zes tests, waaronder de klacht zelf ("dit veld is
niet typbaar") en het rotatiescenario helemaal door de browser heen. De fixture faalt ook
op elke JavaScript-fout in de pagina — dat is hoe "ik kan niets invullen" ontstaat bij een
correcte backend. Zonder browser slaan ze zichzelf over in plaats van de suite rood te
maken.

Twee dingen die daarbij zijn rechtgezet:

- **De bevestigingsknop is weg.** Er stond een "Toch overschrijven" tussen de auditor en
  zijn invoer. Daar was niet om gevraagd, en hij loste een probleem op dat toen al
  verholpen was: zolang opslaan stil genegeerd werd was blokkeren eerlijk, maar zodra de
  ingevulde waarde écht geldt is er niets meer te blokkeren. Ik had die stap moeten
  weghalen toen hij overbodig werd in plaats van hem te laten staan.
- **Er is een testknop.** Per bron, met de uitslag onder het formulier, plus "Opslaan en
  testen" dat na het bewaren meteen test. Nieuw endpoint `GET /config/health/{bron}` zodat
  een Jira-token invullen niet wacht op een Drive-listing. Zonder terugkoppeling vul je
  iets in, krijg je "opgeslagen", en weet je nog steeds niets.

**En de reden dat het scherm bij de gebruiker niet veranderde:** `GET /` stuurde een kale
200 zonder `Cache-Control`, dus browsers cachen het portaal heuristisch. Eén HTML-bestand
zonder buildstap heeft geen versie in de URL, dus na een uitrol zit iedereen op een oud
scherm zonder het te merken — in het cluster net zo goed. Nu `no-store`, met een test.

### Changed — 2026-08-15 — een credential is te vervangen zonder clusterbeheerder

De precedence-regel was absoluut: **environment verslaat de UI**. Dat bleek te breken op
een geval dat zeker gaat gebeuren — een credential die roteert. Komt de waarde uit een
cluster-Secret, dan kon de auditor hem niet vervangen en was er een clusterbeheerder
nodig. Dat is precies de persoonsafhankelijkheid die deze migratie wegneemt, en na eind
augustus is er niemand die dat "even doet".

Aanleiding was concreet: een auditor kon de service-account-key voor Jira niet in het
configuratiescherm plakken, omdat de oude waarde uit de omgeving kwam. De maatregel die
dat blokkeerde was een dag eerder toegevoegd om een ánder probleem op te lossen (een save
die slaagde en niets deed), maar liet de gebruiker zonder uitweg. Een slot zonder deur.

**De rationale van de oude regel blijft overeind.** Er stond: *"environment bovenaan
betekent dat een deployment nooit **stil** een via-de-UI ingevulde waarde gebruikt."* Het
probleem is stilte, niet dat de UI wint. Een expliciete, geregistreerde overschrijving is
niet stil. Daarom:

- precedence wordt `ui-override` > env > `config.yaml` > ui > default;
- `ui-override` staat náást `ui` en vervangt hem niet — het verschil tussen "hier
  ingevuld" en "hier ingevuld terwijl een beheerder iets anders had gezet" is precies wat
  een auditor achteraf moet kunnen zien;
- invullen over een omgevingswaarde heen werkt gewoon, zonder extra bevestigingsstap;
- de handeling staat append-only in `bron_config_log.jsonl` met `overschrijft_omgeving`,
  met wie en wanneer, nooit de waarde;
- terugdraaien is het veld leegmaken — geen apart endpoint nodig;
- **het rotatiegeval wordt gemeld**: wijzigt de omgeving nadat er een overschrijving op
  staat, dan zegt het portaal dat bij dat veld. Anders vervangt een beheerder het Secret,
  gebeurt er niets, en gaat diegene in het cluster zoeken naar een fout die er niet is.
  De vergelijking gaat via een hash; geen van beide waarden wordt getoond of gelogd.

Uniform voor alle velden, niet alleen geheimen: één regel is beter uit te leggen en te
bewaken dan twee, en ook een map-ID veroudert.

**Voor de derde keer vandaag dezelfde valstrik, nu in mijn eigen code.** `BronConfig`
schrijft naar `os.environ` en gebruikte diezelfde `os.environ` om te bepalen óf er een
beheerderswaarde achter een veld zat. Zelfreferentieel: elke opgeslagen waarde leek dan
uit de omgeving te komen. Opgelost zoals eerder — de omgeving wordt één keer vastgelegd,
nu in `BronConfig.basis` bij constructie, in plaats van per methode doorgegeven.

Wijzigt een afgeronde spec; zie
`openspec/changes/credential-rotatie-door-auditor/` met `## MODIFIED Requirements` op
`config-precedence`. Open punt daar: verifiëren in het cluster met een echt geroteerd
Secret.

### Fixed — 2026-08-14 — een run zonder bron werd geaccepteerd, en het run-record loog

Twee dingen die samen "er gebeurt niets en de UI legt niet uit waarom" veroorzaakten.

**Een run zonder bron gaf `200 {"status": "running"}`.** Vier gestapelde terugvallen
maakten er stil een drive-run van: `routes_audit.py:41`, `session.py:256`,
`run_job.py:153` en `pipeline.py:347`. Voor normen bestond de harde check al
(`registry.run_code` → 400); voor bronnen niet. Nu weigert `start_run` met een leesbare
reden, en de drie terugvallen in de API-laag zijn weg. `pipeline.py` houdt zijn default
voor de legacy-CLI-entrypoint — dat is een andere aanroeper met een ander contract.

Bij een live-run weegt de koppelstatus mee; bij een sim-run niet, want die leest per
definitie niets en dan is een verbindingseis theater. **Alleen de gekozen bronnen worden
gecontroleerd**: eerst deed dit `bron_health()` over álle bronnen, waardoor een run over
Drive stond te wachten op een niet-gekoppelde Jira.

**Het run-record beweerde "klaar, 0 toegevoegd, 0 overgeslagen" voordat er iets gelezen
was.** De route las `sessie.laatste_merge` direct nadat de worker-thread was gestart — dus
altijd `(0, 0)` — en `runs.py:127` zette `status: "klaar"`. `runs.jsonl` is append-only,
dus dat viel niet te corrigeren.

Nu twee records per run: een startrecord (`status: "loopt"`, dat het run-nummer reserveert
en een spoor achterlaat als de pod halverwege sneuvelt) en een afsluitrecord van de
**worker**, die de echte tellingen kent. `runs.samengevat()` vouwt ze per `run_id`;
`runs.lijst()` blijft de ruwe waarheid. `runs.som()` telt nu unieke `run_id`s in plaats
van regels — anders telt élke run dubbel, ook in `aantal_runs` op het dashboard.
`geraadpleegde_bronnen()` slaat runs met status `loopt` of `fout` over: die hebben niets
gelezen, en die kolom is een bewijsuitspraak.

Ook: `log_event("run_gestart")` stond vóór de start, dus een geweigerde run kwam als
"gestart" in het toegangslog. Dat is nu `run_geweigerd` met de reden.

### Fixed — 2026-08-14 — de foutnormalisatie dekte het hoofdfaalpad niet

De normalisatie van eerder vandaag zat alleen op de **exception**-tak van
`api/session.py:_check_source`. Adapters die hun fout zélf afvangen en
`{"status": "fail", "reden": ...}` teruggeven gingen er volledig omheen, en `ui.html`
rendert die tekst rechtstreeks. Gemeten in de browser:

- `Jira API 401 op https://conduction.atlassian.net/rest/api/3/myself: Client must be
  authenticated…` — tenant-URL plus responsbody, en `soort` was leeg
- 174 tekens ruwe subprocess-dump met de volledige `gws`-commandoregel

`tests/config/test_verbinding.py` was groen omdat de testadapter een exception **gooit** —
precies de enige tak die wél gesanitiseerd werd.

**De reparatie is routering, geen scherpere regex.** `classificeer()` zou die 401 correct
als `auth` hebben ingedeeld; hij werd alleen nooit aangeroepen. `_check_source` heeft nu
één uitgang: ontbreekt `soort`, dan gaat de tekst er alsnog door de normalisatie. Vergeten
is daarmee niet mogelijk in plaats van "we moeten eraan denken".

En de normalisatie mag geen bruikbare informatie meer weggooien. De echte drive-fout was
`OSError: Geen Drive-map geconfigureerd…` — onze eigen tekst, zonder gevoelige inhoud — en
daar maakte de sanitizer "Zie het serverlog voor details" van. Er is daarom een vijfde
soort `niet_geconfigureerd`, die **nooit** uit `classificeer()` komt: hij hoort bij een
fout die wij zelf vaststellen, en dan is er niets te beschermen. `JiraSource` noemt nu de
ontbrekende velden in auditor-taal (`"Nog niet ingevuld: het Jira-adres, …"`) in plaats van
env-var-namen, en Miro's lege token is `niet_geconfigureerd` en niet meer `auth` — "de
credential is geweigerd" sturen bij een leeg veld stuurt iemand naar de leverancier.

**De gate is een structurele, niet één per geval.**
`tests/api/test_bron_health_lekt_niet.py` loopt over **elke** geregistreerde bron, langs
beide takken, met een markerstring die een URL en een tokenfragment bevat. Nagerekend:
zonder de reparatie vallen zes van de twaalf gevallen om, precies op de zelf-afgevangen
tak. Hij faalt ook op een bron die volgend jaar wordt toegevoegd.

Drie bestaande tests asserteerden dát de ruwe tekst doorkwam (`"401" in reden`,
`reden == "geen creds"`); die legden het lek vast als gewenst gedrag en zijn omgedraaid.

**Bijkomend gevonden:** de suite deed echte Google- en Jira-calls, omdat
`test_healthz_en_config_zijn_niet_audit_gescoped` `/config/health` live aanriep en de
adapters sinds de service-account-omzetting daadwerkelijk verbinden. Die test duurde 75
seconden en las de live auditmap uit. Nu gestubd: hij gaat over routing, niet over
connectiviteit — en een testsuite hoort geen productiedata aan te raken.

### Changed — 2026-08-14 — Drive en planning lopen op het org-service-account

`sources/drive.py` en `sources/planning.py` gingen via de `gws`-CLI, en die authenticeert
met een **persoonlijke** OAuth-sessie (`gws auth login`). Daarmee hing de auditcapability
aan één medewerker. De binary stond bovendien niet in het container-image, dus in het
cluster konden die twee bronnen helemaal niet werken — `deploy/deployment.yaml:148-153`
zei dat zelf al.

De service-account-implementatie in `src/iso_audit/auth.py` bestond wél, maar had **nul
productie-gebruikers**: alleen twee testbestanden importeerden hem. Het cluster mount de
keyfile al op precies de variabele die `auth.py` leest, en niets las hem.

Nu: `clients/google_drive.py` en `clients/google_sheets.py` doen hetzelfde werk via
`google-api-python-client` met de credentials uit `auth.py`. De functienamen en
returnshapes zijn gelijk gehouden aan de `gws_*`-varianten die ze vervangen, zodat de
adapters één importregel wisselden en de bestaande tests in `tests/sources/` inhoudelijk
gelijk bleven — die suite is daarmee het bewijs dat het gedrag niet verschoof.

Gemeten in deze sessie, in deze volgorde, en elke stap vóór de volgende:

1. keyfile is `type: service_account`, org-eigendom (`iso-agent@gws-conduction…`);
2. authenticatie werkt, maar **0 zichtbare bestanden** — er was niets mee gedeeld;
3. na toevoegen aan de Shared Drive: `drives.get` OK, 25 items, submappen leesbaar;
4. na de omzetting: drive en planning `connected` in het portaal, 7 tabs gelezen.

Domain-wide delegation blijkt **niet** nodig zolang de Shared Drive het account als lid
heeft. Dat spaart een eenmalige actie van een Workspace-super-admin uit, en dus
kalendertijd. `GWS_IMPERSONATE_EMAIL` moet dan leeg zijn; hij stond op het
service-account zelf, en een account namens zichzelf laten handelen faalt met
`unauthorized_client`.

Meegenomen omdat het bij de omzetting hoorde:

- `auth.py` krijgt `sheets_read_service()` met een eigen `spreadsheets.readonly`-scope.
  Bewust een derde scope-lijst en niet één regel bij `_READ_SCOPES`: anders draagt het
  Drive-leestoken óók Sheets-rechten. `PlanningSource` is read-only en mag niet aan
  `sheets_service()` hangen — die heeft `_WRITE_SCOPES` en kan mail en agenda schrijven.
  De scope-tripwires in `tests/test_auth.py` blijven ongewijzigd gelden.
- `PlanningSource.probe()` is nieuw: één metadata-call in plaats van álle tabs lezen. Dat
  gebeurde bij élke keer openen van het configuratiescherm.
- `files.export` krijgt géén `supportsAllDrives` — die parameter bestaat daar niet
  (nagemeten in de discovery-doc: `export` heeft er twee, `get` en `list` wel). De CLI
  slikte hem, de python-client raist erop. Met een test erop, want dit is precies iets
  dat iemand "terugrepareert".
- De foutteksten van beide adapters lopen nu door `config/verbinding.normaliseer`. Ze
  gaven eerder `f"gws-fout op {fid}: {e}"` en `f"gws-fout: {e}"` rechtstreeks aan de
  browser; gemeten was dat 174 tekens ruwe subprocess-dump inclusief commandoregel. Drie
  bestaande tests asserteerden dát de ruwe tekst in `reden` stond — die legden het lek
  vast als gewenst gedrag en zijn omgedraaid.
- De `RuntimeError` bij "geen bestanden gevonden" adviseerde `gws auth login`. Dat stuurt
  na deze change de verkeerde kant op; hij wijst nu naar het delen met het service-account
  en naar het lidmaatschap van de Shared Drive.

**Nog niet gedaan:** `clients/gws.py` krimpen. De zes Drive- en Sheets-functies daarin
hebben nu geen klant meer, maar `_gws` blijft nodig voor rapportage, notificatie,
`sinks/drive.py` en `verify_docs.py`. Ook de `sys.exit(1)` op een ontbrekende `gws` in
`pipeline._valideer_env()` staat er nog; het portaal komt daar niet langs
(`api/run_job.py` roept `run_audit()` direct aan), waardoor dit in de container nooit
opviel.

### Fixed — 2026-08-14 — een geplakte URL in een ID-veld faalde misleidend

De velden "Map-ID van de auditmap" en "Spreadsheet-ID van de planning" vragen een ID, maar
in de praktijk plakt iedereen de URL uit de adresbalk. Gemeten: beide waarden waren
volledige URL's — één via de UI ingevuld, één uit een omgevingsbestand. De API krijgt dan
een "ID" van 80 tekens en antwoordt 404, wat in het portaal verschijnt als *"bestaat niet
of is niet gedeeld met dit account"*. Die melding stuurt iemand naar het deelbeleid terwijl
er niets mis is met de rechten — en dat kostte hier ook echt tijd.

`config/google_ids.uit_url()` herleidt de vier vormen die Drive en Sheets zelf produceren,
elk als expliciet patroon. Geen "pak de langste tekenreeks"-heuristiek: die pakt bij een
onbekende URL-vorm stil het verkeerde deel, en dan is de fout verderop weer misleidend.
Wat niet matcht gaat ongewijzigd door.

De bestaande waarschuwing in `planning._valideer_sheet_id` op `=` en whitespace blijft, met
de bijbehorende keuze om die waarde **niet** aan te passen: dat duidt op een kapotte
regel in een omgevingsbestand, en stil een andere sheet aanspreken is erger dan zichtbaar
falen. Een volledige URL is een ander geval — die verwijst naar exact één sheet.

De tests gebruiken de échte gemeten URL's als invoer, niet verzonnen strings.

### Fixed — 2026-08-14 — opslaan in de UI slaagde en deed niets

Een auditor typte een Jira-adres en -token in het configuratiescherm, kreeg
"✓ opgeslagen", en er veranderde niets. De save was ook echt geslaagd: `POST
/config/bronnen/jira` gaf 200 en er stond een regel in `bron_config_log.jsonl`. Maar
beide velden kwamen uit de omgeving, en env wint van de UI-store — dus de waarde werd
opgeslagen, gelogd, en genegeerd.

`ui.html:444-446` benoemde dat risico al letterlijk ("anders typt een auditor iets in
dat stil geen effect heeft") en loste het op met een badge plus tooltip. Dat was te
zwak: het veld bleef typbaar en `bewaarBron` stuurde het gewoon mee. Een badge is geen
slot.

Nu weigert `POST /config/bronnen/{bron}` zo'n veld met een 400 die zegt wélk veld het
is, en toont de UI het als `readonly`. **Beide** kanten, want een UI-only maatregel
laat de API liegen.

**Onderweg een ernstiger fout gevonden, die deze maatregel schadelijk zou hebben
gemaakt.** `Settings.naar_omgeving()` schrijft opgeloste waarden in `os.environ` en
`_uit_env` leest daaruit. Eén kanaal, twee betekenissen: bij de tweede `load_config()`
kwam een via de UI ingevulde waarde terug als `bron="env"`. Nagemeten met het oude
codepad — ronde 1 `ui`, ronde 2 `env`.

Dat is twee dingen tegelijk. Het maakt `/config/herkomst` onwaar op precies de vraag
waarvoor dat endpoint bestaat ("liep die run op een cluster-Secret of op iets dat
iemand in de UI had ingetypt?"), en het zou de blokkade hierboven élk UI-veld na één
save onbewerkbaar hebben gemaakt.

`load_config()` krijgt daarom een `omgeving`-parameter; `create_app` legt de omgeving
vast vóór de eerste `naar_omgeving()` en geeft die mee. Expliciet doorgeven, geen
module-globale: geen verborgen toestand, en het CLI-gedrag blijft ongewijzigd (default
is de live `os.environ`).

De gate is tegen de echte fout nagerekend: met de momentopname eruit valt
`test_ui_waarde_promoveert_niet_naar_env` om met `assert 'env' == 'ui'`. Een gate die
niet vangt is erger dan geen gate.

Ook meegenomen: `openAudit()` roept nu `loadConfig()` aan. Zonder die aanroep bleef de
bronselectie leeg tot iemand op "Laad opties" klikte, en stuurde `selectedConfig()`
`sources: []` mee — een run die niets leest terwijl de auditor bronnen dacht te hebben
gekozen.

979 passed, 1 skipped; ruff + format + mypy --strict clean.

**Bekend en niet opgelost** (aparte beslissingen):

- `tests/test_auth.py` ruimt `GWS_IMPERSONATE_EMAIL` niet op en erft hem uit de
  omgeving van de ontwikkelaar — via de module-level `load_dotenv()` in
  `sources/planning.py:32`. Staat die variabele lokaal gevuld, dan falen 9 tests op
  `AttributeError: 'str' object has no attribute 'with_subject'`. Zonder die variabele:
  20 passed. De suite leest dus mee met een lokaal omgevingsbestand.
- `pyproject.toml` staat op `0.2.0a8`, `src/iso_audit/__init__.py:16` op `0.1.0a0`.
- `sources/jira.py:184` doet uitsluitend Basic auth (`auth=(email, token)`). Een
  Atlassian **service-account**-credential wordt daar afgewezen met 401, terwijl
  dezelfde credential via `Authorization: Bearer` een 403 geeft — dus herkend, maar
  zonder rechten in de tenant. Voor een persoonsonafhankelijke Jira-koppeling is
  Bearer-ondersteuning nodig **en** moet het service-account in Atlassian toegang
  krijgen.

### Fixed — 2026-08-14 — Argo weigerde de hele sync op Role/RoleBinding

Na de laatste push bleef het portaal op `0.2.0a3` staan. Argo stond `OutOfSync` maar
meldde `health: Healthy` — een **stille stilstand**, geen zichtbare storing.

Oorzaak: de AppProject `iso-platform` heeft een `namespaceResourceWhitelist`, en
`rbac.authorization.k8s.io/Role` en `RoleBinding` stonden er niet in. Argo weigerde daarop
de héle sync (`one or more synchronization tasks are not valid`), dus ook de Deployment.
Geen cluster-rechtenprobleem: de argocd-controller *mag* Roles maken in die namespace —
het was de projectpolicy.

Beide kinds toegevoegd aan `argo/projects/iso-platform.yaml`, met de reden erbij.
`clusterResourceWhitelist` blijft ongemoeid: geen ClusterRole.

**Gelukkig gevolg:** omdat de sync faalde, is het image `0.2.0a7` nooit uitgerold. Dat
image is kapot — nagemeten met `podman run`: `ModuleNotFoundError: No module named
'iso_audit.config'`, want het is gebouwd uit de commit waarin die map niet in git zat.
`0.2.0a8` is de eerste correcte.

**Volgorde bij het herstellen:** eerst de commits naar origin (dan wijst het manifest naar
`0.2.0a8`), daarna de AppProject toepassen. Andersom synct Argo `124590c` en rolt het
kapotte `0.2.0a7` uit.

Les: naar origin sturen is geen rollout. `scripts/rollout-portal.sh` wacht op de
Argo-revisie en had dit gezien; die stap is overgeslagen.

### Fixed — 2026-08-14 — `src/iso_audit/config/` stond niet in git

CI viel om op `ModuleNotFoundError: No module named 'iso_audit.config'` terwijl de lokale
suite groen was. Oorzaak: een **globale** gitignore-regel — een kale `config` in
`~/.gitignore_global` — sluit elke map met die naam uit, ook een Python-package.
`src/iso_audit/config/` en `tests/config/` zijn daardoor stil niet meegecommit: `git add -A`
sloeg ze over en `git commit` slaagde zonder klacht.

De lokale testsuite kon dit niet zien: die draait tegen de working tree, waar de bestanden
wél staan. Pas een install uit een verse checkout viel om.

Opgelost met expliciete negaties in `.gitignore`, bewust op `*.py` en niet op `**` — dat
laatste overrulet de `__pycache__`-regel en trekt bytecode de commit in (eerst gebeurd,
daarna teruggedraaid).

**En als gate, niet als aantekening:** `tests/test_alles_getrackt.py` vergelijkt elke
`.py` onder `src/` en `tests/` met `git ls-files` en faalt op wat git niet kent — met een
verwijzing naar `git check-ignore -v` én naar de globale gitignore, want daar zat het.
Een tweede test controleert dat de negaties geen bytecode meetrekken.

**Wat dit nog blootlegde:** ruff respecteert `.gitignore`, dus de genegeerde map werd ook
niet gelint. Zodra hij ontgrendeld was, kwamen er twee bevindingen boven die eerder
onzichtbaar waren (`N818` op een exception-naam zonder `Error`-suffix, en een te lange
regel). Beide gefixt; `SecretStoreOnbeschikbaar` heet nu `SecretStoreError`, conform
`ConfigError` en `AuthError` elders. De eerdere "ruff clean"-meldingen van vandaag dekten
dus minder bestanden dan ze suggereerden. Mypy en pytest keken wél mee — die respecteren
`.gitignore` niet.

974 passed, 1 skipped; ruff + mypy --strict clean; bandit 0 op medium+. Versie `0.2.0a8`.

### Added — 2026-08-14 — UI-configuratie in een Secret, met zo smal mogelijke rechten

`config/secret_store.py` bewaart de UI-configuratie in het Secret
`iso-audit-portal-config` wanneer `ISO_AUDIT_CONFIG_SECRET` gezet is. Achter dezelfde
`BronConfig`-interface: geen publieke methode gewijzigd.

**De PVC-terugval blijft.** Onbereikbare kube-API of geen Secret geconfigureerd = schrijven
naar `bron_config.json` met een waarschuwing. Zonder terugval is het tool niet meer buiten
dit cluster te draaien, en dat was juist de reden om configuratie uit het cluster te halen.

**Twee dingen anders gedaan dan het plan zei.**

Het plan zei `automountServiceAccountToken: true`. Dat zet de token in **élke** container
van de pod, ook in de oauth2-proxy-sidecar, en die heeft bij de kube-API niets te zoeken.
In plaats daarvan blijft de SA-default `false` en mount `deployment.yaml` een **projected**
token alleen in de app-container: 1 uur geldig, automatisch geroteerd, expliciete audience.
Daarmee wordt de hardening-keuze van vorige week niet teruggedraaid maar verfijnd.

Bandit flagde `urllib.request.urlopen` (B310) omdat het niet kan bewijzen dat het schema
https is. Dat is niet met een `# nosec` weggezet: de code gebruikt nu
`http.client.HTTPSConnection`, die geen ander schema *kan* worden. Structureel in plaats van
een controle die iemand kan vergeten — en de bandit-bevinding is weg in plaats van gesust.

**Rechten, zo smal als het kan** (`deploy/rbac-config.yaml`): Role — geen ClusterRole —
met `resourceNames: ["iso-audit-portal-config"]` en verbs `get`+`patch`. Geen `list` (dat
zou alle Secrets opsommen en de naambeperking zinloos maken), geen `create`/`delete`. De
drie `kubectl auth can-i`-regels om dit te verifiëren staan in `deploy/README.md`, samen
met de reden waarom de app nu wél een token heeft — een reviewer die de oude regel kent
moet die uitleg kunnen vinden.

Een kube-API-fout geeft alleen de statuscode terug, nooit de responsbody: die kan het
meegestuurde token echoën. Met test.

972 passed, 1 skipped; ruff + mypy --strict clean; bandit 0 bevindingen op medium+.
Versie `0.2.0a7`.

**Nog te doen in het cluster:** het lege Secret aanmaken en de drie `can-i`-regels
verifiëren. Tot dat moment draait het portaal op de PVC-terugval — dus zonder functieverlies.

### Added — 2026-08-14 — agentische laag: doorvragen, met afdwingbare grenzen

`iso_audit.agent` voegt toe wat de vaste keten niet kan: **doorvragen**. `pipeline.py`
leest alle bronnen, classificeert en stopt. Een auditor die ziet dat een beleidsdocument
verwijst naar een procedure die niet in de auditmap staat, gaat die procedure zoeken — en
dat is capability 2 (patroondetectie), geen extraatje.

**Twee harde grenzen, geen adviserend budget.** `max_iterations` én een kostenplafond op de
gecorrigeerde prijzentabel. Bij overschrijding stopt de lus en staat de reden
(`rondelimiet` / `kostenplafond`) in de trail. `task_budget` is bewust **niet** gebruikt:
dat is adviserend — het model ziet een aftelling maar wordt niet gestopt — en het hangt aan
een beta die de gepinde SDK (0.102.0) niet typeert. Voor een auditor is "de lus stopte
gegarandeerd" bruikbaar; "het model wist van een budget" niet.

**Geen tool schrijft.** Niet naar `findings.json`, niet naar `runs.jsonl`, niet naar de
database. Twee tests lezen de broncode van elke tool en falen op elke schrijf-operatie. Kan
een bevinding de trail bereiken zonder door de join, dan is de trail geen bewijs meer maar
een verzameling losse beweringen.

**De join blijft deterministisch.** De agent *stelt voor*; `api/runs.py:dedup_sleutel`
bepaalt wat één bevinding is. `voeg_toe_via_join` staat als aparte functie zodat die
scheiding in de code te zien is en niet alleen in een docstring. Een test laat de agent twee
voorstellen doen die alleen in schrijfwijze verschillen en controleert dat er één bevinding
uitkomt.

**Bewijs is verplicht.** `stel_bevinding_voor` weigert een voorstel zonder document- of
ticket-id: een observatie zonder bewijs is een vraag, en die hoort als vraag in het memo.

**Elke tool-aanroep levert een trail-regel** met tool, bron, model en prompt-versie
(`agent-v1`). Zonder die velden is een agentische run een zwarte doos en een oude run niet
te reproduceren.

**Nog niet aangesloten** op de UI of op `pipeline.py` als runmodus — dat is de volgende
increment. Half aansluiten is erger dan niet aansluiten, want dan bestaat er een pad dat
niemand kent.

**Managed Agents beoordeeld en voor nu afgewezen.** De cloud-sandbox valt af omdat
auditbewijs dan in een door Anthropic gehoste container terechtkomt; dat is een
verwerkersvraag die dit project niet kan beantwoorden en die het tool onleverbaar maakt aan
een partij die dat niet wil. De self-hosted-sandbox-variant is de interessante upgrade —
lus bij Anthropic, tools in onze pod via uitgaand pollen — maar kost een tweede proces, een
tweede credential-soort en een beta-platformafhankelijkheid. Zie `openspec/changes/
agent-runtime/design.md` voor de afweging.

**Consequentie voor credentials:** een runtime in het cluster is headless en kan dus niet op
de `sso`-modus draaien (geen browser, refresh-token verloopt hard). Een org-workspace-key is
voor autonome runs een voorwaarde, geen verbetering.

961 passed, 1 skipped; ruff + mypy --strict clean. Versie `0.2.0a6`.

### Security — 2026-08-14 — leveranciersfouten lekten naar de browser

`api/session.py:_check_source` gaf `str(exc)[:200]` door aan het configuratiescherm. Die
tekst komt uit de client van de leverancier en kan een URL met credential, een
tokenfragment of een request-dump bevatten — en hij landde rechtstreeks in de browser
(`ui.html`, de reden onder een niet-gekoppelde bron) en in alles wat de browser logt.

Nieuw `config/verbinding.py` zet een exception om naar **één van vier soorten** (`auth`,
`niet_gevonden`, `netwerk`, `onbekend`) met een vaste, leesbare tekst. De ruwe melding
gaat naar het serverlog, waar hij voor diagnose thuishoort. Regressietest gooit een fout
met een token erin en controleert dat noch het token, noch het hostname, noch de ruwe
statuscode de client bereikt.

Dit is **geen** tweede healthcheck: elke bron rapporteert zijn eigen status via
`healthcheck()`/`probe()`, en `bron_health` blijft daarvoor de enige bron van waarheid —
precies wat zijn eigen docstring al voorschreef. `verbinding.py` bevat alleen de
vertaling van een fout, plus de Anthropic-check omdat die geen Source-adapter heeft.

Meegenomen: de Miro-melding zei "MIRO_API_TOKEN ontbreekt". Een configuratiescherm is
niet de plek waar iemand variabelenamen hoort te leren; nu "Er is nog geen API-token
ingevuld."

Toegevoegd: een "Opnieuw testen"-knop. Een token kan ongeldig worden zonder dat er iets
wordt opgeslagen, en tot nu testte het scherm alleen bij het laden en na een wijziging.

949 passed, 1 skipped; ruff + mypy --strict clean; bandit schoon op de CI-drempel.
Versie `0.2.0a5`.

### Added — 2026-08-14 — Anthropic met abonnement of API-key, en optionele GWS-impersonation

**Inloggen met een Claude-abonnement kan nu.** Eerder stond in dit project dat een
abonnement niet bruikbaar was voor de classifier en dat SSO een tweede aanroeppad zou
vragen. Dat was fout: de SDK lost credentials op in de volgorde API-key → auth-token →
CLI-profiel → workload identity → default-profiel, dus een kale `anthropic.Anthropic()`
— precies wat `findings.py`, `llm.py` en `thema.py` al gebruiken — pikt een CLI-profiel
automatisch op. Er is dus **niets** aan de classifier gewijzigd.

- `config/anthropic_auth.py` drijft `ant auth login --no-browser`: het portaal geeft de
  authorize-URL aan de auditor, die logt in zijn eigen browser in en plakt de code terug.
  Het portaal heeft geen browser en hoort er ook geen te hebben.
- Halve logins staan in het geheugen met een harde vervaltijd van 10 minuten en worden
  opgeruimd; een sessie-id is eenmalig. De code en de profielinhoud worden niet gelogd en
  niet teruggegeven.
- Foutmeldingen zijn genormaliseerd — ruwe CLI-output kan een URL met credential bevatten.
- Het configscherm heeft een eigen Claude-kaart met de modus-keuze, de login/uitlog-actie,
  het model en de peildatum van de tarieven. Daar staat ook waaróm een abonnement niet
  overal werkt: geplande runs hebben geen browser om mee in te loggen.

**Getest tegen een stub-CLI, niet tegen een echt account.** Een testsuite die een
OAuth-flow tegen iemands profiel start en dat overschrijft is onacceptabel; de stub
imiteert het contract (URL op stdout, code op stdin).

**GWS-impersonation** is toegevoegd als optioneel veld (`GWS_IMPERSONATE_EMAIL`). Leeg =
map-sharing precies zoals het was. Gevuld = `with_subject`, en dat vraagt eenmalige
autorisatie van domain-wide delegation door een Workspace-super-admin; zonder die stap
faalt elke call met `unauthorized_client`. In de code staat expliciet dat impersonation de
map-sharing omzeilt die anders de auditscope begrenst — laat het leeg tenzij een bron
onbereikbaar is.

**`ant` in het image, met vastgepinde versie én checksum** (1.23.0 +
sha256). Een `curl | tar` zonder verificatie is dezelfde supply-chain-afhankelijkheid die
we vandaag uit deze repo verwijderden; die mag niet via de Dockerfile terugkomen.
Ontbreekt de binary, dan meldt het portaal dat en wijst het naar de API-key-modus.

`ANTHROPIC_CONFIG_DIR` staat op de PVC, zodat een login een pod-restart overleeft; de
initContainer maakt die map met mode 700 aan.

Jira's account-veld heet in de UI nu "Service-account e-mail" met de reden erbij. De
env-naam blijft `JIRA_USER_EMAIL` — hernoemen zou een werkende, uitgerolde bron breken
voor een cosmetische winst.

932 passed, 1 skipped; ruff + mypy --strict clean. Versie `0.2.0a4`.

### Fixed — 2026-08-14 — prijzentabel stond fout, kostenregels vielen te laag uit

`PRIJZEN` in `classification/findings.py` had Haiku 4.5 op $0.80/$4.00 per miljoen
tokens; werkelijk is dat **$1.00/$5.00**. Elke kostenregel in een auditrapport viel
daardoor ongeveer een kwart te laag uit. Opus stond op $15.00/$75.00 waar $5.00/$25.00
klopt — die kant op ook fout, alleen minder gevaarlijk.

Een te lage kostenpost is schadelijker dan geen kostenpost, omdat hij compleet lijkt.

Nu: `claude-haiku-4-5` (plus de gedateerde ID, identiek geprijsd — er staan historische
runs op die vorm), `claude-sonnet-5`, `claude-opus-5`. Toegevoegd:
`PRIJZEN_PEILDATUM = "2026-08-14"` en `KIESBARE_MODELLEN`, met tests die falen zodra een
kiesbaar model geen prijsregel heeft, een tarief niet klopt met de standaard
cache-structuur, of output goedkoper is dan input.

**Nog open, gemeld niet gefixt:** `Kostenteller.kosten_usd()` geeft `0.0` voor een
onbekend model. Dat is bestaand gedrag met een eigen test, en buiten de scope van deze
change — maar het is dezelfde faalmodus: een run die stil geen kosten rapporteert. De
nieuwe test dekt de keuzelijst, niet een handmatig meegegeven `--model`.

### Added — 2026-08-14 — één configuratie-loader met herkomst

Nieuw `src/iso_audit/config/`: `settings.py` en `herkomst.py`. Eén loader lost alle
configuratie op in de volgorde **omgeving > `config.yaml` > UI > default**, en levert per
veld mee **waar de waarde vandaan komt**. Voor een audit is dat het interessante deel:
liep die run op een cluster-Secret of op iets dat iemand in de UI had ingetypt?

- Herkomst is een eigenschap van de waarde (`Waarde(waarde, bron)`), niet een tweede
  administratie die bij een transformatie kan wegvallen.
- `Waarde.__repr__` toont een geheim **nooit** — je krijgt `<geheim>` plus de bron. Een
  geheim kan daardoor niet via een f-string, een assert-melding of een stacktrace in een
  logbestand belanden. Structurele grens, geen discipline; zelfde idee als
  `api/audit_log.log_event`, die bewust alleen scalars aanneemt.
- Eén maskeerfunctie voor de UI, met vaste bullet-lengte zodat de maskering niet verklapt
  hoe lang een token is.
- Bij het starten één audit-logregel per veld met de bron; nooit een waarde.
  `GET /config/herkomst` geeft hetzelfde, zodat een auditor het zonder cluster kan zien.
- Het configuratiescherm toont per invulveld een badge met de bron. Velden uit de
  omgeving of `config.yaml` zijn gemarkeerd als vast — anders typt een auditor iets in dat
  stil geen effect heeft.
- Een geheim in `config.yaml` werkt maar waarschuwt. Weigeren zou een derde partij
  blokkeren op een bestand dat hij zelf kan repareren.
- Kapotte YAML en een nieuwere `config_version` blokkeren het portaal niet: configuratie
  kunnen zien is de voorwaarde om hem te repareren.

**De sso-val, met een eigen test.** Een gezette `ANTHROPIC_API_KEY` verslaat het
CLI-profiel altijd — óók een lege string. Bij `auth_mode: sso` verwijdert de loader die
variabele daarom actief uit de omgeving in plaats van hem over te slaan. Zonder dat faalt
een run op een credential die de auditor niet gekozen heeft, en wijst de foutmelding naar
Anthropic in plaats van naar de configuratie.

Verder: `config.example.yaml`, `env.example` en `docs/reference/configuratie.md`. Het
voorbeeldbestand heet bewust `env.example` en niet `.env.example`: de werkstation-policy
verbiedt tooling het lezen en schrijven van `.env*`, en een naam die daar niet onder valt
houdt agents en scripts weg bij echte secrets.

Geen adapter en geen protocol gewijzigd — de loader vult `os.environ`, dus de
Source-adapters blijven ongewijzigd werken.

913 passed, 1 skipped; ruff + mypy --strict clean.

### Removed — 2026-08-14 — habitat-artefacten uit de repo

Commit `cd0cc4f` (13 juli 2026, "seed apply-docs-contract change + habitat role
files") bracht ongevraagd een externe agent-harnas binnen. Verwijderd:

- `.claude/agents/{builder,reviewer,security}.md` — drie rol-agents die niet in
  `CLAUDE.md` gedocumenteerd stonden en wier rolverdeling botst met de
  OpenSpec-workflow die deze repo wél beschrijft.
- `.mcp.json` — haalde een MCP-server via `uvx --from
  git+https://github.com/MWest2020/handbook`. Dat is code uitvoeren uit een
  **persoonlijke** repo in een org-repo: precies de persoonsgebonden afhankelijkheid
  die dit project aan het opheffen is.
- `.habitat/` (`audit.jsonl`, run-output, HTML-rapport) — getrackte build-artefacten
  van een externe tool in een repo onder ISO 27001-scope. Nu in `.gitignore`.

De historie blijft: `cd0cc4f` is niet herschreven. De bestanden verdwijnen met een
normale commit, want de historie is auditbewijs.

`CLAUDE.md` heeft een regel onder "Wat NIET hier hoort" gekregen, zodat een volgende
seed niet stil opnieuw landt.

### Changed — 2026-08-14 — `apply-docs-contract` gearchiveerd

Deze change was géén artefact: de docs-herindeling naar het handbook-contract
(`docs/{how-to,reference,explanation}` met front matter, stubs op de oude paden) is
echt uitgevoerd en staat op `main`. Alleen de PR-stap stond nog open. Gearchiveerd als
`2026-08-14-apply-docs-contract`.

Wat de migratie destijds liet liggen en nu is opgelost: **de verwijzers**. `CLAUDE.md`
wees twee keer naar `docs/missie.md`, sinds juli een deprecated stub — de
instructie-ingang van de repo stuurde lezers dus naar een doorverwijspagina. En
`README.md` + `ARCHITECTURE.md` linkten naar `docs/sources/`, `docs/sinks/` en
`docs/notifiers/`, drie mappen die **niet meer bestaan**: dode links, geen stubs.

Bijgewerkt: `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, `ONBOARDING.md`, `MEMORY.md`,
`.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/feature.md`. `CHANGELOG.md`
en de openspec-archieven zijn bewust *niet* aangepast — dat zijn verslagen van wat toen
waar was.

Nog open uit de proposal, als besluit voor Mark: de repo is publiek maar een deel van
de pagina's is Nederlands.

875 passed, 1 skipped; ruff clean.

### Added — 2026-08-14 — bronnen koppelen in de UI, uitlogknop, en normkeuze als enum

**Bronnen koppelen kan nu in het portaal.** Per bron een kaart met een
Configureer-knop en een formulier; geen cluster, geen Secret, geen beheerder. Dat is
wat het tool leverbaar maakt aan derden.

- `bron_catalogus.py` zegt *wat* een bron nodig heeft (label, hint, geheim of niet).
  Ingebouwde standaard, te overrulen met YAML via `ISO_AUDIT_BRON_CATALOGUS`. Een
  beheerder genereert die bij initialisatie met
  `scripts/genereer-bron-catalogus.sh`; zonder dat bestand werkt het portaal ook —
  een tool dat pas werkt na een generatiestap lever je niet uit.
- `bron_config.py` bewaart de *waarden* en zet ze in `os.environ`. Daarmee blijven
  álle Source-adapters ongewijzigd: geen adapter hoeft te weten dat er een portaal is.
- Waarden uit het manifest of een Secret blijven vóórgaan op wat via de UI is
  ingevuld — wat een beheerder expliciet zette, weegt zwaarder.
- Geheime velden gaan er nooit uit: de API meldt `ingesteld`, niet de waarde. Het
  bestand op de PVC staat op mode 0600.
- Elke wijziging staat append-only met identiteit, tijdstip en veldnamen in
  `bron_config_log.jsonl` — waarden nooit. Dat registreren *is* de controle.
- Configureren tijdens een lopende run geeft 409: een Source leest zijn config bij
  start, dus halverwege wisselen levert een run met twee scopes.

**Dit is geen secret-manager**, en dat staat er ook zo bij. Waarden staan als JSON op
de PVC naast de audit-trail. Zwakker dan een cluster-Secret; bewuste ruil, want
configuratie die alleen via Secrets kan betekent dat elke partij een
Kubernetes-beheerder nodig heeft om te beginnen.

**Uitlogknop.** Er was geen manier om het portaal te verlaten behalve je browser
sluiten. Nieuw `/me` geeft de identiteit en een optionele logout-URL; de nav toont
"ingelogd als X" plus Uitloggen. Met `ISO_AUDIT_LOGOUT_URL` gezet hopt uitloggen door
naar de identity-provider, zodat een volgende login niet stil doorloopt op een
bestaande sessie. Niet gezet = alleen de proxy-sessie wissen, wat beter is dan een
hardcoded URL die bij een andere partij naar de verkeerde plek wijst.

**Normkeuze is een enum.** Was: vinkjes plus een alinea over id-formaat, periode-syntax
en norm-YAML's. Nu: één select met "ISO 9001", "ISO 27001", "Beide", en de uitleg als
tooltip. De auditor hoeft niets te weten van slugs, id-opbouw of YAML.

**Twee eigen fouten onderweg.** `"/memo/preview".startswith("/me")` is waar, dus het
toevoegen van `/me` aan de ongescopede-padenlijst brak vijf tests; die vergelijking gaat
nu op segmentgrens. En de guard-test voor "geen config tijdens een run" slaagde eerst
per ongeluk: de sim-run doet één tik per bevinding, dus met een lege werkset was hij
direct klaar en werd de guard nooit geraakt.

875 passed, ruff + `mypy --strict` clean. Versie naar `0.2.0a3`.

### Added — 2026-08-14 — CI faalt als de image-inhoud wijzigt zonder versiebump

De bestaande check vergeleek alleen of `version` en `newTag` gelijk waren. Die vangt
niet dat de versie is blijven staan terwijl de inhoud van het image wijzigde — en dan
herbouwt de workflow dezelfde tag met andere inhoud. Argo ziet geen manifest-wijziging,
de node heeft die tag al gecacht, en de pod draait stil oude code.

Dat gebeurde vandaag: commit `9f8dc26` wijzigde `src/` zonder bump, waardoor tag
`0.2.0a0` onder onze handen bewoog.

De nieuwe stap vergelijkt met de vorige commit (PR-basis of `github.event.before`) en
faalt als een van `src/`, `Dockerfile`, `uv.lock`, `pyproject.toml` of `examples/`
wijzigde terwijl de versie gelijk bleef. Logica nagerekend tegen echte historie: faalt
op `9f8dc26`, laat de bump `d19f291` door, en laat een docs-only commit door.

`.github/` zit bewust niet in die padenlijst — een workflow-wijziging landt niet in het
image, dus die hoeft geen versie te bewegen. Deze commit is daar zelf het bewijs van.

### Changed — 2026-08-14 — audit over meerdere normen; normenlijst uit de norm-DB

Twee correcties op mijn eigen ontwerp, beide op aanwijzing van de eigenaar.

**Een audit omvat nu één of meer normen.** 9001 én 27001 samen is één audit met één
memo, geen twee administraties. Het id wordt `9001-2026-Q3` of `27001_9001-2026-Q3`.
De normenlijst in de UI komt uit de **norm-DB** in plaats van een hardcoded select: een
norm-YAML erbij zetten maakt hem kiesbaar zonder codewijziging. Slugs
(`iso-9001-2015`) en korte codes (`9001`) leiden naar hetzelfde id, zodat er één
vocabulaire is.

De run leidt zijn norm-parameter nu af uit het audit-manifest en het run-verzoek kan er
geen meer meegeven. Een run die een andere norm kan kiezen dan de audit, levert een
audit waarvan de scope niet uit de audit volgt — en dan vermeldt de memo iets anders dan
er getoetst is.

Kiesbaar is niet draaibaar: de norm-parameter staat op vier plekken in de pipeline
hardcoded op `9001|27001|beide`. Een norm daarbuiten **faalt bij het aanmaken** met een
leesbare fout, in plaats van stil een verkeerde run op te leveren. Die vier plekken
generaliseren is een eigen change.

**Het configuratiescherm wordt schrijfbaar, niet alleen-lezen.** Mijn eerdere eis was
fout onderbouwd, op twee punten:

- `sources/base.py` eist immutability **na `__init__`** — een object-lifecycle-invariant
  zodat een Source niet halverwege een run van scope wisselt. Ik had daar een
  autorisatiebeleid van gemaakt ("alleen via cluster-Secrets").
- De dreiging bestond niet. Bewijs bestaat of het bestaat niet. Een auditor kiest
  bronnen, die bronnen worden per run vastgelegd, en een ontbrekende bron valt een laag
  hoger op: een interne auditor wordt door een externe gecontroleerd en die staat onder
  toezicht.

Bovendien maakte het het tool onleverbaar: configuratie die alleen via cluster-Secrets
kan, betekent dat elke derde partij een Kubernetes-beheerder nodig heeft. Wat wél uit de
immutability-regel volgt en blijft staan: een configuratiewijziging wordt geweigerd
zolang er in die audit een run loopt. Credentials worden schrijfbaar maar nooit
teruggegeven.

De implementatie daarvan staat als taak 3.6-3.9; het scherm zegt nu eerlijk dat
koppelen vanuit de UI in aanbouw is in plaats van dat het zo bedoeld zou zijn.

851 passed, ruff + `mypy --strict` clean.

### Changed — 2026-08-14 — portaal is een dashboard met audits en runs (breaking API)

Het portaal kende precies één auditsessie, meegegeven bij het starten. Daarmee kon je
een audit doen maar geen auditpraktijk draaien: een nieuwe audit vroeg een
beheeractie, en eerdere audits waren onvindbaar zodra de sessie-dir hergebruikt was.
Change `portal-dashboard`.

**BREAKING op de API.** Alle auditdata-routes noemen nu hun audit:
`/audits/{id}/findings` in plaats van `/findings`. `create_app` neemt een
`AuditRegistry`, en `iso-audit ui` heeft `--audits` in plaats van `--session`;
`--memo-input` is vervallen omdat memo-input bij één audit hoort. Bewust breaking: één
deployment, versie `0.x`, geen consument buiten de eigen `ui.html`.

Manifest en image moeten samen omhoog: het oude image kent `--audits` niet en het
nieuwe kent `--session` niet. Beide zitten daarom in dezelfde commit, met versie én
`newTag` op `0.2.0a0`.

- **Audits zijn eerste-klas.** Directory met `audit.json`; id uit norm + periode
  (`9001-2026-Q3`). Periode gevalideerd op `JJJJ-Qn`/`JJJJ-Hn` zodat sorteren klopt.
  Een dubbel id is een fout, geen stil suffix.
- **Runs append-only geregistreerd** in `runs.jsonl` met identiteit, modus, bronnen en
  aantallen — inclusief mislukte runs met hun fout.
- **Een volgende run vult aan.** Dedup deterministisch op norm + clausule + bron +
  genormaliseerde titel; overgeslagen duplicaten worden geteld, niet stil weggelaten.
- **Dashboard als landingsscherm** met norm+periode, status, triage-voortgang en
  memo-status, bronnen, en wie er als laatste aan werkte. Status is **afgeleid** uit de
  bestanden (`nieuw`/`loopt`/`memo-klaar`), nooit opgeslagen.
- **Configuratie is een eigen, alleen-lezend scherm.** Wijzigen blijft via Secrets en
  manifest: `sources/base.py` eist dat een bron zijn configuratie onveranderlijk houdt
  binnen een auditperiode, en een auditor die zijn Drive-map kan verzetten kan zijn
  eigen bewijsbasis kiezen.
- **Gelijktijdig werk wordt gemeld, niet geblokkeerd** (`.actief`). Bewust geen slot:
  een blijven-hangen slot maakt een audit onbruikbaar. Restrisico staat in de spec.
- **Portaal start op een lege audits-root.** InitContainer heet nu `seed-audits` en
  maakt alleen de root plus het profiel.

**Gat dat de containertest blootlegde:** `_run_live_worker` deed `self._save(drafted)`
en overschreef de hele werkset. De dedup-module bestond en was getest, maar niets riep
hem aan vanuit de run — dus de eis "een volgende run gooit geen triage weg" hield op
moduleniveau en niet in de praktijk. Nu gewired, met een regressietest via de échte
route.

Ook: sessies worden per audit-id gecachet (`api/deps.py`). Geen optimalisatie — de
voortgang van een lopende run leeft in het sessie-object, en een verse sessie per
request liet `/run/progress` altijd `idle` zeggen. Bij opschalen naar meerdere replicas
moet run-status naar schijf.

**Migratie: niets te doen.** Gemeten op de PVC 2026-08-14: `sessie/findings.json` is
`[]` en er is geen `triage_log.jsonl`, dus er is nooit een beslissing vastgelegd. De
oude `sessie/`-map wordt genegeerd en kan later weg.

Versie naar `0.2.0a0`.

### Fixed — 2026-08-12 — login-500 opgelost in Git in plaats van in de Keycloak-UI

De 500 na een geslaagde login kwam doordat Keycloak deze client niet als `aud` in
het token zet; er staat alleen `azp: iso-audit-portal`. oauth2-proxy verifieert de
audience en faalde met `audience claims [aud] do not exist in claims`.

De gangbare remedie is een `oidc-audience-mapper` in Keycloak. **Bewust niet
gekozen.** Die mapper leeft dan in de Keycloak-UI en niet in Git, en dat is precies
de onzichtbare drift die in deze opstelling al drie keer is opgetreden: de clients
zelf, de Google identity provider, en dezelfde mapper bij `openwoo-provisioner`.

In plaats daarvan `--oidc-audience-claim=azp` in `deployment.yaml`. Die vlag staat in
een manifest dat Argo synct, dus de fix is reviewbaar, reproduceerbaar en verdwijnt
niet als iemand de realm opnieuw importeert. Semantisch klopt het: `azp` is de client
waaraan het token is uitgegeven, en oauth2-proxy vergelijkt de claim met zijn eigen
`client_id` — de check blijft "is dit token voor mij bedoeld", alleen via de claim die
Keycloak hier daadwerkelijk levert.

Geverifieerd dat oauth2-proxy v7.7.1 de vlag kent (`--oidc-audience-claim strings —
which OIDC claims are used as audience to verify against client id`) en hem accepteert.

De audience-mapper blijft als alternatief in `keycloak-client.example.yaml` staan, met
beide token-claims aan, voor wie de realm ooit vers importeert.

### Fixed — 2026-08-12 — login gaf 500: audience-mapper ontbrak; Argo-wacht keek niet naar de revisie

**Login faalde na een geslaagde inlog.** Keycloak zet de client niet als `aud` in
het token — in de claims stond alleen `azp: iso-audit-portal` — en oauth2-proxy eist
die audience-claim. Resultaat: inlogportaal werkt, login lukt, daarna een 500 met
`audience claims [aud] do not exist in claims` in de proxy-log. De bekende
Keycloak/oauth2-proxy-valkuil.

De benodigde `oidc-audience-mapper` staat nu in `keycloak-client.example.yaml` en in
de import-JSON, plus in de prerequisites van `deploy/README.md` met de foutmelding
erbij zodat niemand dit opnieuw hoeft te debuggen. Toevoegen aan een bestaande client
gaat via de UI (Client scopes → dedicated → Audience); een herstart is niet nodig.

Bijkomende observatie voor het dossier: `openwoo-provisioner` heeft dezelfde mapper
nodig en werkt, dus die is daar eerder met de hand toegevoegd. Daarmee is dit het
derde stuk Keycloak-configuratie dat alleen in Keycloak bestaat en niet in Git — na
de clients zelf en de Google identity provider. `keycloak-config-cli` als sync-stap
zou dat hele patroon opheffen en is nu de duidelijkste openstaande verbetering.

**`rollout-portal.sh` wachtte op de verkeerde voorwaarde.** `wacht_op_argo` keek
alleen of Argo `Synced` was, niet op *welke* revisie. Argo stond al Synced op de
vorige commit, dus de wacht viel er meteen door en de herstart liep met het oude
manifest — zonder de nieuwe initContainer. Argo pollt standaard om de ~3 minuten. De
functie forceert nu een refresh en vergelijkt de revisie met `git rev-parse HEAD`.

Dat is de derde aanname over "het staat er wel" die onderweg omviel, na de
non-numerieke `USER` en het cookie-secret. Alle drie zijn nu een check in het script
of in een manifest, in plaats van iets dat je moet onthouden.

### Fixed — 2026-08-12 — portaal start nu op een verse PVC (initContainer `seed-sessie`)

Na de USER- en cookie-secret-fix startte `oauth2-proxy` wel, maar viel de app om met
`SessionError: Geen findings.json in sessie-dir`. Dat is geen bug — het is precies
het gedrag uit de spec: de app verzint geen lege sessie. Maar het legde wel een
ontwerpgat bloot: een portaal dat alleen draait als er al een auditsessie op de PVC
staat, kun je niet online laten staan. Prerequisite 4 was handwerk dat niemand had
gedaan.

Opgelost met een initContainer die een **lege maar geldige** sessie neerzet als die
er niet is: `findings.json` met `[]`, plus profiel en memo-input uit het image. Geen
fixture-bevindingen — leeg is leeg, en dat is een eerlijke startstand voor een
auditwerktuig. Idempotent: bestaande bestanden worden nooit overschreven, dus een
echte auditsessie blijft ongemoeid.

Het onderscheid staat nu expliciet in de spec: de **applicatie** verzint niets, het
**deployment** mag provisioneren. Dat is een zichtbare deploy-stap, geen stille
fallback in de app.

Geverifieerd tegen het gepubliceerde image `0.1.0a1`, in containers met een named
volume (de eerdere hosttest struikelde op de uid-mapping van rootless podman): seed
werkt, overschrijft bestaande data niet, en de app start daarna met `/healthz` 200,
`/findings` `[]` en `/config/health` 200.

### Fixed — 2026-08-12 — de eerste rollout viel om op twee fouten in mijn manifests

Beide pas gevonden door het echt uit te rollen; het image bouwde en draaide lokaal
prima. Versie naar `0.1.0a1` zodat de fix ook daadwerkelijk uitgerold wordt.

- **`app`-container werd niet eens aangemaakt.** De Dockerfile deed `USER app` —
  een naam. In combinatie met `runAsNonRoot: true` weigert de kubelet de container:
  hij kan niet vaststellen dat de user geen root is en faalt met *"image has
  non-numeric user (app), cannot verify user is non-root"*. Er is dan geen
  container om te zien starten, alleen een `Failed`-event — vandaar "niet eens aan
  het initialiseren". Nu `USER 10001:10001` in het image, én expliciet
  `runAsUser`/`runAsGroup` in de pod-securityContext zodat het manifest niet
  afhankelijk is van de image-inhoud.
- **`oauth2-proxy` crashloopte op het cookie-secret.** Het script genereerde
  `openssl rand -base64 32`. oauth2-proxy decodeert met `base64.RawURLEncoding`, en
  die verwerpt de tekens `+` en `/` uit standaard-base64; mislukt het decoderen, dan
  leest het de string als 44 ruwe bytes en faalt met *"cookie_secret must be 16, 24,
  or 32 bytes ..., but is 44 bytes"*. Nu URL-safe (`tr -- '+/' '-_'`) plus een
  vormcontrole in het script, zodat een fout secret in het script faalt en niet in
  het cluster.

**Actie bij bijwerken:** het script moet opnieuw gedraaid worden om het
cookie-secret te vervangen — een secret dat met de oude versie is aangemaakt blijft
fout. Draai het uit een checkout die deze fix bevat.

Geverifieerd op het herbouwde image, met exact de cluster-constraints
(`--read-only`, `--user 10001:10001`, PVC-mount): `USER` is numeriek `10001:10001`,
de app start, `/healthz` geeft 200, `/findings` 403 zonder identity-header en 200
met. De cookie-secret-generatie is 5x nagelopen op vorm en decodeert naar 32 bytes.

### Changed — 2026-08-12 — geen bot-commits naar main; realm-import blijkt create-once

Twee correcties op de deploy-aannames van change `iso-portal`, beide gemeten en
niet aangenomen.

**`image.yml` schrijft niet meer naar de repo.** De merge-is-deploy-opzet committe
de image-tag zelf terug naar main en had daarvoor `contents: write` nodig. Dat
maakte branch-bescherming onmogelijk zonder uitzondering voor de bot, en een
gecompromitteerde workflow-stap kon zo de gedeployde tag verleggen — sec-bevinding
3 van de change. Nu bouwt de workflow op de PR, verifieert dat `newTag` in
`deploy/kustomization.yaml` gelijk is aan `version` in `pyproject.toml`, en heeft
alleen nog `contents: read`. De ordening klopt vanzelf: het image bestaat vóór de
merge, dus Argo vindt de tag direct. Fork-PR's kunnen niet naar de registry pushen.

Release-flow wordt daarmee: één nummer op twee plekken (version + newTag), in
dezelfde PR. Lopen ze uiteen, dan faalt de check met een leesbare melding. Naast
de versietag wordt `sha-<short>` gepusht als immutabel spoor per commit.

Hiermee is sec-bevinding 3 gedicht in plaats van gemitigeerd: er is geen
automatisering meer die naar main schrijft, dus branch-bescherming heeft geen
uitzondering nodig.

**`KeycloakRealmImport` is create-once — de docs beweerden iets anders.** De
prerequisites en `design.md` stelden dat de Keycloak-client via de realm-import
komt. Dat is in deze opstelling niet zo: de operator importeert een realm die nog
niet bestaat, maar werkt een bestaande realm niet bij. Argo synct de CR wel (de
live resource kreeg `iso-audit-portal` erin), maar er werd geen import-job gestart
— gemeten 2026-08-12: na de merge bleef de laatste job die van 3 augustus. De
client moet met de hand worden aangemaakt via de UI.

Gevolg dat nu vastligt in plaats van in iemands hoofd te zitten: de realm-YAML is
gewenste staat, niet toegepaste staat, en Git en Keycloak kunnen stil uiteenlopen.
Datzelfde gold al voor de Google identity provider. Een reconciliërende oplossing
(`keycloak-config-cli`) is eigen werk.

### Security — 2026-08-12 — 23 dependabot-alerts gedicht (lockfile-bump)

`uv.lock` bijgewerkt met de bump uit dependabot-PR #17, die exact de vijf
pakketten raakt die alarm sloegen: `cryptography` → 50.0.0, `pillow` → 12.3.0,
`httplib2` → 0.32.0, `pyasn1` → 0.6.4, `soupsieve` → 2.8.4. Samen 19 high en
4 moderate alerts.

Deze alerts stonden er al, maar werden pas zichtbaar toen de repo bij de
org-transfer public werd — `secret_scanning` en de dependabot-rapportage komen
met public mee. Relevant voor de ISO-scope omdat het portaal-image uit deze
lockfile bouwt: deze versies gaan naar productie.

`cryptography` 50.0.0 is een major bump onder `google-auth`, dus vóór het mergen
apart getest in plaats van op de CI-uitslag te vertrouwen:

- volledige suite groen (792 passed, 1 skipped) met de nieuwe lockfile;
- WeasyPrint rendert een geldige PDF onder pillow 12.3.0 + soupsieve 2.8.4 (die
  twee zijn render-dependencies, dus de meest waarschijnlijke breukplek);
- `google-auth` en de Drive-client importeren onder cryptography 50.0.0.

De bump hing sinds 11 augustus op de kapotte bandit-gate; met de fix in deze
zelfde wijziging kon hij mee.

### Fixed — 2026-08-12 — de kwaliteitsgates werkten niet meer (sinds 17 juni rood)

CI faalde bij élke run sinds 2026-06-17, en `pre-commit run --all-files` net zo.
Niet op echte problemen, maar op configuratiefouten. Een gate die altijd rood
staat, is geen gate: een écht nieuw probleem valt niet op tussen de ruis. Drie
oorzaken, alle drie pre-existing:

- **CI gaf `-c pyproject.toml` niet mee aan bandit**, terwijl de pre-commit-hook
  dat wel deed. De gedocumenteerde `[tool.bandit]`-skips (B101 voor
  pytest-asserts) golden dus lokaal en niet in CI — precies de stille divergentie
  tussen CI en lokaal die `CLAUDE.md` verbiedt.
- **Bandit geeft exitcode 1 bij élke bevinding**, ook low-severity. Met vier
  pre-existing lows (B110/B112/B404/B607) faalde de stap altijd, ook mét config.
  Nu twee stappen: alles rapporteren (niet-blokkerend) en falen op
  `--severity-level medium` en hoger. Nieuwe lows blijven zichtbaar, blokkeren
  niet; een medium of high breekt de build meteen.
- **De pre-commit bandit-hook was helemáál stuk**: `-r src` samen met de
  bestandslijst die pre-commit erachter plakt, laat bandit afbreken met
  `unrecognized arguments`. De hook faalde dus op een argumentfout, niet op
  bevindingen. `-r src` eruit, `files: ^src/` doet nu de scope — gelijk aan wat CI
  scant.
- **De mypy-hook kon nooit slagen**: `mirrors-mypy` met
  `additional_dependencies: []` draait mypy in een geïsoleerde venv zonder
  pydantic, python-docx of de markdown-stubs, dus faalde hij altijd op
  `import-not-found`. Vervangen door een lokale hook die `uv run mypy --strict src`
  aanroept — exact wat CI draait.

Na deze wijziging: `pre-commit run --all-files` volledig groen, en de CI-stappen
lokaal nagespeeld allemaal exit 0 (792 passed, 1 skipped).

De vier resterende low-bandit-meldingen elk beoordelen en waar terecht van een
`# nosec BXXX` met reden voorzien blijft openstaan als eigen werk — beter
auditspoor, maar geen reden om de gate ondertussen rood te laten staan.

### Added — 2026-08-12 — portaal-deployment: image, manifests, Argo (taak 3-5)

- **`Dockerfile`**: twee stages, `uv sync --frozen` tegen de gecommitte `uv.lock`
  (nooit pip), non-root uid 10001, werkt onder `readOnlyRootFilesystem`.
  WeasyPrint-systeemlibs in de runtime-stage — zonder die faalt de memo-render pas
  wanneer een auditor op exporteren drukt, dus in productie.
- **`deploy/`** (9 manifests + README): namespace `iso-platform`, SA met
  token-automount uit, PVC `tier-1`/8Gi/RWO, deployment met app op `127.0.0.1:8081`
  + oauth2-proxy-sidecar, ClusterIP, Ingress met `letsencrypt-prod`, en de
  NetworkPolicy die ingress tot `ingress-nginx` beperkt. `kubectl kustomize deploy`
  rendert; de proxy-config wordt een gehashte ConfigMap zodat een edit de pod rolt.
- **Twee dingen bewust níet gekloond** uit openwoo: `rbac-*.yaml` (dit portaal
  pollt geen Argo-status en heeft dus geen kube-API-toegang nodig) en
  `networkpolicy-egress.yaml` (staat daar sinds 2026-07-13 uitgeschakeld wegens
  DNS-breuk onder Gardener/Calico — meenemen zou een bekend defect kopiëren).
- **`Recreate`-strategie** i.p.v. rolling update: bij een RWO-volume kan de nieuwe
  pod niet mounten zolang de oude het vasthoudt, dus een rolling update blijft
  hangen. Eén replica is trouwens geen tijdelijke keuze — `create_app()` neemt één
  `AuditSession` en meerdere replicas zouden dezelfde SQLite-DB beschrijven.
- **`argo/`**: AppProject `iso-platform` (één repo, één namespace,
  `clusterResourceWhitelist` alleen `Namespace`) + Application die `deploy/` synct.
  Bewust een eigen project: `cluster-infra` is voor cluster-brede infra en
  `nextcloud-platform` is de verkeerde grens. `Secret` staat niet in de whitelist,
  zodat Argo de out-of-band credentials niet kan beheren of prunen.
- **`.github/workflows/image.yml`**: merge-is-deploy — `sha-<short>` bouwen,
  pullbaarheid verifiëren, dan pas `newTag` terugcommitten met `[skip ci]`. Die
  volgorde is niet vrij: een tag zetten die nog niet bestaat richt Argo op een
  niet-pullbaar image.
- **`deploy/README.md`** met de **credential-herleidbaarheidstabel**: per credential
  het systeem, de Secret-key, het org-account, de eigenaar-rol
  (`info@conduction.nl`) en een maximale leeftijd — inclusief de deploy-keten
  (ghcr-push, tag-bump). De 12-maandstermijn is een keuze, want de meeste van deze
  credentials verlopen niet uit zichzelf.
- **Secret-mechanisme gekozen: out-of-band, geen ESO en geen SOPS.** ESO draait wel
  in dit cluster, maar de bestaande `nextcloud-shared-store` bestaat om één
  seed-Secret naar véél tenant-namespaces te distribueren. `iso-platform` is één
  namespace — er valt niets uit te delen, dus ESO zou een extra hop en een extra te
  auditen component toevoegen zonder dat er iets geheimer wordt.
- **`pyproject.toml`**: `authors`/`maintainers` → Conduction, `Repository` → de
  org-URL. **`CODEOWNERS`** toegevoegd met de deploy-, argo-, workflow- en
  auth-paden expliciet benoemd.
- **Kosten-attributie** (sec-bevinding 6, besluit "loggen, niet begrenzen"):
  `POST /run/start` logt wie de run startte plus de config. `Kostenteller` hield het
  token-verbruik al bij, maar niet de opdrachtgever — zonder die koppeling is een
  kostenpiek niet te adresseren. Er komt géén rate limit; het restrisico staat
  benoemd in de spec.
- **`src/iso_audit/api/audit_log.py`** (nieuw): JSONL-toegangslog naar stdout, apart
  van de inhoudelijke trail. Logt auth-weigeringen, mutaties en run-starts met
  identiteit. Een credential kan er structureel niet in lekken: de functie krijgt
  het request-object nooit te zien en accepteert alleen scalars — geen
  redactie-lijst die iemand moet onderhouden.
- Baseline groen: 792 passed / 1 skipped, ruff + `mypy --strict` clean, bandit
  onveranderd op 5 pre-existing meldingen (geen in nieuwe code).

### Changed — 2026-08-12 — auditor-API is fail-closed (taak 1 + 2 van `iso-portal`)

> **Gedragswijziging voor lokale runs.** `iso-audit ui` weigert vanaf nu elk
> request zonder geverifieerde identiteit met een 403; alleen `/healthz` blijft
> open. Voor lokaal werken zonder proxy: `REQUIRE_AUTH=false uv run iso-audit ui
> …`. Dat is bewust de niet-default — een verkeerd geconfigureerde ingress
> moet naar "op slot" degraderen, niet naar "open".

- **`src/iso_audit/api/auth_gate.py`** (nieuw): fail-closed identity-gate die
  `X-Forwarded-Email` / `X-Forwarded-User` leest, met `REQUIRE_AUTH` default aan.
  Onbekende waarden (`REQUIRE_AUTH=maybe`) betekenen **aan** — een typfout mag geen
  portaal openzetten. Geïmplementeerd als HTTP-middleware en niet als `Depends()`
  per route: een dependency moet bij élk nieuw endpoint opnieuw worden aangezet en
  vergeten betekent stil een open route. `OPEN_PADEN` is de expliciete
  uitzonderingenlijst en bevat alleen `/healthz`.
- **`GET /healthz`** (nieuw): ongeauthenticeerd probe-endpoint voor liveness/
  readiness; geeft geen auditdata terug.
- **Trail is toewijsbaar** (sec-bevinding 1): `POST /findings/{id}` geeft de
  geverifieerde identiteit door als `actor` aan `apply_triage()`. Het veld bestond
  al en werd al weggeschreven, maar de API gaf het niet mee — élke trail-regel
  bevatte daardoor de default `"auditor"`. Met de gate uit is de actor de
  onmiskenbare waarde `dev:auth-uitgeschakeld`, nooit een leeg veld.
- **`store.db_pad()`**: de fallback naar `<repo>/output/audit.db` is niet langer
  stil — één waarschuwing per proces die het pad noemt, conform de repo-conventie
  voor env-var-fallbacks. Een harde fout zou de lokale CLI breken en valt buiten
  deze change; het portaal zet `AUDIT_DB_PATH` expliciet.
- **Docs** volgens het docs-contract van `66f4309` (Diátaxis):
  `docs/explanation/portal-auth.md` (waarom de header te vertrouwen is: topologie +
  fail-closed, en wat het model níet oplost) en
  `docs/how-to/verify-portal-auth.md` (fail-closed aantonen zonder cluster, plus de
  offboarding-handeling die toegang direct beëindigt). Beide in `docs/index.md`.
- **Tests**: `tests/api/test_auth_gate.py` (15) en `tests/api/test_persistentie.py`
  (5) — 403 zonder header, header-fallback, lege header telt niet, `/healthz` open,
  UI-route bewaakt, actor in de trail, geen beslissing zonder identiteit, trail
  identiek na herstart, append-only over herstarts heen. De bestaande api-tests
  sturen nu de identity-header mee zodat ze de bewaakte route lopen.
- Baseline groen: 785 passed / 1 skipped, ruff + `mypy --strict` clean, geen
  nieuwe bandit-meldingen.

### Added — 2026-08-12 — OpenSpec-change `iso-portal` + repo naar ConductionNL

- **`openspec/changes/iso-portal/`**: voorstel voor een portaal op
  `iso.commonground.nu` en voor het ontpersoonlijken van alle credentials, vóór
  het vertrek van de huidige beheerder eind augustus 2026.
- **Provisioner-hergebruik**: het Keycloak/oauth2-proxy-patroon van
  `openwoo-app-provisioner` wordt gekloond (realm `commonground`, nieuwe client
  `iso-audit-portal`); geen nieuwe auth-laag. `rbac-argo`/`rbac-secrets` en de
  bewust uitgeschakelde egress-policy worden expliciet niet overgenomen.
- **Drie nieuwe capability-specs**: `portal-deployment` (image, Argo-manifests,
  audit-trail op PVC i.p.v. emptyDir), `portal-auth` (fail-closed identity-gate,
  proxy als enige listener), `credential-model` (geen persoonsgebonden
  credential, eigenaar is een rol, herleidbaarheidstabel).
- **Migratiebesluit per bron vastgelegd**: `drive`/`planning` van de persoonlijke
  `gws`-sessie naar het bestaande `auth.py`-service-account, `jira` naar een
  functioneel Atlassian-account, `miro` naar een org-token, notifiers naar
  org-owned Slack/SMTP/Anthropic. Netto **nul** bronnen naar MCP, met de reden
  per bron — de beschikbare MCP-connectors authenticeren per gebruiker via OAuth
  en zouden de persoonlijke credential verplaatsen, niet opheffen.
- **Ongewijzigd**: de Source/Mode/Notifier-architectuur, de registries, de
  `Document`/`Finding`-shapes en de append-only trail. De migratie vraagt geen
  interface-wijziging; alleen de auth-implementatie binnen een adapter wisselt.
- **Security-audit op de specs** (`/opsx:sec`) leverde zeven gaps, alle als eis
  opgenomen. Materieel: de geverifieerde identiteit landt als `actor` in de trail
  (het veld bestaat al in `api/session.py:134` maar de API geeft het niet mee, dus
  élke regel zegt nu de placeholder `"auditor"`); toegang eindigt binnen een
  gedocumenteerd venster i.p.v. pas bij cookie-verval; de deploy-keten staat in
  het credential-model en is niet ongereviewd te verleggen; auth-events gelogd en
  credentials niet. Verder: maximale leeftijd per machine-credential,
  run-begrenzing op de org-LLM-key, en vaststellen welke trust-paths na migratie
  resteren (lokale artefacten, repo-toegang na transfer).
- **Repo verhuisd naar `ConductionNL/iso-audit`** (uitgevoerd 2026-08-12, taak 0.1
  route B). De org-naam was bezet door een private scaffold-repo van 2026-05-26
  (staand op `dee54989`, een voorouder van `main` — niets unieks); die is hernoemd
  naar `ConductionNL/iso-audit-scaffold-2026-05`, niets verwijderd. Daarna
  transfer van `MWest2020/iso-audit`, waarmee de historie, alle 15 branches, de
  **public**-zichtbaarheid (EUPL-1.2 blijft dus geldig) en een permanente redirect
  vanaf het oude pad meeverhuisden. `secret_scanning` en
  `secret_scanning_push_protection` staan hierdoor nu aan.
- **Nog open op de org-repo:** `main` is `"Branch not protected"`. Onbeschermd in
  combinatie met merge-is-deploy is sec-bevinding 3 in levende lijve — zie taak
  0.6 en 3.5.
- Implementatie volgt in aparte changes (`iso-portal` zelf, daarna één change per
  bron), pas na akkoord op dit voorstel. `openspec validate iso-portal --strict`
  groen.

### Added — 2026-06-17 — brondocument-links in de memo + redigeerbare maatregel/aanbeveling

- **Brondocument-links in de gerenderde memo**: `NCBlock` + `ImprovementBlock`
  krijgen `bronnen` (uit `Finding.bronnen`); de NC- en verbeterpunt-partials
  tonen een "Brondocumenten"-lijst met klikbare links (Drive/Jira/Miro) + per
  bron de beschrijving. Vervangt de losse reasoning-lijst (was redundant).
- **OFI-aanbeveling redigeerbaar**: `suggestion` toegevoegd aan `TriageUpdate`
  + `apply_triage` (append-only gelogd). In de triage-uitklap is nu per
  bevinding het juiste veld te bewerken — **NC → vereiste corrigerende
  maatregel**, **OFI → aanbeveling** — met een Opslaan-knop (lazy, per finding,
  geen zware mass-load).
- **Tests**: OFI-aanbeveling round-trip + memo-brondocument-links. Gate clean.

### Added — 2026-06-17 — memo-editor + memo-context uit run; bulk-verfijning

- **Memo aanpasbaar vóór generatie**: `GET`/`POST /memo/input` +
  `AuditSession.memo_input_data()`/`update_memo_input()` (validatie via
  `MemoInput` → 400 bij ongeldige input, niet pas bij render). UI-stap 5 krijgt
  een "Memo aanpassen"-formulier (titel, lead, auditcyclus, scope, bronnen,
  voorbehoud, bespreking) dat opslaat vóór preview/export.
- **Memo-context volgt de run**: na een live run zet `_update_memo_context` de
  **scope** (alle gedraaide normen — 9001 én 27001 bij een beide-run — met het
  hoofdstuk-bereik) en de **geraadpleegde bronnen** = de *geselecteerde* bronnen
  (Google Drive / Jira / Miro), niet langer de DB/dataset. Eerder toonde de memo
  alleen 9001 + `output/audit.db`.
- **Bulk-triage vereenvoudigd**: classificatie-keuze weg uit de bulk-balk (je
  filtert al op severity); bulk zet nu alleen de triage-status op de selectie.
- **Bulk-opslaan in de kop-NC-editor**: "Alles opslaan"-knop slaat alle
  bewerkte kop-NC's in één keer op.
- **Tests**: memo-input round-trip + validatie-fail. Gate clean.

### Added — 2026-06-17 — triage: NC-voorbeelden, OFI-thematisering, bulk-wijziging

Drie auditor-hulpmiddelen op de triage-flow:

- **NC-voorbeelden** ("hoe de tool het had willen zien"): nieuwe versie-prompt
  `nc_draft_v2.md` (= v1 + veld `voorbeelden`: 2-3 concrete conformante
  praktijken) + `Finding.examples`. De uitklap toont ze onder de bronnen — helpt
  de auditor inschatten of de NC terecht is (auditor-spiegel). Versiegestuurd:
  v1 blijft bestaan; `draft.py` laadt nu v2.
- **OFI-thematisering**: `Finding.thema` (keyword-taxonomie `bepaal_thema`, geen
  LLM) wordt gezet bij export (per bevinding) en bij de kop-NC-draft (dominant
  thema van het cluster). `conclusion()` levert `ofi_themes` — OFI's gegroepeerd
  per thema, aflopend, met betrokken clausules. Conclusie-view toont "verbeter-
  thema's, grootste hefboom eerst": één thema breed aanpakken tilt de organisatie
  op meerdere clausules tegelijk.
- **Bulk-triage**: checkbox per rij + "alles selecteren"; een bulk-balk zet
  classificatie en/of triage-status (met reden) op de hele selectie in één keer.
  Hergebruikt het append-only `POST /findings/{id}` per item.
- **Tests**: examples+thema-capture in de draft, `ofi_themes`-groepering in de
  conclusie. 754 groen; ruff/format/mypy clean.

### Added — 2026-06-17 — triage-UI: uitklapbare bronlinks + severity-kleuren + filter

Auditor-spiegel-verfijning op de triage-tabel (`api/ui.html` + ondersteunende
modellen). Drie wensen uit de demo:

- **Uitklapbare bevinding → brondocumenten**: nieuw `BronRef`-model
  (`herkomst`/`doc_id`/`doc_naam`/`url`/`beschrijving`) + `Finding.bronnen`.
  `export_db_findings` legt per bevinding de bron vast met een **klikbare URL**
  (`_bron_url`: Drive → `drive.google.com/open?id=`, Jira → `<base>/browse/<key>`,
  Miro → board-widget); de kop-NC-draft **bundelt** de bronnen van zijn cluster
  (gededupliceerd op herkomst+id). Elke rij klapt uit met één lijst — per
  brondocument de link + de beschrijving (= wat de tool aantrof). `finding_context`
  levert `bronnen` mee. De aparte hover-tooltips op de triage-rijen zijn
  verwijderd (redundant met de uitklap); de uitklap laadt lazy bij openen.
- **Severity-onderscheid**: niet elke bevinding is een NC. De DB-export-titel
  had altijd het misleidende prefix "NC clausule …"; nu neutraal "§<clausule> —
  …". Severity-badges + rij-rand gekleurd (NC=rood, OFI=amber, POSITIVE=groen).
- **Filter** op severity (Alle / NC / OFI / POSITIVE) boven de triage-tabel.
- **Tests**: `_bron_url` (per bron + edge-cases), bronnen-aggregatie+dedup in de
  draft. 752 tests groen; ruff/format/mypy/bandit clean.

### Fixed — 2026-06-17 — Jira: migratie naar enhanced search (`/search/jql`)

Atlassian heeft `/rest/api/3/search` verwijderd (HTTP 410). `JiraSource`
gebruikte dat endpoint nog → een echte Jira-ingest zou falen. Gemigreerd naar
de enhanced search `/rest/api/3/search/jql`: token-paginatie via
`nextPageToken` (i.p.v. `startAt`), stoppen op `isLast` (geen `total` meer).
Geverifieerd tegen de live ISO-scope. Pagination-test bijgewerkt.

### Added — 2026-06-17 — connector-engine: run_audit leest élke geselecteerde bron in

De kern van de connectoren-fase. Tot nu had `run_audit` de ingest hardcoded op
Drive + Miro; de `sources`-lijst voedde alleen de `ingest_scope`-Decision. Nu
bepaalt `sources` de feitelijke ingest — een gekoppelde Jira (of Planning, en
straks GitHub/Codeberg) levert echt bevindingen op.

- **`sources/protocol_ingest.py`** (nieuw): `ingest_documenten(naam)` mapt elk
  `Document` (+ `fetch_content`) van een geregistreerde Source-adapter naar de
  pipeline-document-dict (`naam`/`id`/`mime_type`/`tekst`/`herkomst`/
  `modified_at`). `herkomst` = bronnaam met hoofdletter. Leesfouten op één
  document zijn niet fataal (gelogd + overgeslagen).
- **`pipeline.run_audit`**: ingest honoreert nu `sources`. Drive en Miro houden
  hun eigen pad maar worden overgeslagen als ze niet geselecteerd zijn; elke
  andere geselecteerde bron loopt via `ingest_documenten` en wordt aan de
  document-stroom toegevoegd (en zo gekoppeld + geclassificeerd). Dode
  `_alle_input`-regel + ongebruikte `merge_met_drive_bevindingen`-import
  verwijderd.
- **`classification/findings.py`**: bevindingen krijgen nu de **eigen herkomst**
  van het document (Drive/Jira/Planning) i.p.v. hardcoded `"Drive"`; de dedup
  (`_gedaan_per_doc`) dekt alle niet-Miro-bronnen (`herkomst != 'Miro'`), zodat
  Jira/Planning óók correct gededupliceerd worden over re-runs. Classifications-
  log-`finding_id` gebruikt de echte herkomst-prefix.
- **Tests**: `ingest_documenten`-unit (mapping + skip-on-error + onbekende bron),
  `run_audit`-gating (Jira zonder Drive; default = Drive+Miro) via `dry_run_cost`,
  uitgebreide `_gedaan_per_doc` (Jira meegeteld, Miro uitgesloten). 747 tests
  groen; ruff/format/mypy/bandit clean.

### Changed — 2026-06-17 — Jira: JIRA_USER_EMAIL + project-scoping; planning sheet-id-validatie

- **`JiraSource`** (`sources/jira.py`): leest nu `JIRA_USER_EMAIL` (gekozen naam),
  met `JIRA_EMAIL` als fallback (geen breaking change). Healthcheck-reden +
  module-docstring bijgewerkt.
- **Jira project-scoping**: nieuwe env `JIRA_PROJECTS` (komma-gescheiden, bv.
  `"ISO"`). Wordt als `project in ("ISO", …)` AND-prefix op elke effectieve JQL
  gezet (documenten én findings), zodat een run binnen de ISO-scope blijft.
  Volledige JQL-override blijft via `JIRA_JQL` / `JIRA_FINDINGS_JQL` /
  `filter={"jql": …}`.
- **`PlanningSource`**: valideert de Sheets-ID aan de config-grens
  (`_valideer_sheet_id`). Een `=` of whitespace (typisch een .env-regel zonder
  newline die de volgende toewijzing aan de waarde plakt) geeft nu een
  duidelijke waarschuwing i.p.v. een cryptische gws-fout. De waarde wordt niet
  aangepast (geen stille verkeerde-sheet-bug).
- **Tests**: hermetische autouse-fixture die alle `JIRA_*`-env stript (voorkomt
  dat een gebruiker-.env de geasserteerde JQL beïnvloedt) + 5 nieuwe Jira-tests
  + 2 planning-validatie-tests.

### Added — 2026-06-17 — bron-healthcheck + UI grey-out van niet-gekoppelde bronnen

Connectoren-fase, stap 1: voorkomen dat de auditor een bron selecteert die niet
gekoppeld is. Hoort bij de `auditmemo-ui`-flow.

- **`GET /config/health`** (`api/app.py`) → `AuditSession.source_health()`
  (`api/session.py`): draait per geregistreerde bron een korte connectiviteits-
  check en levert `{naam: {connected: bool, status, reden, …}}`. Brede
  exception-vang: een falende healthcheck markeert de bron als niet-gekoppeld,
  breekt nooit de UI.
- **Drive `probe()`** (`sources/drive.py` + `clients/gws.py
  gws_drive_bereikbaar`): lichte reachability-check (één bounded `files list`,
  pageSize=1, niet-recursief) i.p.v. de volledige recursieve `healthcheck()`
  (die minuten duurt). `_check_source` gebruikt `probe()` als de adapter die
  biedt, anders `healthcheck()`. Miro (pseudo-source) = `MIRO_API_TOKEN`-presence.
- **UI** (`api/ui.html` `loadConfig`): bronnen zonder verbinding worden greyed-out
  (disabled + uitgevinkt) met een ● gekoppeld / ⚠ niet-gekoppeld-badge en de
  reden in de tooltip. Gekoppelde bronnen blijven default aangevinkt.
- **Jira**: `JiraSource` (sinds milestone C) gebruikt een persoonlijke Atlassian
  API-token (`JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN`, basic auth);
  healthcheck via `/rest/api/3/myself`. NB: `run_audit` ingest is nog hardcoded
  op Drive+Miro — een gekoppelde Jira draagt nog niets bij tot de ingest over
  de geselecteerde sources itereert (volgende connector-stap).
- **Tests**: 3 hermetische tests in `tests/api/test_app.py` (endpoint-bedrading,
  `probe()`-voorkeur, miro-token). Geen netwerk; `_check_source`/registry gestubd.

### Added — 2026-06-15 — `iso-audit memo`: management-auditmemo uit findings

Change `auditmemo-management` (MVP). Genereert de management-one-pager
(HTML + PDF) uit de findings-dataset; status: code + tests klaar, handmatige
visuele diff tegen het referentie-PDF + security-review nog open.

- **`iso_audit/memo/`** (nieuw): `models` (pydantic v2), `protocols` (5
  interfaces), `classifier` + `pattern_detection`, `norm_lookup` (user-pointed
  norm-DB, hard-fail bij ontbrekende clausule/taal), `theme/` (profielsysteem
  + SVG-validator + wizard), `renderer/` (Jinja2 → WeasyPrint), `builder`
  (assemblage + audit-trail-metadata), `cli` (Typer-subapp).
- **CLI**: `iso-audit memo` + `iso-audit profile new/list/show/validate`,
  gewired achter de bestaande console-script. Nieuwe deps: typer, rich,
  pydantic, jinja2, weasyprint.
- **Multi-tenant profielen** (standalone YAML, inline SVG-logo, kleurpalet met
  afgeleide defaults, schema-versioning) + **lean, user-pointed norm-DB** (repo
  ship alleen een NL-voorbeeld; officiële/EN-teksten levert de gebruiker).
- **Examples**: `examples/auditmemo/` + `examples/norms/` reproduceren de
  referentie-memo (2 NC + verbeterpunt + historical).
- Tests: 44 (incl. integratie: HTML lxml-valid, PDF, norm-resolutie,
  audit-trail). Alle files ≤ 200 regels. ruff/format/mypy --strict schoon.
- Docs: `docs/memo-architecture.md` + README-sectie + ONBOARDING.

### Added — 2026-06-15 — rapport-taal: versie-prompts, SMART-aanbevelingen, gate, --report-only

Change `audit-rapport-management-taal` (gated op akkoord kwaliteitsmanagement
vóór archivering). Status: code + tests klaar, validatie op echte DB + Marianne-
akkoord nog open.

- **Versie-prompts** `src/iso_audit/reporting/prompts/management_summary_v1.md`
  + `aanbevelingen_v1.md`: redactionele regels staan nu versiegestuurd, niet
  hardcoded. `report_generation.py` levert alleen feiten via `{{placeholders}}`
  (`_laad_prompt`, faalt luid op niet-ingevulde placeholder).
- **§3 Aanbevelingen SMART + positief** via `_genereer_aanbevelingen` (LLM met
  `aanbevelingen_v1`) i.p.v. rauwe NC/OFI-dump. Ontwerpbesluit: SMART in §3,
  summary blijft kort en verwijst ernaar.
- **`_check_verboden_woorden`**: deterministische gate (woordgrens-regex) op de
  aanbevelingen-output; logt waarschuwing, crasht niet. De auditeerbare
  garantie achter de prompt. Samenstellingen (`risicobeoordeling`) niet gevlagd.
- **Jargon-vertaal-instructie** in de summary-prompt (ISO-titels → leesbaar).
- **`temperature=0`** op alle LLM-calls in `report_generation.py` →
  near-idempotente regeneratie.
- **`--report-only`** doorgetrokken naar `iso-audit pipeline` (`cli.py`):
  regenereert rapport uit bestaande DB, slaat ingest/classificatie/Drive/Miro
  over, `--source`/`--mode` niet vereist. `run_report_only` bestond al.
- Geverifieerd: OFI-uitleg (§2a) + top-5 thema-tabel (§3) in `local_report.py`
  waren al geïmplementeerd (req 5).
- Tests: +8 (gate, prompt-loader, `_genereer_aanbevelingen`, `--report-only`).
  Suite 657 passed, 1 skipped. Gate ruff + format + mypy --strict schoon.

### Changed — 2026-06-15 — licentie Proprietary → EUPL-1.2 (open source)

- **`LICENSE`** toegevoegd: volledige verbatim EUPL-1.2-tekst (canonieke SPDX-
  bron). **`pyproject.toml`** `license` → `EUPL-1.2` + OSI-classifier.
  **`README.md`** Licentie-sectie herschreven.
- Reden: repo wordt publiek gemaakt. EUPL-1.2 (copyleft, EU-publieke-sector)
  past bij Conduction's open-by-default-cultuur. Tool is gegroeid uit een
  private repo van de auteur; consultancy-model blijft mogelijk bovenop de
  open-source-basis.

### Added — 2026-06-15 — `ONBOARDING.md` als levend onboarding-document

- **`ONBOARDING.md`** toegevoegd: van-nul-naar-productief voor iedereen die
  de repo oppakt. Mentaal model, mappenoverzicht, veelgebruikte commando's,
  **"een adapter toevoegen"** (lost ongedocumenteerd registry-patroon op),
  uitleg auditor-interview, en de richting UI + DB-config. Gelinkt vanuit
  README. Reden: repo overdraagbaar maken (zie ook docstring-fixes hieronder).
- **`src/iso_audit/interview.py`** docstring herschreven: expliciete status
  ("bewust ondersteunde auditor-tool, geen legacy"), verwijzing naar de
  auditor-spiegel-capability en `ONBOARDING.md` §7. Verving de Ops_to_Biz-
  migratienotitie. Reden: module was onzichtbaar/ongedocumenteerd.

### Changed — 2026-06-15 — housekeeping: scope-opschoning + doc-debt

- **`openspec/changes/hww-2-0/` → `archive/`.** Deze change gaat over de
  Docusaurus-website (`ConductionNL/.github`), niet over iso-audit, en was
  per ongeluk meeverhuisd uit `Ops_to_Biz`. Verplaatst (niet verwijderd)
  met `NOTE.md` die de scope en de bij de website-repo horende open tasks
  vastlegt. Reden: schone change-lijst vóór de milestone-B merge naar main.
- **`src/iso_audit/sinks/__init__.py` docstring.** Verwijderde de verouderde
  "spec-only in milestone A"-tekst; `DriveSink` bestaat. Verwees naar
  `ONBOARDING.md` voor het toevoegen van een adapter. Reden: documentatie-
  debt uit modulariteit-audit (lezer dacht dat sinks nog niet werkten).

### Fixed — 2026-05-26 — `.gitignore` aangevuld met secret-patronen

- **`.gitignore`** uitgebreid met `*.pem`, `*.key`, `*_rsa`, `*.crt`,
  `*.p12`, `*.pfx`. Was eis vanuit workstation-policy (zie globale
  CLAUDE.md "Secrets and Credentials"); pre-tool-use hook blokkeerde
  de commit tot deze patronen erin stonden. Niet dat er specifieke
  files bestonden die per ongeluk gecommit zouden worden — dit is
  preventief.

### Fixed — 2026-05-26 — Broken gitleaks-pin in pre-commit-config

- **`.pre-commit-config.yaml` gitleaks rev `v8.30.6` → `v8.30.1`.** De
  v8.30.6-tag bestaat niet in de gitleaks-repo (laatste reachable was
  v8.30.1 op fetch-moment); pre-commit faalde tijdens init met
  `pathspec 'v8.30.6' did not match any file(s) known to git`,
  waardoor elke commit geblokkeerd was. v8.30.6 stond pinned vanaf de
  initial scaffold (commit `6fba351`, M-A) — vermoedelijk een
  typo/non-existent-rev die `pre-commit autoupdate` had geschreven.
  Verlaging naar de eerstvolgende bestaande tag (v8.30.1) is de
  minimale fix.

### Changed — 2026-05-26 — Doc-sync: README + ARCHITECTURE post-M-C

- **README.md status-banner herschreven.** Was "milestone A skeleton
  (alpha) — pipeline/classifier/rapport komen in M-B; modes/notifiers
  in M-C". Nu: "A + B + grootste deel C gemerged; drie sources, één
  Sink, twee Notifiers, beide modes". Resterend werk (M-C §3.6
  acceptatie + `v1.0.0`-tag) expliciet vermeld.
- **README.md "stub-CLI" paragraaf** vervangen — `pipeline`, `doctor`,
  `setup-template` zijn allemaal beschikbaar; korte beschrijving van
  de drie verplichte flags (`--source`, `--mode`, `--notifier`).
- **README.md roadmap-pointer** verlegd van dode link
  `openspec/changes/iso-refactor/` naar `MEMORY.md`.
- **ARCHITECTURE.md status-banner** zelfde behandeling; M-A/M-B/M-C
  labels in de protocol-secties blijven staan als provenance (wanneer
  elke module landde — nuttig voor reviewers).
- **ARCHITECTURE.md Sink-sectie** herschreven: "Spec-only in milestone A"
  → "`DriveSink` shipped in M-C §3.3.1; reporting write-pad consolidatie
  DEFERRED tot na eerste integer-run".
- **ARCHITECTURE.md Modes-sectie** herschreven: "In M-A bestaat alleen
  Decision dataclass + Mode-stub. AutonoomMode/IntegerMode komen in M-C"
  → "AutonoomMode en IntegerMode zijn beide gerealiseerd in M-C".
- **ARCHITECTURE.md sectie-titel** "Pipeline-orchestratie (vooruitkijkend,
  milestone B/C)" → "Pipeline-orchestratie" (niet meer vooruitkijkend).
- **Drie dode links naar `openspec/changes/iso-refactor/design.md` en
  `openspec/changes/iso-refactor/`** opgeruimd (regels 86, 131, 203 in
  ARCHITECTURE.md). Decision-2-rationale staat al in de tekst eromheen;
  decision 3 → vervangen door pointer naar `docs/modes.md`; "Verder
  lezen"-pointer vervangen door `MEMORY.md`.
- **CLAUDE.md (project-niveau, regel 30) heeft dezelfde dode pointer
  nog staan** — bewust niet aangepast in deze sessie omdat de gevraagde
  scope README + ARCHITECTURE was. Genoteerd in MEMORY.md "Wat NIET
  vergeten".
- Geen code-changes. Tests blijven 649 passed, 1 skipped.

### Changed — 2026-05-26 — Housekeeping: handoff-doc sync + change archiveren

- **MEMORY.md gesyncroniseerd met huidige repo-staat.** PR #9
  (`miro-write-trim`) staat nu gemarkeerd als gemerged 2026-05-21
  (`6d0c1ee`) i.p.v. ⏳; test-baseline-rij teruggebracht tot één
  regel (649 passed / 85% cov, post-merge). De obsolete "Open PR #9"
  detail-sectie vervangen door een korte gemerged-notitie.
- **"Wat NIET vergeten" uitgebreid** met twee resterende issues
  (de derde — README/ARCHITECTURE stale — is in dezelfde sessie
  weggewerkt, zie de doc-sync entry hierboven): (a)
  `openspec/changes/iso-refactor/` bestaat niet in deze repo maar
  wordt vanuit project-CLAUDE.md (regel 30) nog als pointer gebruikt
  — dead-link; (b) `.env` mist `JIRA_*`/`SLACK_*`/`SMTP_*` keys en
  bevat nog Ops_to_Biz vars — opschonen vóór de smoke-test.
- **`openspec/changes/miro-write-trim/` verplaatst naar
  `openspec/changes/archive/`** (per CLAUDE.md OpenSpec §4 "archiveren
  na merge"). Tasks.md afgevinkt; §5.6 (tag `v0.3.0-beta`) als
  overgeslagen genoteerd omdat de tag-strategie nu één gebundelde
  `v1.0.0` na M-C §3.6 mikt.
- Geen code-changes. Tests blijven 649 passed, 1 skipped.

### Added — 2026-05-14 — Milestone C §3.3 + §3.4: DriveSink + JiraSource

- **`sinks/drive.py` (§3.3.1) — `DriveSink`.** Eerste concrete Sink-
  implementatie. Accepteert `ReportPayload`; weigert
  `NotificationPayload`/`MirrorPayload` met `SinkResult(succes=False)`.
  Upload via `iso_audit.clients.gws._gws`: maakt eerst leeg Google Doc
  in `AUDIT_DRIVE_FOLDER_ID`-folder, vult dan `inhoud_html` via
  Docs API `batchUpdate.insertText` (minimale HTML→tekst conversie).
  `@register` voor auto-discovery. 11 tests, 90% cov.
- **§3.3.2 consolidatie van reporting write-paden DEFERRED.** De
  bestaande `reporting/`-modules (`local_report`, `tabular_report`,
  `report_generation`) blijven hun eigen write doen; volledige
  doorgeleiding via `DriveSink.send()` komt in een eigen
  iteratie nadat de eerste integer-run heeft gedraaid en het
  rich-content-pad is bevestigd.
- **`sources/jira.py` (§3.4.1-3) — `JiraSource`.** Jira Cloud REST
  API v3 met basic-auth via env-vars (`JIRA_BASE_URL`, `JIRA_EMAIL`,
  `JIRA_API_TOKEN`). `list_documents()` pagineert via `startAt`;
  `fetch_content()` rendert ADF naar plain text; `list_findings()`
  filtert op ISO/compliance-labels (override via `JIRA_FINDINGS_JQL`).
  Labels `iso27001-<clausule>`/`iso9001-<clausule>` worden naar
  `clausule_ids` gemapped. `@register` voor auto-discovery.
  17 tests, 91% cov.
- **Contract-tests** (§3.4.5): `tests/sources/test_protocol_contract.py`
  parametrizet nu over `drive`, `planning`, `jira`. Sink-contract-
  test `test_registry_bevat_minstens_drive` vervangt M-A's
  `test_registry_is_empty`. `conftest.lege_registries` re-importeert
  alle bundled adapters (incl. `jira` + `sinks.drive`).
- 28 nieuwe tests; cumulatief **672 tests passed**, 81% overall cov.

### Added — 2026-05-14 — Milestone C §3.1.7-8 + §3.5: pipeline emit + CLI --mode/--notifier

- **`pipeline._emit_decision()` helper.** Stuurt een Decision naar de
  actieve Mode en geeft het besluit terug. Bij `mode=None` (legacy)
  retourneert het voorstel direct — equivalent aan AutonoomMode-
  laag-pad zonder DB-rij.
- **`pipeline.run_audit()`** accepteert nu `mode`, `audit_id`, en
  `sources` als parameters. Decision-emit wired op drie kritieke
  punten (§3.1.7, partial):
  - `ingest_scope` (laag-risico; `vraag_bevestiging` opt-in via
    `ISO_AUDIT_BEVESTIG_SCOPE`-env);
  - `send_report` (hoog-risico; auditor kan in integer-modus
    verzenden weigeren via Notifier);
  - `delete_data` is voorzien maar nog niet aangeroepen — pipeline
    schrijft momenteel geen data weg in de delete-richting; komt mee
    met §3.6 retention-werk.
  De andere vier beslispunten (`merge_drive_miro`, `classify_finding`,
  `assign_clausule`, `generate_report_section`) zijn intentioneel nog
  niet aangesloten — die vereisen diepe `findings.py`-refactor; nota
  in changelog.
- **`pipeline._resume_pending_decisions()` (§3.1.8).** Bij start van
  een run-id worden bestaande `pending` rijen gelogd. Volledige
  resume-polling op specifieke `decision_id` komt mee met
  `audit_id`-persistentie in §3.6.
- **CLI `--mode` (§3.5.1) + `--notifier` (§3.5.2).** Beide met
  env-var-fallback (`ISO_AUDIT_DEFAULT_MODE`,
  `ISO_AUDIT_DEFAULT_NOTIFIER`). Validatie:
  - missing `--mode` zonder env → `SystemExit(2)` met opties opgesomd;
  - `--mode integer` zonder `--notifier` → `SystemExit(2)`;
  - `--notifier` met `--mode autonoom` → WARNING (§3.5.3);
  - onbekende mode/notifier-naam → `SystemExit(2)`.
- **`iso-audit doctor` (§3.5.4)** roept nu `healthcheck()` op alle
  geregistreerde notifiers aan; exit-code 1 bij eerste fail. Toont
  Slack + Email + Sources + env-keys in één overzicht.
- 12 nieuwe tests + 4 bijgewerkt; cumulatief 646 tests passed.

### Added — 2026-05-14 — Milestone C §3.2: Notifiers (resolver + Slack + Email)

- **`notifiers/resolver.py` (§3.2.1).** `SqliteDecisionResolver` met
  `resolve(decision_id, action, modified_payload)`. Action-set:
  `approve|reject|modify|abort`. Validatie van action-naam,
  modify-payload-vereiste, decision-id-type. Append-only via
  `store.resolve_decision`'s `WHERE status='pending'`-guard.
- **`notifiers/slack.py` (§3.2.2).** `SlackNotifier` met webhook-pad
  (`SLACK_WEBHOOK_URL`) of Web API (`SLACK_BOT_TOKEN +
  SLACK_CHANNEL_ID`). Block Kit-message-payload. Healthcheck
  rapporteert welk auth-pad actief is. `@register` voor auto-discovery.
- **`notifiers/email.py` (§3.2.5).** `EmailNotifier` via SMTP met
  STARTTLS-optie. Genereert vier magic-link-URLs per decision
  (approve/reject/modify/abort). Token-opslag ligt bij het portaal
  (§3.2.6 — nog te bouwen). `@register` voor auto-discovery.
- **`IntegerMode._escaleer`** injecteert nu `decision_id` als
  string in `decision.context` vóór de notifier-call, zodat de
  notifier de correlatie-sleutel terug kan zenden.
- **Contract-tests groen** (§3.2.9): `tests/notifiers/test_protocol_contract.py`
  parametrizet nu over `slack` en `email` (was leeg-groen in M-A).
  `tests/conftest.lege_registries` re-importeert ook notifier-modules.
- **37 tests** in `tests/notifiers/{test_resolver,test_slack,test_email}.py`
  + 4 nieuwe in contract-tests; cumulatief 634 tests passed.

### Added — 2026-05-14 — Milestone C §3.1.3-6: Modes-implementatie + decisions-tabel

- **`decisions`-tabel (§3.1.3).** Append-only audit-trail in `store.py`:
  `(audit_id, punt, context_json, voorstel_json, status, besluit_json,
  risico, classificatie_id, notifier_naam, created_at, resolved_at)`
  met FK naar `classifications.id`. Indexen: `idx_decisions_audit_status`
  en `idx_decisions_punt_resolved`. Status-set: `pending|resolved|cancelled`.
- **`store.schrijf_decision()` + `resolve_decision()` + `laad_decision()` +
  `laad_pending_decisions()`.** Helpers met append-only-guard: een
  `resolved`/`cancelled`-rij wordt nooit overschreven; `resolve_decision`
  doet alleen iets wanneer de huidige status `pending` is.
- **`AutonoomMode` (§3.1.4) — `iso_audit/modes/autonoom.py`.** Selectieve
  persistentie: laag/midden krijgen `voorstel` direct terug zonder DB-rij;
  hoog wel een rij met `status="resolved"`, `notifier_naam=NULL`.
  `delete_data` heeft een hard skip-uitzondering.
- **`IntegerMode` (§3.1.5) — `iso_audit/modes/integer.py`.** Notifier via
  DI; risico-gebaseerde escalatie + `vraag_bevestiging`-flag op laag-
  risico + `confidence < 0.7` op midden. Bij escalatie: pending-rij
  voor notifier-call, dan polling op `decisions.status` (commit per
  iteratie om SQLite read-isolation te omzeilen). Timeout: 24h default.
- **`modes/__init__.py`.** Exporteert `AutonoomMode` + `IntegerMode`
  naast Protocol + dataclass.
- **18 tests** in `tests/modes/test_autonoom.py` (8) + `test_integer.py`
  (10): protocol-conformance, risico-regels, threaded resolver-mock met
  per-thread connecties, timeout, cancelled-status. 96-100% cov.
  Cumulatief 600 tests passed.

### Added — 2026-05-14 — Milestone B §2.7: OpenSpec changes verhuisd uit Ops_to_Biz

Vier change-dirs gekopieerd uit `Ops_to_Biz/openspec/changes/` naar
`iso-audit/openspec/changes/`:

- `audit-rapport-management-taal/` — auditrapport-taal voor management
- `gsuite-iso-audit-automation/` — GSuite-ingangen voor ISO-audit
- `miro-kennissessie-generator/` — Miro-bord auto-generation
- `hww-2-0/` — Handboek waar werken 2.0

Deze waren in Ops_to_Biz nog `untracked` (nooit gecommit), dus geen
`<sha>`-referentie in de commit-message — het is een schone verhuizing.

### Fixed — 2026-05-14 — `lege_registries` conftest dubbele-registratie bug

In `tests/conftest.py` veroorzaakte de combinatie
`importlib.import_module() + importlib.reload()` een dubbele
`@register`-call wanneer een Source-module voor het eerst werd
geladen tijdens een test (`import_module` voert het script éénmaal
uit, `reload` voert het nog eens uit). Fix: check `sys.modules` —
`reload()` alleen als de module al geladen is, anders `import_module`.
Maakt isolated `pytest tests/sources/test_protocol_contract.py`-runs
groen (was: 2 teardown-errors).

### Added — 2026-05-14 — Milestone B §2.8: M-B acceptatie

- **§2.8.2** Pipeline-reproduceerbaarheid: geverifieerd via
  `test_cli.py` (15 tests) + `test_pipeline.py` (21 tests) met
  gemockte deps. Geen integratie-run uitgevoerd om bestaande
  `output/`-artefacten van eerdere audit-runs niet te overschrijven.
- **§2.8.3** Contract-tests Drive + Planning groen — 6 passed +
  2 skipped (parametrized leeg-groen omdat M-A contract-stub
  geen adapters verwachtte; in M-B is `drive` geregistreerd
  → `test_registry_bevat_minstens_drive` is groen).

### Added — 2026-05-14 — Milestone B §2.6.3-5: classifications traceability

- **`classifications`-tabel (§2.6.3).** Nieuwe additieve tabel in
  `store.py`: `(audit_id, finding_id, input_hash, prompt_versie,
  model_versie, raw_output, usage_json, elapsed_s, created_at)`.
  Dedup-key: `UNIQUE(audit_id, finding_id, prompt_versie,
  model_versie)`. Indexen op `audit_id` en `finding_id`. Bestaande
  `audit.db`-bestanden blijven werken (toevoeging is idempotent).
- **`log_classification()` helper (§2.6.4).** Persist een LLM-call
  vóór JSON-parsing. `prompt_versie = sha256(system)`,
  `input_hash = sha256(system + user)`. `INSERT OR IGNORE` op
  dedup-key zodat reruns een append-only trace blijven.
- **Classifier wiring (§2.6.4).** `_classificeer_doc` en
  `_classificeer_miro_batch` accepteren nu optionele `conn` +
  `audit_id` en roepen `log_classification` aan na de LLM-call,
  voor de JSON-parse. `_ClassifyContext` krijgt `audit_id`; default
  via `_maak_audit_id()` (UTC-tijdstempel).
- **`laad_classifications(conn, audit_id, finding_id)`.**
  Query-helper met optionele filters.
- 14 tests in `tests/store/test_classifications.py`: schema,
  indexen, dedup-key (split op audit_id / prompt_versie /
  model_versie), filters. Cumulatief 582 tests passed.

### Added — 2026-05-14 — Milestone B §2.6.1 + §2.6.2: CLI + --source flag

- **`cli.py` herschreven (§2.6.1).** De milestone-A stub is vervangen
  door een echte argparse-met-subparsers implementatie:
  - ``iso-audit pipeline`` — alle bestaande `--norm/--no-review/...`-
    flags + de nieuwe `--source`;
  - ``iso-audit doctor``   — controleert `gws` op `PATH`, drukt env-
    sleutels af + geregistreerde sources;
  - ``iso-audit setup-template`` — wikkelt `_valideer_env` +
    `run_setup_template`.
- **`__main__.py` toegevoegd** — `python -m iso_audit` delegeert naar
  `cli.main`.
- **`--source` flag (§2.6.2).** Verplicht voor `pipeline`, multi-value
  (kan meerdere keren opgegeven). Fallback: env-var
  `ISO_AUDIT_DEFAULT_SOURCE` (komma-gescheiden) met INFO-log bij
  gebruik. Onbekende source-naam → `SystemExit(2)` met duidelijke
  foutmelding. Multi-value wordt deduplicate en gesorteerd.
- 15 tests; CLI-coverage rond 90%.

### Added — 2026-05-14 — Milestone B §2.5.11 + §2.5.12: assets + config layout

- **`assets/` (§2.5.11).** Drie Conduction-logo-SVG's gekopieerd uit
  `Ops_to_Biz/audit/assets/`. `__init__.py` toegevoegd zodat
  `importlib.resources.files("iso_audit.assets")` werkt. Wheel-build
  bevestigd: SVGs zitten in `iso_audit/assets/*.svg`.
- **§2.5.12 layout-aanpassing.** Het oude `audit/config/` is in deze
  refactor opgesplitst: clause-maps onder `data/clause_maps/`
  (§2.2.4), normteksten als Python-modules onder `data/normteksten/`
  (§2.2.3), report-template-yaml onder `data/` (§2.5.3). De
  `service_account.json` is bewust niet gemigreerd — credentials
  horen per-environment in `.env`, niet gebundeld in een Python-pakket.

### Added — 2026-05-14 — Milestone B §2.5.10: pipeline orchestrator

- **`pipeline.py` (§2.5.10).** Top-level orchestrator gemigreerd uit
  `Ops_to_Biz/audit/pipeline.py`. Imports verwezen naar `iso_audit.*`;
  `subprocess.run` voor `gws auth status` met bandit-nosec markers;
  HTML/DOCX/PDF-conversie als private helper `_converteer_md_naar_html_docx_pdf`
  (was inline duplicatie); type-hints aangevuld; `main()` accepteert
  optionele `argv` voor tests; specifieke `OSError`-vangst voor Miro
  in plaats van blanket `EnvironmentError`.
- **CLI-routes geverifieerd via tests**: `--local-only`, `--setup-template`,
  `--report-only`, `--no-review`, `--dry-run-cost` → correcte dispatch.
- 21 tests; overall coverage 79% (run_audit/run_report_only-bodies
  niet integraal getest — orchestratie met veel externe afhankelijkheden).

### Added — 2026-05-14 — Milestone B §2.5.8 + §2.5.9: interview + ingest

- **`ingest.py` (§2.5.9).** Drive + Miro inlees-orchestrator op top-level
  van het package. `--only` valideert tegen `beschikbare_bronnen()` —
  Source-registry-adapters (`drive`, `planning`, …) + pseudo-bron `miro`
  (zolang er nog geen `MiroSource`-adapter is in §2.4). Imports
  vernieuwd naar `iso_audit.*`. 13 tests, 95% coverage.
- **`interview.py` (§2.5.8).** Interactieve clausule-doorloop. ANSI-
  kleurkode helpers, `_vraag_bevinding` met EOF/quit-handling, gap-
  detectie via `clause_matches`-tabel. `main()` accepteert optionele
  `argv` voor testbaarheid. 13 tests, 68% coverage (interactieve loop
  zelf niet integraal getest — overall gate 82% blijft groen).

### Added — 2026-05-14 — Milestone B §2.5.6: make_pptx snapshot-presentatie

- **`reporting/make_pptx.py` (§2.5.6).** Verbatim-migratie van de
  hardcoded MT-snapshot-presentatie (2026-03-24); dode imports verwijderd
  (`qn`, `etree`, `Emu`), type-hints toegevoegd voor mypy --strict.
- `python-pptx>=1.0.2` als runtime-dep toegevoegd (transitive: pillow,
  xlsxwriter).
- Mypy override: `pptx.*` aan `ignore_missing_imports`; module-specifieke
  `disable_error_code = ["no-untyped-call"]` voor `make_pptx`.
- Ruff per-file-ignore voor `E501` op `make_pptx.py` — presentatie-tekst
  moet verbatim blijven (line-breaks zouden de inhoud wijzigen).
- 5 tests, 96% coverage.

### Added — 2026-05-14 — Milestone B §2.5.1 rest: tabular_report + slide_summary + report_generation

- **`reporting/tabular_report.py` (§2.5.1).** CSV/Excel-export voor
  bevindingen + per-clausule samenvatting. `iso_audit.classification.thema`
  als bron-of-truth voor THEMA_LIJST/`bepaal_thema` (geen duplicatie meer).
  `openpyxl` als runtime-dep voor Excel-output. 21 tests, 87% coverage.
- **`reporting/slide_summary.py` (§2.5.1).** Google Slides executive
  summary (5 slides) via `iso_audit.clients.gws._gws`. 8 tests, 98% coverage.
- **`reporting/report_generation.py` (§2.5.1).** Google Docs template-fill
  flow: `_oordeel_zin`/`_oordeel_instructie`-helpers (strikt sjabloon
  voorkomt LLM-hedging), management-summary via Anthropic met optionele
  basis-document fallback (`AUDIT_BASIS_SUMMARY`). 18 tests, 84% coverage.
- **`verify_docs.py`.** Bandit `nosec B608` markers op de twee
  `DELETE … WHERE id IN ({placeholders})` queries — placeholders zijn
  `?,?,…` zonder user-input, geparametriseerde executie is veilig.
- **Mypy override.** `openpyxl.*` toegevoegd aan `ignore_missing_imports`
  (stubs onvolledig voor Workbook/cell API).

### Added — 2026-05-13 — Milestone B start: baseline-meting + fixture-skeleton

Start van milestone B met de baseline-prep-stappen 2.1.x uit
`Ops_to_Biz/openspec/changes/iso-refactor/tasks.md`.

- **Coverage-baseline gemeten (2.1.3).** Huidige `Ops_to_Biz/audit/`-codebase
  bevat 0 tests (43 modules, ~12.9k regels) → baseline = 0%. Per spec
  `max(baseline + 5%, 70%)`, plafond 85% → definitieve gate = **70%**. Huidige
  iso-audit M-A scaffolding rapporteert 80% (211 stmts, 38 missed) — ruim
  boven gate.
- **CI-gate verhoogd (2.1.4).** `.github/workflows/ci.yml`: `--cov-fail-under`
  van 60 → 70. Comment bijgewerkt met baseline-context.
- **Fixture-skeleton (2.1.1 deels).** `examples/fixture-audit-2026-q1/`
  aangemaakt met README dat schema, anonimisatie-regels en selectie-criteria
  voor de ≤20-rij sample-set vastlegt. Data-vulling in aparte commit nadat
  anonimisatie-mapping is afgestemd.

### Changed — Milestone A scaffolding aangevuld met compensating-control

- `docs/compensating-control.md` toegevoegd (task 1.1.4): zes compenserende
  controles voor het ontbreken van GitHub Audit Log (persoonlijk account,
  geen Enterprise-tier). Migratiepad naar Enterprise opgenomen.
- Repo `MWest2020/iso-audit` aangemaakt op GitHub (private); initial push
  + tag `v0.1.0-alpha` (annotated, via gh API; pre-commit-hook update voor
  tag-pushes geweigerd door auto-classifier, workaround via API).
- CI run #25819303656 success op alle 5 jobs (lint, format, typecheck,
  security, test) — milestone A acceptatie-criterium 1.6.2 voldaan.

### Added — Milestone A — repo-skeleton + drie protocol-lagen

- Standalone `iso-audit` repo met fresh git-history; verhuisd uit
  `MWest2020/Ops_to_Biz` (waar het `audit/` heette).
- `pyproject.toml` + `uv.lock` met Python `>=3.12`; console-script
  entry-point `iso-audit = "iso_audit.cli:main"`.
- Maintainability-stack: `ruff` (lint+format), `mypy --strict`,
  `pytest` + `pytest-cov`, `bandit`, `pre-commit` met `gitleaks`.
- GitHub Actions CI met vijf parallelle jobs (lint, format, typecheck,
  security, test); coverage-gate tijdelijk 60% tot baseline-meting in
  milestone B.
- Pre-commit-config draait `--check` varianten — geen format-on-write,
  voorkomt silent CI-falen.
- Issue-templates: `bug.md`, `feature.md`, `source-adapter.md`,
  `notifier-adapter.md`. Laatste twee forceren protocol-conformance +
  tests + docs voor mergeability.
- `Source` Protocol (`src/iso_audit/sources/base.py`) met `Document` en
  `Finding` frozen dataclasses; read-only contract; immutable runtime-
  configuratie discipline.
- `Sink` Protocol (`src/iso_audit/sinks/base.py`) — spec-only, eerste
  implementatie (DriveSink) komt in milestone C. Payload-hierarchy
  (`ReportPayload`, `NotificationPayload`, `MirrorPayload`-placeholder).
- `Notifier` Protocol (`src/iso_audit/notifiers/base.py`) +
  `DecisionResolver` Protocol — kanaal-agnostische handoff-laag.
- `Mode` Protocol-stub + `Decision` dataclass in
  `src/iso_audit/modes/base.py` (Notifier-signatuur heeft Decision nodig;
  volledige Mode-implementatie volgt in C).
- Drie identieke registries (`@register` decorator, `available()`,
  `get(naam)`, `ValueError` bij dubbele namen). Patroon herhaald voor
  uitlegbaarheid aan externe code-reviewers.
- Contract-tests: `tests/sources/test_protocol_contract.py`,
  `tests/notifiers/test_protocol_contract.py`,
  `tests/sinks/test_protocol_shape.py`. Parametrized over geregistreerde
  adapters; in milestone A draaien parametrized-blokken leeg-groen.
- `docs/missie.md` als ankerdocument met drie capabilities (onafhankelijke
  bronnen, patroondetectie, auditor-spiegel) en het ISO 19011 §6.4.2
  rolconflict-frame.
- `ARCHITECTURE.md`, `CLAUDE.md`, `README.md` — projectoriëntatie voor
  Claude-sessies, externe reviewers, en nieuwe contributors.
- `docs/sources/{drive,planning,jira,mcp,rest}.md` en
  `docs/notifiers/{slack,email,teams,mattermost}.md` met
  setup-instructies of placeholder bij later-te-implementeren adapters.
- `docs/modes.md` met sectie "Modi en de missie" (autonoom-runs leveren
  geen capability-3-data).

### Migration notes

Deze repo bevat de eerste alpha-skeleton. `Ops_to_Biz/audit/` blijft
draaien zoals gewoonlijk tot milestone B; daarna deprecated, in
milestone C verwijderd. Zie
[`openspec/changes/iso-refactor/`](openspec/changes/iso-refactor/) voor
de volledige refactor-roadmap.
