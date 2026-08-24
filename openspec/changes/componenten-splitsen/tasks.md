# Taken — componenten-splitsen

## 1. De graaf (eerst meten)

- [ ] 1.1 Import-graaf uit de code afleiden — welke module hangt aan welke
- [ ] 1.2 Gedeelde toestand in kaart: welke paden schrijven hetzelfde bestand of dezelfde tabel
      (`findings.json`, `audit.db`, `runs.jsonl`, `triage_log.jsonl`, `bron_config.json`)
- [ ] 1.3 Per gedeelde plek: hoeveel schrijvers, uit welke thread of welk verzoek
- [ ] 1.4 De graaf als artefact in de repo, met de opdracht die hem genereert
- [ ] 1.5 Controle die faalt als er een nieuwe gedeelde schrijver bijkomt zonder benoeming

## 2. Contracten en faalmodi

- [ ] 2.1 Per kandidaat-component: invoer, uitvoer, en wat de auditor ziet bij uitval
- [ ] 2.2 Inventariseren waar uitval nu stil is (`logger.warning` in een pad dat de auditor niet
      leest) — dat is de lijst met verborgen faalmodi
- [ ] 2.3 Elke stille faalmodus zichtbaar maken vóór de splitsing; anders verplaatst de
      splitsing hem alleen

## 3. Eerste splitsing: de rapportketen

- [ ] 3.1 Meting vooraf: geheugenpiek en duur van het portaalproces tijdens rapportgeneratie
- [ ] 3.2 Contract: werkset erin, bestanden eruit
- [ ] 3.3 Eigen deployment met eigen resource-limieten (de renderer heeft 2Gi, de API niet)
- [ ] 3.4 Uitval-gedrag: de run meldt dat het rapport ontbreekt, met de reden; bevindingen en
      dekking blijven kloppen
- [ ] 3.5 Meting achteraf, vergeleken met 3.1
- [ ] 3.6 Test: renderer uit, run draait, melding klopt

## 4. Beoordelen vóór de volgende stap

- [ ] 4.1 Wat leverde de eerste splitsing op, en wat kostte hij (uitrol, foutzoeken, latency)
- [ ] 4.2 Besluit of de assistent de volgende is, of dat het bij één blijft
- [ ] 4.3 **Niet** doorpakken zonder dit besluit

## 5. De werkset (apart, later)

- [ ] 5.1 Vaststellen of `findings.json` op een PVC houdbaar is tussen twee deployments, of dat
      de werkset naar de database moet
- [ ] 5.2 Zo ja: eigen change, met migratie en met de trail intact
- [ ] 5.3 Niet meenemen in de eerste splitsing

## 6. Documentatie

- [ ] 6.1 `ARCHITECTURE.md`: de graaf, de componenten en hun contracten
- [ ] 6.2 `docs/explanation/`: waarom één component tegelijk, en wat de meting opleverde
- [ ] 6.3 CHANGELOG met de motivatie
