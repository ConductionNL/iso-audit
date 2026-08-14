# Design — portal-dashboard

## Opslag: directories, geen nieuwe database

```
/var/lib/iso-audit/
  audits/
    9001-2026-Q3/
      audit.json          norm, periode, aangemaakt, aangemaakt_door
      findings.json       de werkset (bestaand formaat, ongewijzigd)
      triage_log.jsonl    append-only auditor-beslissingen (bestaand)
      runs.jsonl          append-only run-registratie (nieuw)
      memo-input.yaml     bestaand
      Auditmemo_management.pdf
    27001-2026-H2/
      …
  conduction.profile.yaml
  audit.db                bestaande SQLite (decisions, classifications)
```

Een audit is dus precies de sessie-dir die er nu al is, plus twee bestanden. Dat is
bewust: `AuditSession` hoeft niet te veranderen, alleen de manier waarop we hem
aanwijzen.

**Waarom geen index-tabel.** De vier dashboard-kolommen zijn allemaal uit de
bestanden af te leiden: norm en periode uit `audit.json`, triage-voortgang uit
`findings.json`, laatste actor en tijdstip uit de staart van `triage_log.jsonl`,
geraadpleegde bronnen uit `runs.jsonl`. Bij de verwachte omvang — één tot enkele
audits per jaar — is een directory-scan sneller te schrijven, te lezen en te
auditen dan een tweede waarheid die synchroon moet blijven. Een index is een
optimalisatie voor een probleem dat we niet hebben; komt die er ooit, dan is
`store.py` de plek.

## Runs vullen aan — en dedup is deterministisch

Een tweede run binnen dezelfde audit voegt kandidaten toe en laat bestaande triage
staan. Dat is wat de praktijk vraagt (Jira erbij zetten na een Drive-only run)
maar het vraagt een dedup-regel, anders triageert de auditor hetzelfde twee keer.

**Dedup-sleutel:** `(standard, clause, source, titel-genormaliseerd)`. Deterministisch
in code, geen LLM — conform de norm uit `auditmemo-curate`: "redactie in
versie-prompts, deterministische checks in code". Titel-normalisatie is lowercasing
plus whitespace-collaps; geen fuzzy matching, want een drempel die niemand kan
uitleggen hoort niet in een auditwerktuig.

**Overgeslagen duplicaten worden gelogd**, met de sleutel en het run-id, in
`runs.jsonl` bij het run-record. Niet stil weglaten: dat is dezelfde discipline als
het `dropped`-spoor bij curate. Een auditor moet kunnen zien dat run 2 dertig
kandidaten opleverde waarvan achttien al bekend waren.

**Wat een run níet doet:** bestaande `findings.json`-regels wijzigen. Toevoegen
alleen. Daarmee blijft de triage-trail als geheel geldig — een beslissing verwijst
naar een finding die niet onder haar voeten is veranderd.

## Eén schrijver per audit, zichtbaar in plaats van vergrendeld

Meerdere audits naast elkaar is gratis zodra de sessie niet meer hard vastzit.
Meerdere schrijvers in dezelfde append-only trail is dat niet: twee gelijktijdige
`apply_triage`-calls op dezelfde finding leveren twee geldige regels met een
onbepaalde uitkomst in `findings.json`.

Gekozen: een `.actief`-bestand per audit met identiteit en timestamp, verversd bij
elke mutatie. Is er een vers record (< 5 minuten) van iemand anders, dan **waarschuwt**
de UI zichtbaar. Geen slot.

Waarom niet vergrendelen: een slot dat blijft hangen na een gesloten tabblad is een
supportprobleem, en de kans dat twee auditors tegelijk dezelfde bevinding triageren
is klein terwijl de kosten van een vastgelopen audit groot zijn. Waarschuwen maakt
het probleem zichtbaar zonder een nieuwe faalmodus te introduceren. Dit is een
bewuste risico-acceptatie en hoort als zodanig in de spec, niet als stilte.

## API: audit-gescoped, en dat breekt de huidige UI

```
GET  /audits                      overzicht (de vier kolommen)
POST /audits                      aanmaken: norm + periode
GET  /audits/{id}                 manifest + samenvatting
GET  /audits/{id}/runs            run-historie
POST /audits/{id}/run/start       run starten binnen deze audit
GET  /audits/{id}/findings        …bestaande routes, nu gescoped
POST /audits/{id}/findings/{fid}
GET  /audits/{id}/trail
GET  /audits/{id}/memo/preview
GET  /config/health               ongewijzigd, audit-onafhankelijk
GET  /healthz                     ongewijzigd, buiten de auth-gate
```

