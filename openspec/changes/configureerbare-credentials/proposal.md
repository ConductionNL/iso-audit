# Change: configureerbare-credentials

## Why

Een auditor kan sinds `portal-dashboard` bronnen koppelen in de UI, maar de configuratie
is per bron los en er is geen enkele plek die vastlegt **welke** waarde gewonnen heeft en
**waarom**. Voor een ISO 27001-audit is dat het interessante deel: niet de waarde, maar de
herkomst. Nu kan niemand na een run aantonen of een bron op een cluster-Secret liep of op
iets dat iemand in de UI had ingevuld.

Daarbovenop dekken drie integraties hun eis niet:

- **Google Workspace** — impersonation bestaat niet in de code, dus een service-account
  kan alleen lezen wat expliciet met hem gedeeld is.
- **Jira** — geen expliciet service-account-veld; het label suggereert een persoon.
- **Anthropic** — alleen een API-key. Een Claude-abonnement kan niet, terwijl dat voor
  interactief gebruik de laagste drempel is.

Capability-raakvlak (`docs/explanation/missie.md`): dit versterkt **capability 1**
(onafhankelijke bronnen). Een bron die je niet kunt koppelen zonder cluster-beheerder is
niet onafhankelijk — hij is afhankelijk van wie het cluster beheert.

## What Changes

- Eén `Settings`-laag met vastgelegde precedence **env > config.yaml > UI** die per veld
  de herkomst meelevert, en die herkomst bij het starten logt.
- Geheime waarden krijgen een structurele bescherming: geen `__repr__` die de waarde
  toont, en één maskeerfunctie voor de UI.
- GWS-impersonation als optioneel veld; leeg betekent map-sharing zoals nu.
- Anthropic met twee modi: `api_key` en `sso` (het `ant`-CLI-profiel), plus modelkeuze.
- De prijzentabel gecorrigeerd — die is niet alleen oud maar fout, waardoor kostenregels
  in auditrapporten te laag uitvallen.
- `config.example.yaml` en `.env.example` met alle sleutels en placeholders.

## Scope-grens

- **Geen** wijziging aan Source/Mode/Notifier-protocollen of aan een adapter-interface.
  De adapters blijven env-vars lezen; `Settings` vult die omgeving.
- **Geen** nieuwe secret-opslag in deze change. De k8s-Secret-backend is een eigen change
  (`credential-opslag`), omdat die `automountServiceAccountToken` aanzet en dus apart
  geverifieerd moet worden.
- **Geen** wijziging aan de append-only trail, de dedup of de zeven beslispunten.
