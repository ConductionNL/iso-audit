# Tasks: nextcloud-bron

De verhuizing van de lezers staat vóór de adapter: andersom ontstaat er een tweede set die
daarna samengevoegd moet worden, en dat is precies de duplicatie die deze change wil vermijden.

## 1. Lezers verhuizen (geen gedragswijziging)

- [x] 1.1 `_tekst_uit_docx`, `_tekst_uit_xlsx`, `_tekst_uit_pptx`, `_tekst_uit_pdf`,
      `LeegDocumentError` en `GESCANDE_FORMATEN` naar `sources/tekst.py`
- [x] 1.2 `sources/drive.py` importeert ze daar; de Google-exports blijven Drive-specifiek
- [x] 1.3 Bestaande drive-tests blijven ongewijzigd draaien — dat is het bewijs dat de
      verhuizing niets veranderde

## 2. De adapter

- [x] 2.1 `sources/nextcloud.py` met `NextcloudSource`: `list_documents`, `fetch_content`,
      `probe`, geregistreerd via `@register`
- [x] 2.2 `PROPFIND` met `Depth: 1` per map, recursie in de adapter; geen `Depth: infinity`
- [x] 2.3 `getcontenttype` → dezelfde MIME-tabel als Drive; onbekend type gemeld, niet stil
- [x] 2.4 Prullenbak, versies en systeembestanden overslaan **met melding**
- [x] 2.5 Dekkingtelling zoals bij Drive: gezien, gelezen, per reden overgeslagen
- [x] 2.6 Basic auth met app-wachtwoord over TLS
- [x] 2.7 OpenDocument lezen (`odt`, `ods`, `odp`, `odg`) — stdlib `zipfile` + `content.xml`,
      geen `odfpy`. Toegevoegd 2026-08-24 nadat de eerste echte run 32 van de 168 bestanden op
      de canary als "onbekend type" meldde; op een LibreOffice-schijf is dat de hoofdmoot.
      DOCTYPE geweigerd en een grens op de **uitgepakte** `content.xml` (zip-bom)

## 3. Configuratie

- [x] 3.1 Bron-catalogus: basis-URL, gebruikersnaam, app-wachtwoord (geheim), pad(en)
- [ ] 3.2 Meerdere paden als lijst in de UI, zoals bij Drive — geen komma-gescheiden invoer.
      **Nog niet gedaan:** de adapter en de catalogus zijn er, maar het lijstveld in `ui.html`
      dat Drive sinds 2026-08-17 heeft, staat er voor Nextcloud nog niet
- [x] 3.3 `probe()` per pad, met eerlijke status per pad
- [x] 3.4 Test: ingetrokken wachtwoord levert "niet gekoppeld" met reden

## 4. Links

- [x] 4.1 `run_job._bron_url` uitbreiden met `nextcloud`
- [x] 4.2 Test: een bevinding uit Nextcloud krijgt een link

## 5. Testen tegen de echte server

- [x] 5.1 Component `nextcloud` in `scripts/preflight.py`, gedraaid tegen
      `canary-accept/nextcloud` (32.0.13): **9 documenten** (pdf, docx, xlsx, pptx, md, csv,
      3× txt), dekking 10 gezien / 9 gelezen. Vond twee fouten die de gestubde tests niet
      zagen: paden relatief aan de opgevraagde map i.p.v. de DAV-wortel, en "mogelijk staat de
      inhoud in tekstvakken" bij een lege `.txt`
- [ ] 5.2 **Aan de beheerder van die namespace:** `canary.accept.commonground.nu` wijst in DNS
      naar de nginx-ingress (81.24.6.82), terwijl de HTTPRoute aan de Envoy-gateway
      (81.24.11.239) hangt. Voor een preflight is een port-forward genoeg, maar dat is
      eromheen bouwen
- [x] 5.3 Testbestanden in `ISO-Audit-Test` op de canary: één per formaat, plus een leeg
      bestand en een verborgen bestand
- [ ] 5.4 End-to-end: een run met alleen Nextcloud levert documenten, dekking en bevindingen.
      **Nog niet gedaan** — dat vraagt de bron in het portaal geconfigureerd en een run met
      classificatiekosten

## 6. Documentatie

- [x] 6.1 `docs/reference/source-nextcloud.md`: configuratie, app-wachtwoord, wat er niet
      gelezen wordt
- [x] 6.2 `ARCHITECTURE.md`: Nextcloud in de bronnenlijst
- [ ] 6.3 CHANGELOG met de motivatie — inclusief wat deze change over het `Source`-protocol
      heeft aangetoond of weerlegd
