# Nextcloud als bron: WebDAV naast Drive

## Waarom

Er is vraag naar Nextcloud in plaats van Google Drive. Voor overheidsklanten is dat geen
smaakkwestie: documenten in een Amerikaanse cloud zijn bij een informatiebeveiligingsaudit zelf
een gespreksonderwerp, en Common Ground-partijen draaien Nextcloud.

Voor dit tool is het bovendien de eerste echte test van de eigen architectuur. `iso_audit.sources`
bestaat om bronnen inwisselbaar te maken; tot nu toe zijn Drive, Jira en Planning alle drie
Google- of Atlassian-specifiek en heeft niemand bewezen dat het protocol een wezenlijk andere
bron aankan. Een WebDAV-bron zonder wijziging aan de pipeline is dat bewijs — of de weerlegging.

**De testomgeving staat er al.** In het cluster draait `canary-accept/nextcloud`
(Nextcloud 32.0.13, met eigen postgres en TLS op `canary.accept.commonground.nu`), inclusief een
`nextcloud-secrets` met gebruikersnaam en wachtwoord. Daarmee is dit lokaal én in CI te testen
tegen een echte server in plaats van tegen een mock — precies wat de preflight-regel van
2026-08-22 vraagt.

## Wat er verandert

**Een `NextcloudSource` die het `Source`-protocol implementeert.** Dezelfde drie methoden als
de andere bronnen: `list_documents`, `fetch_content`, `probe`. WebDAV (`PROPFIND` voor de
listing, `GET` voor de inhoud) — een standaard die Nextcloud, ownCloud en elke andere
WebDAV-server delen, dus de adapter is niet Nextcloud-specifiek al heet hij zo.

**De tekstextractie wordt gedeeld.** De lezers voor PDF, docx, xlsx, pptx en de tekstformaten
staan nu in `sources/drive.py` en zijn daar niet Drive-specifiek: het zijn functies van bytes
naar tekst. Ze verhuizen naar een eigen module zodat beide bronnen ze gebruiken. Anders
ontstaat er een tweede set lezers die uit elkaar loopt — en dan is "wat leest het tool" een
vraag met twee antwoorden.

**Dekking werkt hetzelfde.** Gezien, gelezen, per reden overgeslagen, in het run-record. Dat is
een eigenschap van een bron, niet van Drive.

## Wat er niet verandert

**Geen schrijven.** Read-only, zoals elke bron in dit tool.

**Geen migratie.** Drive blijft; een audit kan beide bronnen tegelijk hebben. Dat is precies
wat het `Source`-protocol moet kunnen, en een klant die overstapt heeft een periode met allebei.

**Geen OCR.** Zelfde grens als bij Drive: een scan wordt gemeld als scan.

## Wat dit gaat blootleggen

Twee dingen die nu Drive-aannames zijn en het waarschijnlijk niet overleven:

1. **`bron_url` in `run_job._bron_url`** kent `drive`, `jira` en `miro` en bouwt een
   Google-URL. Een Nextcloud-document heeft een andere vorm.
2. **Snelkoppelingen, gedeelde mappen en versies** zijn Drive-begrippen. Nextcloud heeft eigen
   equivalenten (shares, trashbin) en die moeten expliciet worden overgeslagen of gevolgd —
   stil overslaan is precies wat op 2026-08-18 in Drive is rechtgezet.

## Capability-impact

Versterkt **onafhankelijke bronnen** in de letterlijke zin: het bewijst dat het bronprotocol
werkt voor een bron die niets met Google deelt, en het maakt het tool bruikbaar voor klanten die
geen Drive hebben.

Raakt de **auditor-spiegel** niet: dezelfde dekking, dezelfde meldingen, dezelfde trail.
