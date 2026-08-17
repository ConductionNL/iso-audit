# Tasks: drive-locaties-ui

- [ ] 1.1 `clients/google_drive.py`: `drive_locatie_info(id)` — één `files.get` met
      `id,name,mimeType,driveId` en `supportsAllDrives`; geeft `None` bij een fout in plaats
      van te raisen, want de naam is comfort en geen voorwaarde
- [ ] 1.2 `clients/google_drive.py`: de bestaande bounded `files.list` ook het aantal en de
      aanwezigheid van submappen laten teruggeven, zodat "leeg" en "alleen submappen" uit
      elkaar te houden zijn
- [ ] 2.1 `sources/drive.py`: `probe()` geeft per locatie een record — id, naam, soort
      (shared-drive / map / geen-map / onbekend), aantal, en een reden bij een waarschuwing
- [ ] 2.2 `sources/drive.py`: de bron geldt als gekoppeld zodra één locatie bestanden
      oplevert; een lege locatie maakt de bron niet rood maar levert wel een waarschuwing
- [ ] 2.3 Geen recursieve enumeratie in `probe()`/`healthcheck()` — bewaken met een test die
      faalt als het aantal API-aanroepen met de mapdiepte meegroeit
- [ ] 3.1 `api/bron_catalogus.py`: `Veld` krijgt een soort `lijst`; alleen het Drive-veld
      gebruikt hem. Geen generiek herhaalbaar-veld-mechaniek
- [ ] 3.2 `api/bron_config.py`: lijst ⇄ komma-gescheiden string, met normalisatie via
      `uit_url` en ontdubbeling bij het toevoegen
- [ ] 4.1 `api/ui.html`: rijen met naam, soort, status en verwijderknop; één toevoegveld dat
      URL of ID accepteert. De auditor typt nooit een komma
- [ ] 4.2 `api/ui.html`: waarschuwingsregel per locatie, met oorzaak alleen wanneer die is
      vastgesteld
- [ ] 4.3 Contract-test in `tests/api/test_ui_contract.py`: geen komma-instructie meer in de
      hint, wél een toevoeg- en verwijderpad
- [ ] 5.1 Tests: bestand-ID levert een waarschuwing en telt niet als gekoppeld
- [ ] 5.2 Tests: lege map levert een waarschuwing zonder beweerde oorzaak
- [ ] 5.3 Tests: één goede plus één lege locatie houdt de bron gekoppeld
- [ ] 5.4 Tests: toevoegen van een bestaande locatie geeft geen dubbele rij
- [ ] 5.5 Tests: `files.get` die faalt laat de rij staan met het ID en de markering onbekend
- [ ] 6.1 `docs/reference/source-drive.md` bijwerken: meerdere locaties, wat het getal
      betekent, en dat losse bestanden niet worden ondersteund
- [ ] 6.2 CHANGELOG-regel met de motivatie: onvindbare mogelijkheid plus valse groen
- [ ] 7.1 In het cluster verifiëren met twee locaties: de Shared Drive plus "Interne audits",
      en één bewust fout ID om de waarschuwing te zien
