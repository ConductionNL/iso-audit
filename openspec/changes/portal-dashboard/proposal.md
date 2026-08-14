# Proposal — portal-dashboard

## Why

Het portaal staat live sinds 2026-08-12, maar het is één scherm dat één auditsessie
kent. `create_app(session)` neemt letterlijk één `AuditSession` en `iso-audit ui`
verwacht één working-dir. Daarmee kun je een audit doen, maar je kunt er geen
auditpraktijk op draaien:

- **een nieuwe audit starten** betekent nu een directory op de PVC klaarzetten en de
  deployment-args aanpassen — dat is een beheeractie, geen auditorhandeling;
- **een lopende audit voortzetten** kan alleen als het precies die ene sessie is;
- **historie terugzoeken** kan niet: eerdere audits en memo's zijn onvindbaar zodra
  de sessie-dir is hergebruikt;
- **configuratie** zit verweven in hetzelfde scherm als triage, terwijl het een
  andere vraag beantwoordt ("staan de bronnen goed?") op een ander moment.

De eigenaar noemde alle drie de eerste punten als dagelijks gebruik. Zolang het
portaal één sessie kent, is het een demonstratie en geen werktuig.

**Capability-raking** (`docs/missie.md`): dit versterkt capability 3
(*auditor-spiegel*). De trail is nu toewijsbaar aan een mens, maar niet aan een
audit — je kunt niet terugkijken hoe een eerdere auditperiode tot zijn conclusies
kwam. Capability 1 wordt geraakt: de bron-scope staat vast zodra een run loopt — een
correctheidseis, geen wantrouwen jegens de auditor (zie `design.md`).

## What Changes

- **Audits worden eerste-klas.** Een audit is een directory met een manifest
  (`audit.json`: norm, periode, aangemaakt, aangemaakt door). De naam komt uit norm
  + periode die de auditor bij het aanmaken kiest, bijvoorbeeld `9001-2026-Q3` —
  voorspelbaar, sorteerbaar en leesbaar op schijf.
- **Runs worden vastgelegd, niet weggegooid.** Elke pipeline-run schrijft een regel
  in een append-only `runs.jsonl` binnen de audit: wie, wanneer, welke modus, norm,
  bronnen, hoofdstuk, en hoeveel kandidaten hij toevoegde.
- **Een tweede run vult aan.** Nieuwe kandidaten komen erbij; bestaande triage
  blijft staan. Deduplicatie is deterministisch in code (geen LLM) en overgeslagen
  duplicaten worden gelogd — niet stil weggelaten, in de geest van het bestaande
  `dropped`-spoor uit `auditmemo-curate`.
- **Dashboard als landingsscherm** met één regel per audit: norm + periode +
  status, triage-voortgang en of de memo klaar is, welke bronnen zijn geraadpleegd,
  en wie er als laatste aan werkte en wanneer.
- **Configuratie als eigen taak, door de auditor zelf te zetten.** Per bron gekoppeld
  of niet, met wat er ontbreekt, en koppelen/scope instellen in de UI. Geen cluster,
  geen beheerder — anders is het tool niet aan derden te leveren. De controle is
  registratie: elke wijziging append-only met identiteit, en elk run-record vermeldt
  de geraadpleegde bronnen.
- **Toegang blijft zoals hij is:** iedereen die inlogt ziet alle audits. Het
  audit-log legt vast wie wat deed. Geen tweede rechtenmodel naast Keycloak.

## Capabilities

### Added Capabilities

- `audit-registry` — audits en runs als eerste-klas, aanvullende runs met
  deterministische deduplicatie.
- `portal-dashboard` — overzicht van audits met de vier kolommen.
- `portal-config-view` — configuratie als losse taak die de auditor zelf zet.

### Modified Capabilities

- `audit-api` — routes worden audit-gescoped (`/audits`, `/audits/{id}/…`). Dit is
  een **breaking change** op de API. Bewust: er is één deployment, de versie is
  `0.1.0a…`, en een compatibiliteitslaag onderhouden voor een consument die niet
  bestaat is verspilling.

### Unmodified

De triage- en memo-motor blijft ongemoeid: `AuditSession`'s append-only gedrag,
`apply_triage`, `build_memo`, de renderer, `curate`, `recidive`. Ook de
Source/Mode/Notifier-architectuur en de fail-closed auth-gate blijven zoals ze
zijn. Deze change verandert *hoe je een sessie adresseert* en *wat je erover ziet*,
niet wat er binnen een sessie gebeurt.

## Scope-grens

**In scope:** de audit-registry, het dashboard, het configuratiescherm, en de
API-herstructurering die daarvoor nodig is.

**Buiten scope, expliciet:**

- **Meerdere mensen tegelijk in dezelfde audit.** Onbeperkt audits naast elkaar is
  bijna gratis zodra het portaal niet één sessie hard kent; twee schrijvers in
  dezelfde append-only trail is dat niet. Deze change levert één schrijver per
  audit, met een zichtbare waarschuwing als iemand anders actief is — geen
  vergrendeling en geen samenvoeging van gelijktijdige beslissingen.
- **Per-audit autorisatie.** Zou een eigen rechtenmodel naast Keycloak betekenen.
  Kan later fijnmazig via de bestaande `groups`-scope.
- **Credentials teruglezen.** Invoeren kan, uitlezen nooit: het scherm meldt
  "ingesteld" of "niet ingesteld" en de API geeft de waarde niet terug.
- **Een leesrol voor management.** Niet genoemd als dagelijks gebruik; toevoegen
  vraagt de autorisatielaag die hierboven buiten scope staat.
- **Automatische migratie van de bestaande sessie-dir.** Data verplaatsen doet een
  mens, met een gedocumenteerde eenmalige stap.
