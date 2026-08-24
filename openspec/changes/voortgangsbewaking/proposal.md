# Voortgangsbewaking: van memo-actie naar aantoonbare opvolging

## Waarom

De managementmemo eindigt met acties: *wie* doet *wat*, *waar*, en *uiterlijk wanneer*. In het
Q2-memo staan er acht, met eigenaren (IT-lead, DevOps, KAM + MT) en termijnen (2026-Q3, 2026-Q4,
"doorlopend, 1e review 2026-Q3").

Daarna houdt het tool op. Er is geen scherm waar die acht acties staan, geen manier om te zien of
er iets mee gebeurd is, en geen koppeling naar het bewijs dat het gebeurd is. Bij de volgende
audit begint het opnieuw — de auditor zoekt met de hand of de actie van vorig kwartaal is
opgevolgd.

Voor ISO is dat juist de kern. **9001 §10.2** vraagt niet alleen om een corrigerende maatregel
maar om het vaststellen van de **doeltreffendheid** ervan. Een NC die is "opgelost" zonder bewijs
dat de maatregel werkt, is niet gesloten. Het Q2-memo zegt dat zelf, bij het derde verbeterpunt:
*"Peer-review-NC: sectie 4 (doeltreffendheid) + definitieve maatregelen afronden, status
sluiten."*

Er ligt bovendien al materiaal klaar. Jira is als bron gekoppeld en de opvolgpunten komen binnen
met herkomst `<bron>-opvolging` — bewust uitgesloten van de triage-werkset, want ze zijn geen
kandidaat-bevinding maar bewijs dát er opvolging plaatsvond. Dat is precies wat
voortgangsbewaking nodig heeft, en het wordt nu nergens getoond.

## Wat er verandert

**Een actie is een eersteklas ding.** De velden uit de memo-actietabel (`wat`, `wie`, `waar`,
`uiterlijk`) horen bij een bevinding en krijgen een status: open, in uitvoering, aangetoond,
vervallen. De statuswisseling is een handeling met identiteit en tijdstip in de append-only
trail, net als triage.

**Een scherm dat over audits heen kijkt.** Niet "de acties van deze run" maar "alle openstaande
acties, met hun termijn en hun eigenaar". Een audit is een moment; opvolging is een lijn. Het
scherm sorteert op wat het eerst verloopt en toont wat over de termijn is.

**Koppeling naar bewijs, niet naar een vinkje.** Een actie gaat naar "aangetoond" met een
verwijzing — een Jira-issue, een document uit het landschap, een bevinding uit een latere run.
Zonder verwijzing kan de status niet naar aangetoond. Dat is dezelfde regel als bij de
Bronbevrager: een bewering zonder bron is voor een audit waardeloos.

**Wat de planning-bron erbij doet.** De Planning-bron (Sheets) bevat de auditplanning: welke
clausules wanneer aan de beurt zijn. Die naast de openstaande acties leggen laat zien of een
clausule opnieuw wordt getoetst voordat de actie erop verlopen is — en dat is de vraag die een
auditor bij het plannen stelt.

**Een agent die bewaakt, niet beslist.** Optioneel bovenop het scherm: een agent die per actie
zoekt of er bewijs van opvolging in het corpus is bijgekomen — een nieuw document, een gesloten
Jira-issue, een positieve bevinding op dezelfde clausule. Hij **stelt voor**, met bronverwijzing;
de auditor zet de status. Zelfde grens als in `triage-agents`.

## Wat er niet verandert

- **Jira blijft buiten de triage.** Opvolgpunten zijn bewijs van opvolging, geen kandidaat-NC.
  Dat is een bewuste keuze en die staat niet ter discussie.
- **Geen tweede projectadministratie.** Dit tool wordt geen taakbeheer. De actie leeft hier omdat
  hij uit een auditbevinding komt; de uitvoering leeft in Jira of waar de organisatie hem al
  bijhoudt, en het tool verwijst ernaar.
- **De auditor sluit.** Een agent mag bewijs aandragen; "aangetoond" is een oordeel.

## Volgorde

Dit hangt aan `managementmemo-1a4`: zonder de actie-velden is er niets te bewaken. Het scherm kan
daarna, en de agent daar weer na — die is het minst nodig en het makkelijkst verkeerd te doen.
