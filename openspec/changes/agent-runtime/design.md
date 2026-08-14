# Design — agent-runtime

## Drie opties, en waarom deze

| | A. tool-runner in de pod | B. Managed Agents + self-hosted sandbox | C. Managed Agents + cloud |
|---|---|---|---|
| Wie draait de lus | wij, in-process | Anthropic | Anthropic |
| Waar draaien de tools | onze pod | onze pod (uitgaand pollen) | Anthropic-container |
| Waar staat het auditbewijs | PVC, blijft in cluster | PVC, blijft in cluster | Anthropic-container |
| Nieuwe infra | geen | worker-proces + environment-key | geen |
| Levering aan derden | werkt overal | vraagt een Anthropic-org | idem |

**C valt af.** Auditbewijs — beleidsdocumenten, ticketinhoud, bevindingen — in een door
Anthropic gehoste container plaatsen is een verwerkersvraag die dit project niet kan
beantwoorden zonder DPA-werk, en het maakt het tool onleverbaar aan een partij die dat niet
wil. Dat is geen technisch bezwaar maar een besluit dat niet aan de bouwer is.

**B is de interessante upgrade,** niet de eerste stap: de lus draait bij Anthropic terwijl
de tools in onze container blijven, via een worker die uitgaand pollt. Dat past op het
bestaande trust-model (NetworkPolicy laat alleen ingress uit `ingress-nginx` toe) en levert
sessies, geversioneerde configs en cron-achtige deployments zonder eigen scheduler. Prijs:
een tweede proces, een tweede credential-soort en een beta-platformafhankelijkheid.

**A is het kleinste dat werkt.** Geen nieuw platform, geen environment-key, geen tweede
proces, en te testen in de pod die er al staat. Ga naar B zodra er een concrete behoefte is
die A niet dekt — geplande autonome runs, of sessie-historie die we anders zelf bouwen.

## Waarom max_iterations en niet task_budget

`task_budget` is adviserend: het model krijgt een aftelling te zien en wordt geacht zich
in te houden. Voor een auditor is dat geen garantie. `max_iterations` stopt de lus
gegarandeerd, en het kostenplafond hieronder ook — bij overschrijding stopt hij en staat de
reden in de trail.

Bijkomend: `task_budget` hangt aan beta `task-budgets-2026-03-13`. De gepinde SDK
(0.102.0) typeert dat veld niet. Een adviserende grens toevoegen die ook nog een
beta-afhankelijkheid meebrengt, is de slechtste van de twee.

## Waarom de join niet van de agent is

`api/runs.py:dedup_sleutel` bepaalt op `(standard, clause, source, genormaliseerde titel)`
wat één bevinding is — deterministisch, geen LLM, geen drempel. Een auditor moet kunnen
uitleggen waarom twee bevindingen zijn samengevoegd; "een model vond ze hetzelfde" is geen
uitleg, en een drempel die vandaag 0.87 is en morgen 0.85 maakt oude runs onreproduceerbaar.

Daarom stelt de agent alleen voor. `voeg_toe_via_join` is een aparte functie zodat die
scheiding in de code te zien is en niet alleen in een docstring.

## Waarom geen tool schrijft

De trail is van de coordinator. Zou een tool zelf naar `findings.json` of `runs.jsonl`
schrijven, dan kan een bevinding de trail bereiken zonder door de join te gaan — en dan is
de trail geen bewijs meer maar een verzameling losse beweringen. Twee tests lezen de
broncode van elke tool en falen op elke schrijf-operatie.

## Waarom bewijs verplicht is

`stel_bevinding_voor` weigert een voorstel zonder document- of ticket-id. Dat is
capability 3 (de auditor-spiegel) in code: een observatie zonder bewijs is een vraag, en
een vraag hoort als vraag in het memo te staan — niet als bevinding.

## Kosten

Het kostenplafond gebruikt de gecorrigeerde `PRIJZEN`-tabel en logt de peildatum mee. Een
model zonder prijsregel levert geen stille nul: dat wordt gelogd, want een run die gratis
lijkt terwijl hij dat niet is, is een verkeerd auditrapport.
