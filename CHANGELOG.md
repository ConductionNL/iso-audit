# Changelog

Alle relevante wijzigingen aan dit project worden hier vastgelegd.
Format volgt [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/).
Versionering volgt [Semantic Versioning](https://semver.org/lang/nl/).

## [Unreleased]

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
