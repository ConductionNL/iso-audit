# Credential-rotatie zonder clusterbeheerder

## Waarom

De precedence-regel uit `configureerbare-credentials` zegt: **environment verslaat de UI**,
zonder uitzondering. Dat is goed voor de vraag die hij beantwoordt — een deployment mag
nooit stil een via-de-UI ingevulde waarde gebruiken — maar hij breekt op een geval dat
zeker gaat gebeuren: **een credential die roteert.**

Een Jira-token, een Miro-token of een Anthropic-key verloopt, wordt ingetrokken, of moet
vervangen worden na een incident. Komt die waarde uit een cluster-Secret, dan kan de
auditor hem niet vervangen. Er is dan een clusterbeheerder nodig — en dat is precies de
persoonsafhankelijkheid die dit hele traject wegneemt. Na het vertrek van de huidige
beheerder (eind augustus 2026) is er niemand die dat "even doet".

Aanleiding was concreet: een auditor probeerde in het configuratiescherm een
service-account-key in te vullen en kon het veld niet gebruiken, omdat de oude waarde uit
de omgeving kwam. De maatregel die dat blokkeerde was juist bedoeld om een ander probleem
op te lossen (een save die slaagde en niets deed), maar liet de auditor zonder uitweg.

## Wat er verandert

De UI mag een omgevingswaarde overschrijven, maar **alleen als expliciete handeling**.

Let op de rationale van de oorspronkelijke regel: *"environment bovenaan betekent dat een
deployment nooit **stil** een via-de-UI ingevulde waarde gebruikt."* Het probleem dat die
regel oplost is **stilte**, niet dat de UI wint. Een expliciete, geregistreerde
overschrijving is niet stil. Daarom blijft de rationale overeind terwijl de dode weg
verdwijnt:

- precedence wordt **`ui-override` > env > `config.yaml` > ui > default**;
- `ui-override` is een eigen herkomst, náást `ui` — het verschil tussen "hier ingevuld" en
  "hier ingevuld terwijl een beheerder iets anders had gezet" is precies wat een auditor
  achteraf moet kunnen zien;
- overschrijven vraagt een aparte keuze (`?overschrijf=true`), en die keuze staat
  append-only in `bron_config_log.jsonl` met `overschrijft_omgeving: true`;
- het portaal meldt wanneer de omgeving **sindsdien is gewijzigd** — het rotatiegeval
  waarin een beheerder het Secret vervangt en de overschrijving die nieuwe waarde
  blokkeert. Vergelijking gaat via een hash; waarden worden nooit getoond;
- terugdraaien is het veld leegmaken; dan geldt de omgevingswaarde weer.

Uniform voor alle velden, niet alleen voor geheimen. Eén regel is beter uit te leggen en
te bewaken dan twee, en ook een map-ID of een adres kan verouderen.

## Capability-raakvlak

Versterkt **capability 1 (onafhankelijke bronnen)**. Een bron die je niet kunt herstellen
zonder clusterbeheerder is niet onafhankelijk — en een credential die roteert maakt van
"kunnen koppelen" een terugkerende handeling, niet een eenmalige.

Raakt **auditeerbaarheid** niet negatief: de overschrijving is zichtbaar in de herkomst,
staat in het append-only spoor met wie en wanneer, en de UI-store is in het cluster zelf
een Secret (`iso-audit-portal-config`). Er komt dus geen credential buiten een Secret te
staan.

## Wat hier niet in zit

- **Geen sleutelbeheer of encryptielaag.** Dit blijft geen secret-manager.
- **Geen automatische rotatie.** Het portaal detecteert een gewijzigde omgeving en meldt
  die; het kiest niet zelf welke waarde beter is.
- **Geen rolonderscheid.** Iedereen die het portaal mag configureren mag overschrijven.
  Wie het deed staat in het spoor. Een rollenmodel is een aparte change.
