# Tasks: classificatie-modelkeuze

- [x] 1.1 `classification/findings.py`: `thinking={"type": "disabled"}` expliciet meegeven in
      beide classificatiepaden (doc en Miro), met de reden erbij — het gedrag mag niet
      veranderen doordat een ander model een andere default heeft
- [x] 1.2 `classification/llm.py`: dezelfde expliciete configuratie op de aanroepen daar
      (regel 89 en 132), zodat er geen tweede pad overblijft met de oude aanname
- [x] 2.1 Helper die het eerste blok met `type == "text"` opzoekt in plaats van
      `resp.content[0]` te nemen; gebruikt door alle classificatie-aanroepen
- [x] 2.2 Geen tekstblok gevonden ⇒ `teller.fouten` omhoog plus een logregel met de reden;
      `_parse_json_list` blijft ongewijzigd voor een leesbaar antwoord zonder array
- [x] 3.1 Comment bij `max_tokens = 150 * len(clausule_ids) + 64`: waar de 150 vandaan komt
      (80 woorden beschrijving plus onderbouwing) en dat het budget mee moet omhoog zodra
      thinking aangaat, omdat `max_tokens` thinking én antwoord samen begrenst
- [x] 4.1 ~~Uitzoeken waarom `usage_json` leeg blijft~~ — **vervallen, premisse was fout.**
      Correct gemeten op 17-08 met Python (de eerdere check gebruikte `sqlite3`, dat op deze
      machine niet bestaat): 215 van 215 rijen gevuld in de referentie-checkout. Geen defect
- [x] 4.2 Run-record krijgt totale kosten met `PRIJZEN_PEILDATUM` én de prijsgrondslag
- [x] 5.1 `PRIJZEN` krijgt een expliciete grondslag (lijstprijs of werkelijk tarief); geen
      datumlogica in de tabel
- [x] 5.2 Grondslag staat op `lijstprijs` en de tabel volgt dat; **openstaande vraag aan de
      opdrachtgever**: moet het auditrapport lijstprijs of werkelijke kosten noemen? Wisselen
      is een waardewijziging, geen code. Oorspronkelijk: vraag aan de opdrachtgever welke van de twee
      het auditrapport moet noemen
- [x] 5.3 Cache: `cache_control` staat op prompts van 122–726 tokens terwijl het minimum 4096
      (Haiku), 1024 (Sonnet 5) en 512 (Opus 5) is — gemeten cache_read = 0 over 215 calls.
      Zichtbaar maken dat er niet gecachet wordt, en de "~10x goedkoper"-belofte uit de
      module-docstring van `findings.py` halen of waarmaken
- [x] 6.1 Test: elk model in `KIESBARE_MODELLEN` levert een geparseerde bevinding op met een
      gestubde respons waarvan het eerste blok géén tekstblok is
- [x] 6.2 Test: respons zonder tekstblok verhoogt de foutenteller en logt de reden
- [x] 6.3 Test: leesbaar antwoord zonder bevindingen blijft een geldig leeg oordeel zonder
      foutmelding
- [x] 6.4 Test: `usage_json` is gevuld na een classificatie — als regressiebewaking, niet als
      reparatie; het werkt al
- [x] 6.5 Test: het output-budget laat ruimte voor thinking zodra thinking aanstaat
- [x] 7.1 `docs/reference/configuratie.md` (of de modelkeuze-doc): wat de modelkeuze betekent,
      welke grondslag de prijzen hebben, en dat `max_tokens` thinking meerekent
- [x] 7.2 CHANGELOG-regel met de motivatie: twee van de drie modellen leverden stil nul
      bevindingen
- [ ] 8.1 In het cluster verifiëren: dezelfde audit op Haiku 4.5 én op Sonnet 5, en vaststellen
      dat beide bevindingen opleveren en dat de kosten in het run-record staan
- [ ] 8.2 **Meting voorleggen aan Mark:** triage van beide runs vergeleken met de
      referentie-output van juni — is het betere oordeel de prijs waard? Deze change kiest
      geen model; dit is het moment waarop dat wel gebeurt
