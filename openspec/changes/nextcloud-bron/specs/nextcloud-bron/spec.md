# Spec — nextcloud-bron (nieuw)

## ADDED Requirements

### Requirement: Nextcloud is een bron zoals elke andere

De adapter MUST het `Source`-protocol implementeren: `list_documents`, `fetch_content` en
`probe`, met dezelfde `Document`-vorm als de andere bronnen.

De pipeline MUST NOT hoeven te weten dat het Nextcloud is.

Rationale: `iso_audit.sources` bestaat om bronnen inwisselbaar te maken, en dat is tot nu toe
niet bewezen — Drive, Jira en Planning zijn alle drie Google- of Atlassian-specifiek. Een bron
die niets met Google deelt en tóch zonder pipelinewijziging werkt, is het bewijs; lukt dat niet,
dan is dat een bevinding over de architectuur en geen detail van deze adapter.

#### Scenario: Run met Nextcloud als enige bron

- **WHEN** een audit alleen Nextcloud als bron heeft
- **THEN** levert de run documenten, dekking en bevindingen zoals met Drive

#### Scenario: Run met Drive én Nextcloud

- **WHEN** beide bronnen gekoppeld zijn
- **THEN** komen documenten uit allebei in hetzelfde landschap

### Requirement: Lezen gaat over WebDAV en niet over een productspecifieke API

De adapter MUST bestanden ophalen via WebDAV (`PROPFIND` voor de listing, `GET` voor de inhoud).

Rationale: WebDAV is een standaard die Nextcloud, ownCloud en andere servers delen, dus dezelfde
adapter werkt breder dan één product. De Nextcloud-eigen OCS-API zou het aan één product binden
zonder iets op te leveren dat hier nodig is. `Depth: infinity` blijft eruit: veel servers
weigeren het, en waar het mag is een fout halverwege één antwoord van megabytes niet te
lokaliseren.

#### Scenario: Map met submappen

- **WHEN** een gekoppelde map submappen bevat
- **THEN** worden die per niveau opgevraagd

### Requirement: De tekstextractie is gedeeld met de andere bronnen

Beide bronnen MUST dezelfde lezers gebruiken voor PDF, docx, xlsx, pptx en de tekstformaten.

Er MUST NOT een tweede set lezers per bron bestaan.

Rationale: die lezers zijn functies van bytes naar tekst en raken Drive niet. Een tweede set
maakt van "leest het tool xlsx-tabellen?" een vraag met twee antwoorden, die na één wijziging
uit elkaar lopen — precies het soort stille verschil waar de dekkingsmeldingen van 2026-08-18
voor bestaan.

#### Scenario: Dezelfde docx uit beide bronnen

- **WHEN** hetzelfde bestand via Drive en via Nextcloud wordt gelezen
- **THEN** levert het dezelfde tekst op

### Requirement: Wat niet gelezen wordt, wordt ook hier gemeld

De adapter MUST per overgeslagen categorie melden waarom, en die aantallen MUST in de dekking
van de run terechtkomen.

Prullenbak, versies en systeembestanden MUST NOT stil worden overgeslagen.

Rationale: dezelfde regel als bij Drive, en bij een nieuwe bron is de verleiding het grootst om
"die map hoort er niet bij" ongezegd te laten. Op 2026-08-18 bleek in Drive dat 92 bestanden zo
verdwenen; dat hoeft geen tweede keer.

#### Scenario: Prullenbak in de boom

- **WHEN** de adapter een prullenbak of versiemap tegenkomt
- **THEN** wordt die overgeslagen met een gemelde reden

### Requirement: Authenticatie met een intrekbaar app-wachtwoord

De adapter MUST met een app-specifiek wachtwoord kunnen werken en MUST NOT een
gebruikerswachtwoord vereisen.

Rationale: hetzelfde argument als bij het Google-service-account — de auditcapability hoort niet
aan de sessie van een medewerker te hangen. Een app-wachtwoord is apart intrekbaar en geeft geen
toegang tot de webinterface.

#### Scenario: Ingetrokken app-wachtwoord

- **WHEN** het app-wachtwoord is ingetrokken
- **THEN** meldt `probe()` dat de bron niet gekoppeld is, met de reden

### Requirement: Een document verwijst naar zijn plek in Nextcloud

Een bevinding uit deze bron MUST een link opleveren waarmee de auditor het document opent.

Rationale: `run_job._bron_url` kent nu alleen `drive`, `jira` en `miro` en bouwt een Google-URL.
Zonder uitbreiding krijgt een Nextcloud-bevinding geen link, en dan is "open het document zelf"
— de kern van hoe dit tool naar bewijs verwijst — niet te doen.

#### Scenario: Bevinding uit Nextcloud

- **WHEN** een bevinding op een Nextcloud-document berust
- **THEN** bevat de bronverwijzing een werkende link
