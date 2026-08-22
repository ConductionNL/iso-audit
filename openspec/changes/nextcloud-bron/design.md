# Design — nextcloud-bron

## WebDAV, niet de Nextcloud-API

Nextcloud heeft een eigen OCS-API, maar bestanden lezen gaat via WebDAV op
`/remote.php/dav/files/<gebruiker>/`. Dat is een standaard, en dat is hier het argument: een
WebDAV-adapter werkt ook tegen ownCloud, Seafile met WebDAV, en een gewone Apache met
`mod_dav`. De OCS-API zou de adapter aan één product binden zonder dat het iets oplevert dat we
nodig hebben.

`PROPFIND` met `Depth: 1` per map geeft naam, grootte, `getlastmodified` en `getcontenttype` —
alles wat `Document` nodig heeft. Recursie doet de adapter zelf, net als de Drive-adapter.

Overwogen en verworpen: `Depth: infinity`. Veel servers weigeren dat, en waar het mag levert het
één antwoord van megabytes op waarin een fout halverwege niet te lokaliseren is.

## Authenticatie: app-wachtwoord, geen gebruikerswachtwoord

Nextcloud kent app-specifieke wachtwoorden: per applicatie één credential, apart intrekbaar,
zonder toegang tot de webinterface. Dat is hier de juiste vorm — hetzelfde argument als bij het
Google-service-account: de auditcapability hoort niet aan de sessie van een medewerker te hangen.

Basic auth over TLS, met het app-wachtwoord als wachtwoord. Voor de canary-omgeving staat er een
`nextcloud-secrets` in de namespace; voor productie hoort het via het configuratiescherm, zoals
elke andere bron-credential.

## De lezers verhuizen

`sources/drive.py` bevat `_tekst_uit_docx`, `_tekst_uit_xlsx`, `_tekst_uit_pptx` en
`_tekst_uit_pdf`, plus `LeegDocumentError` en de regel dat een lege extractie een storing is.
Geen daarvan raakt Drive: het zijn functies van bytes naar tekst.

Ze verhuizen naar `sources/tekst.py`. Zonder die verhuizing krijgt Nextcloud een tweede set
lezers, en dan is "leest het tool xlsx-tabellen?" een vraag met twee antwoorden die na één
wijziging uit elkaar lopen. De Drive-adapter importeert ze uit de nieuwe plek; de bestaande
tests blijven gelden en bewijzen dat de verhuizing niets veranderde.

Wat **niet** meeverhuist: de Google-exports (Docs, Sheets, Slides). Die zijn Drive-specifiek.

## Wat Nextcloud heeft dat Drive niet heeft

| Nextcloud-begrip | behandeling |
|---|---|
| gedeelde map (share) | gewoon lezen; hij zit in de bestandsboom van de gebruiker |
| prullenbak (`trashbin`) | overslaan — verwijderd is verwijderd |
| versies (`versions`) | overslaan; alleen de huidige versie telt als bewijs |
| `.` -bestanden en systeemmappen | overslaan |

Elk van deze **gemeld**, niet stil overgeslagen. Dat is de regel uit `landschap-dekking`, en
juist bij een nieuwe bron is de verleiding groot om "die map hoort er niet bij" ongezegd te
laten.

## Testen tegen de echte server

`canary-accept/nextcloud` in het cluster: Nextcloud 32.0.13, TLS op
`canary.accept.commonground.nu`, credentials in `nextcloud-secrets`. Daar hoort een
preflight-component bij, zoals Drive en planning die hebben.

Let op: de DNS van die host wijst nu naar de nginx-ingress (81.24.6.82) en niet naar de
Envoy-gateway waar de HTTPRoute aan hangt. Voor een preflight is dat op te lossen met een
port-forward naar de service, maar het is een aanwijzing dat die omgeving nog niet af is — en
dat is een vraag aan de beheerder van die namespace, niet iets om omheen te bouwen.

## Wat er aan Drive-aannames sneuvelt

`run_job._bron_url` bouwt per herkomst een URL en kent alleen `drive`, `jira` en `miro`. Voor
Nextcloud is dat `<basis>/index.php/f/<fileid>`. Die functie is de plek waar een nieuwe bron
zich meldt; dat hij per bron een expliciete vorm heeft en geen "geheime mapping-logica" is
precies waarom hij uitbreidbaar is.
