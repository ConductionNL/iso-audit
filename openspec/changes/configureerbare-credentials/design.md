# Design — configureerbare-credentials

## Waarom herkomst een eigenschap van de waarde is

De alternatieve opzet is een dict met waarden plus een tweede dict met herkomsten. Dat is
één administratie te veel: bij elke transformatie kan de herkomst wegvallen zonder dat een
test dat merkt. Door herkomst in hetzelfde object te zetten als de waarde
(`Waarde(waarde, bron)`) kan een veld niet gebruikt worden zonder dat zijn herkomst
meekomt.

## Waarom geen `__repr__` met de waarde

Een geheim dat in een f-string, een `assert`-melding of een stacktrace belandt, staat
daarna in een logbestand dat we niet meer opruimen. `bron_config.py` beschermt hier al
tegen door geheime velden nooit terug te geven; `Waarde` doet hetzelfde één laag dieper,
zodat het ook geldt voor code die nog niet bestaat.

Dit is het patroon dat `api/audit_log.log_event` al volgt: die neemt bewust alleen scalars
aan en ziet het request-object nooit, waardoor een credential er structureel niet in kan
komen.

## Waarom env boven yaml boven UI

De opdracht schrijft deze volgorde voor en hij is verdedigbaar: een deployment mag nooit
stil een waarde gebruiken die iemand in de UI heeft ingevuld. Omgekeerd zou een UI die
het manifest overruled betekenen dat een auditor de deployment kan wijzigen zonder dat het
in Git zichtbaar is.

`config.yaml` staat ertussen omdat het bedoeld is voor niet-geheime defaults die je wél in
een repo wil hebben — een Jira-adres, een modelkeuze. Staat er tóch een geheim in, dan
werkt het maar wordt het gemeld. Weigeren zou een derde partij die dit tool krijgt kunnen
blokkeren op een bestand dat hij zelf kan repareren; melden is genoeg.

## Anthropic: waarom sso zonder herbouw kan

Eerder is in dit project aangenomen dat een Claude-abonnement niet bruikbaar is voor de
classifier en dat SSO een tweede aanroeppad zou vragen. Dat was fout. De SDK lost
credentials op in de volgorde API-key → auth-token → CLI-profiel → workload identity →
default-profiel. Een kale client — precies wat `classification/findings.py`, `llm.py` en
`thema.py` al gebruiken — pikt een CLI-profiel automatisch op.

Wat dus nodig is: de CLI in het image, het profiel op de persistente volume zodat het een
herstart overleeft, en een loginflow die de browserstap buiten de pod houdt.

**De val.** Een gezette API-key-variabele verslaat het profiel altijd, ook als hij leeg is.
Bij modus `sso` moet de loader die variabele daarom actief verwijderen. Zonder dat faalt
een run op een credential die de auditor niet gekozen heeft, en de foutmelding wijst naar
Anthropic in plaats van naar de configuratie.

## Wat een subscription niet oplost

Een subscription is per definitie persoonsgebonden. Voor het doel van dit project — de
auditcapability losmaken van één persoon — is `sso` dus een werkbare tussenstap voor
interactief gebruik, geen eindstation. Een geplande of autonome run heeft een
org-workspace-key nodig: er is geen browser, en een refresh-token verloopt hard.

Dat betekent ook dat de latere agent-runtime in het cluster niet op `sso` kan draaien. De
org-key is daarvoor een voorwaarde, niet een verbetering.

## GWS-impersonation: wat het vraagt buiten deze repo

`auth.py` kent vandaag geen impersonation; het service-account leest wat expliciet met hem
gedeeld is. Impersonation toevoegen is een kleine codewijziging (`with_subject`) maar
vraagt dat een Workspace-super-admin domain-wide delegation autoriseert voor de client-ID
en de scopes. Zonder die autorisatie faalt elke call met `unauthorized_client`.

Daarom is het veld optioneel: leeg betekent map-sharing zoals nu. De verbindingstest maakt
het verschil zichtbaar in plaats van het te verbergen, zodat een auditor niet denkt dat een
bron gekoppeld is terwijl alleen de configuratie klopt.

## Prijzentabel: waarom dit een correctie is en geen verversing

De tabel in `classification/findings.py` noemt voor Haiku 4.5 tarieven die lager zijn dan
de werkelijke, en noemt twee modellen die niet meer actueel zijn. Elke kostenregel in een
auditrapport valt daardoor te laag uit. Een te lage kostenpost is schadelijker dan geen
kostenpost, omdat hij compleet lijkt.

De tabel krijgt daarom een peildatum, en een test die faalt zodra een kiesbaar model geen
prijsregel heeft. Prijzen veranderen buiten deze repo om; de test voorkomt niet dat ze
verouderen, maar wel dat een nieuw model stil zonder kosten gaat lopen.
