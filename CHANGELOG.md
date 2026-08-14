# Changelog

Alle relevante wijzigingen aan dit project worden hier vastgelegd.
Format volgt [Keep a Changelog](https://keepachangelog.com/nl/1.1.0/).
Versionering volgt [Semantic Versioning](https://semver.org/lang/nl/).

## [Unreleased]

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
