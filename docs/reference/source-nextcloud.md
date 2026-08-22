---
status: current
last_reviewed: 2026-08-22
---

# Source: Nextcloud

Documenten uit een Nextcloud- of andere WebDAV-server, read-only. Dezelfde `Source`-adapter als
Drive, Jira en Planning: de pipeline weet niet dat het Nextcloud is.

## Configuratie

| Env-var | Verplicht | Beschrijving |
|---|---|---|
| `NEXTCLOUD_BASE_URL` | ja | `https://cloud.organisatie.nl` — zonder `/remote.php` erachter |
| `NEXTCLOUD_USER` | ja | Gebruikersnaam; bij voorkeur een functioneel account |
| `NEXTCLOUD_APP_PASSWORD` | ja | App-specifiek wachtwoord, **geen** gebruikerswachtwoord |
| `NEXTCLOUD_PATHS` | nee | Eén of meer mappen onder de gebruikersmap. Leeg = de hele map |

In het portaal staan de mappen als losse rijen; de komma is het opslagformaat van de env-var,
niet iets dat een auditor intypt.

**App-wachtwoord en geen gebruikerswachtwoord.** Nextcloud maakt ze aan onder Instellingen →
Beveiliging: per applicatie één credential, apart intrekbaar, zonder toegang tot de
webinterface. Zelfde argument als bij het Google-service-account — de auditcapability hoort
niet aan de sessie van een medewerker te hangen. Op de commandoregel:
`php occ user:add-app-password <gebruiker>`.

## Wat er gelezen wordt

Dezelfde lezers als Drive, uit `sources/tekst.py`: PDF (`pypdf`, geen OCR), `.docx` inclusief
tabellen, `.xlsx` per blad, `.pptx` per dia, en `text/plain`, markdown, HTML en CSV.

Geen Google-native types — die bestaan hier niet.

**Waarom gedeelde lezers:** het zijn functies van bytes naar tekst en ze raken Drive niet. Een
tweede set per bron maakt van "leest het tool xlsx-tabellen?" een vraag met twee antwoorden, die
na één wijziging uit elkaar lopen.

## Wat er niet gelezen wordt

Afbeeldingen, video en zip-archieven — met de reden in de melding en meegeteld in de dekking.

Plus drie Nextcloud-eigen mappen, die **gemeld** worden overgeslagen:

| map | waarom |
|---|---|
| `trashbin` | verwijderd is verwijderd |
| `versions` | alleen de huidige versie is bewijs; anders levert één document evenveel bevindingen als het versies heeft |
| `uploads` | onafgemaakte chunked uploads |

Verborgen bestanden (`.`-prefix) idem. Bij een nieuwe bron is de verleiding het grootst om "die
map hoort er niet bij" ongezegd te laten; dat is precies wat op 2026-08-18 in Drive is
rechtgezet.

## Hoe het leest: `PROPFIND` met `Depth: 1`

WebDAV, niet de Nextcloud-eigen OCS-API. Dat is een standaard, dus dezelfde adapter werkt tegen
ownCloud, Seafile met WebDAV of een Apache met `mod_dav`.

`Depth: infinity` zou de hele boom in één antwoord geven, maar veel servers weigeren dat en waar
het mag is een fout halverwege niet te lokaliseren in een antwoord van megabytes. Recursie per
map dus, net als de Drive-adapter.

## Een XML-antwoord met een DOCTYPE wordt geweigerd

Nagemeten op 2026-08-22 met Python 3.12.13 en expat 2.7.3: `xml.etree.ElementTree` weigert een
klassieke entity-expansie ("billion laughs") **niet** — een kleine invoer leverde 3000 tekens op,
en dat schaalt door.

De weigering zit daarom in een DOCTYPE-check vóór het parsen, plus een lengtegrens van 32 MB.
Entiteiten vereisen een DTD, en een WebDAV-antwoord heeft er nooit legitiem een. Dat is twee
regels en geen extra afhankelijkheid; `defusedxml` zou hetzelfde doen met meer oppervlak, en een
pakket toevoegen aan een repo die zelf onder ISO 27001-scope valt is een beslissing.

Het gaat niet om wantrouwen tegen Nextcloud, maar erom dat een gecompromitteerde of verkeerd
geconfigureerde server dit proces niet mag laten omvallen.

## Dekking

Zoals bij Drive: gezien, gelezen, en per reden overgeslagen — in het run-record.

`gezien = gelezen + overgeslagen` klopt altijd. Dat is de rekensom die een auditor maakt, en op
2026-08-22 klopte hij één keer niet: wat de WebDAV-client al oversloeg (verborgen bestanden) werd
in `overgeslagen` geteld maar niet in `gezien`.

## Getest tegen een echte server

`scripts/preflight.py --component nextcloud`, tegen `canary-accept/nextcloud` (Nextcloud
32.0.13) in het cluster. Die run vond twee fouten die de gestubde tests niet zagen:

1. **Paden waren relatief aan de opgevraagde map** in plaats van aan de DAV-wortel, waardoor de
   recursie in de verkeerde map zocht en submappen leeg leken.
2. **Een lege `.txt` kreeg de melding "mogelijk staat de inhoud in tekstvakken"** — over een
   bestand van nul bytes. De reden hangt nu af van het formaat.

Let op bij testen tegen de canary: `canary.accept.commonground.nu` wijst in DNS naar de
nginx-ingress (81.24.6.82), terwijl de HTTPRoute aan de Envoy-gateway (81.24.11.239) hangt. Een
`kubectl port-forward svc/nextcloud 18080:8080` omzeilt dat; het is een vraag aan de beheerder
van die namespace, niet iets om omheen te bouwen.