`AuditSession` wordt per request geopend op basis van `{id}`, in plaats van één keer
bij het starten van de app. Dat is de kern van de change; alles daarboven is schermwerk.

**Breaking, bewust.** Er is één deployment, de versie is `0.1.0a…`, en een consument
buiten de eigen `ui.html` bestaat niet. Een compatibiliteitslaag onderhouden voor een
consument die niet bestaat is verspilling.

## Configuratie: de auditor zet het zelf

Het configuratiescherm laat de auditor bronnen koppelen en de scope instellen. Geen
cluster, geen manifest, geen beheerder.

**Dit corrigeert een eerder besluit in deze change.** Ik had het scherm alleen-lezen
gemaakt met als argument dat `sources/base.py` immutability eist en dat een auditor
anders "zijn eigen bewijsbasis kiest". Twee fouten:

1. Die regel eist immutability **na `__init__`** — een object-lifecycle-invariant zodat
   een Source niet halverwege een run van scope wisselt. Het is geen uitspraak over wie
   mag configureren of waar de config vandaan komt. Ik heb een engineering-invariant
   tot autorisatiebeleid gepromoveerd.
2. De dreiging bestaat niet. Bewijs bestaat of het bestaat niet. Een auditor kiest
   bronnen, die bronnen worden vastgelegd, en een ontbrekende bron valt een laag hoger
   op: een interne auditor wordt door een externe gecontroleerd en die staat onder
   toezicht.

Bovendien maakte het het tool onleverbaar. Configuratie die alleen via cluster-Secrets
kan, betekent dat elke derde partij een Kubernetes-beheerder nodig heeft om te
beginnen.

Wat er wél uit de immutability-regel volgt, en dat blijft staan: een
configuratiewijziging wordt geweigerd zolang er in die audit een run loopt. Dat is een
correctheidseis — een Source leest zijn config bij start en daarna niet meer, dus
halverwege wisselen levert een run waarvan de helft een andere scope had.

De controle is registratie, niet blokkade: elke configuratiewijziging append-only met
identiteit en tijdstip, en elk run-record vermeldt de geraadpleegde bronnen. Dat
laatste bestond al.

Credentials mogen ingevoerd worden maar worden nooit teruggegeven — "ingesteld" of
"niet ingesteld" volstaat. Invoeren moet kunnen, teruglezen hoeft nooit.


## Vastgelegde ontwerpbesluiten

1. **Audit-id uit norm + periode**, door de auditor gekozen bij aanmaken; het
   portaal slugificeert naar `<norm>-<periode>`. Botst de id, dan een leesbare fout
   in plaats van een suffix — twee audits met dezelfde norm en periode is bijna
   altijd een vergissing.
2. **Geen automatische migratie** van de bestaande `sessie/`-dir. Data verplaatsen
   doet een mens; het portaal verzint niet welke audit dat was.
3. **`runs.jsonl` is append-only**, net als de triage-trail. Een run die faalde
   blijft staan met zijn fout — dat is auditinformatie, geen ruis.
4. **Dashboard toont ook lege audits.** Een aangemaakte audit zonder run is een
   geldige toestand ("nog te starten") en hoort zichtbaar te zijn.

## Stack & grenzen

Geen nieuwe dependencies. FastAPI, pydantic en Jinja2 staan al in `pyproject.toml`.
Max 200 regels per file; de audit-registry wordt een eigen module
(`api/registry.py`) en niet nog een laag in `api/session.py`. `uv` blijft.

## Niet opgelost / aandachtspunten

- **`ui.html` wordt grotendeels herschreven.** Dat is het grootste stuk werk en het
  minst interessante; het is één bestand zonder build-stap en dat houden we zo.
- **Periode-notatie.** `2026-Q3` sorteert goed, `2026-H2` ook, maar vrije invoer als
  "najaar" breekt sortering. Te fixeren bij implementatie: een lichte validatie met
  een leesbare fout.
- **Wat is "status" van een audit?** Voorstel: afgeleid — `nieuw` (geen run),
  `loopt` (run gedaan, triage niet compleet), `memo-klaar` (triage compleet én memo
  gegenereerd). Geen apart statusveld dat kan gaan liegen tegen de bestanden.
