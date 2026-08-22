# Tasks: nextcloud-bron

De verhuizing van de lezers staat vóór de adapter: andersom ontstaat er een tweede set die
daarna samengevoegd moet worden, en dat is precies de duplicatie die deze change wil vermijden.

## 1. Lezers verhuizen (geen gedragswijziging)

- [ ] 1.1 `_tekst_uit_docx`, `_tekst_uit_xlsx`, `_tekst_uit_pptx`, `_tekst_uit_pdf`,
      `LeegDocumentError` en `GESCANDE_FORMATEN` naar `sources/tekst.py`
- [ ] 1.2 `sources/drive.py` importeert ze daar; de Google-exports blijven Drive-specifiek
- [ ] 1.3 Bestaande drive-tests blijven ongewijzigd draaien — dat is het bewijs dat de
      verhuizing niets veranderde

## 2. De adapter

- [ ] 2.1 `sources/nextcloud.py` met `NextcloudSource`: `list_documents`, `fetch_content`,
      `probe`, geregistreerd via `@register`
- [ ] 2.2 `PROPFIND` met `Depth: 1` per map, recursie in de adapter; geen `Depth: infinity`
- [ ] 2.3 `getcontenttype` → dezelfde MIME-tabel als Drive; onbekend type gemeld, niet stil
- [ ] 2.4 Prullenbak, versies en systeembestanden overslaan **met melding**
- [ ] 2.5 Dekkingtelling zoals bij Drive: gezien, gelezen, per reden overgeslagen
- [ ] 2.6 Basic auth met app-wachtwoord over TLS

## 3. Configuratie

- [ ] 3.1 Bron-catalogus: basis-URL, gebruikersnaam, app-wachtwoord (geheim), pad(en)
- [ ] 3.2 Meerdere paden als lijst in de UI, zoals bij Drive — geen komma-gescheiden invoer
- [ ] 3.3 `probe()` per pad, met eerlijke status per pad
- [ ] 3.4 Test: ingetrokken wachtwoord levert "niet gekoppeld" met reden

## 4. Links

- [ ] 4.1 `run_job._bron_url` uitbreiden met `nextcloud`
- [ ] 4.2 Test: een bevinding uit Nextcloud krijgt een link

## 5. Testen tegen de echte server

- [ ] 5.1 Component `nextcloud` in `scripts/preflight.py`, tegen `canary-accept/nextcloud`
      (Nextcloud 32.0.13)
- [ ] 5.2 **Aan de beheerder van die namespace:** `canary.accept.commonground.nu` wijst in DNS
      naar de nginx-ingress (81.24.6.82), terwijl de HTTPRoute aan de Envoy-gateway
      (81.24.11.239) hangt. Voor een preflight is een port-forward genoeg, maar dat is
      eromheen bouwen
- [ ] 5.3 Testbestanden in een eigen map op de canary: één per formaat, plus een scan en een
      leeg bestand
- [ ] 5.4 End-to-end: een run met alleen Nextcloud levert documenten, dekking en bevindingen

## 6. Documentatie

- [ ] 6.1 `docs/reference/source-nextcloud.md`: configuratie, app-wachtwoord, wat er niet
      gelezen wordt
- [ ] 6.2 `ARCHITECTURE.md`: Nextcloud in de bronnenlijst
- [ ] 6.3 CHANGELOG met de motivatie — inclusief wat deze change over het `Source`-protocol
      heeft aangetoond of weerlegd
