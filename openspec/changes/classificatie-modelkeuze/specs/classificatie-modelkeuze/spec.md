# Spec — classificatie-modelkeuze (nieuw)

## ADDED Requirements

### Requirement: Elk kiesbaar model levert werkende classificatie

Elk model in `KIESBARE_MODELLEN` MUST bevindingen kunnen opleveren. Een model dat in de UI
te kiezen is maar geen classificatie kan produceren, MUST NOT in die lijst staan.

De classificatie-aanroep MUST zijn thinking-configuratie expliciet meegeven, zodat het gedrag
niet verandert doordat een ander model een andere default heeft.

Rationale: gemeten op 2026-08-17 werkte alleen Haiku 4.5. Op Sonnet 5 en Opus 5 staat adaptive
thinking standaard aan wanneer de parameter wordt weggelaten, waardoor het eerste
responsblok een thinking-blok is; `resp.content[0].text` gooide daar een `AttributeError` die
werd afgevangen tot een lege string, en de run meldde zich klaar met nul bevindingen.

#### Scenario: Model met thinking-aan-default

- **WHEN** de auditor een model kiest dat adaptive thinking als default heeft
- **THEN** levert de classificatie bevindingen op zoals bij elk ander model

#### Scenario: Nieuw model toegevoegd aan de keuzelijst

- **WHEN** een model aan `KIESBARE_MODELLEN` wordt toegevoegd
- **THEN** faalt de suite als dat model geen werkende classificatie oplevert

### Requirement: Het antwoord wordt opgezocht, niet aangenomen

Het tekstblok van een classificatie-respons MUST worden gevonden op basis van zijn type, niet
op basis van zijn positie in `content`.

Rationale: "het eerste blok is tekst" is niet door de API gegarandeerd en klopt niet zodra er
een thinking-blok, een tool-blok, of een toekomstig bloktype voor staat.

#### Scenario: Thinking-blok vóór het tekstblok

- **WHEN** de respons begint met een niet-tekstblok
- **THEN** wordt het tekstblok alsnog gevonden en geparseerd

#### Scenario: Respons zonder tekstblok

- **WHEN** de respons geen enkel tekstblok bevat
- **THEN** geldt dat als storing, niet als een leeg oordeel

### Requirement: Nul bevindingen uit een onleesbaar antwoord is een storing

Een onleesbaar antwoord MUST meetellen in de foutenteller en een logregel met de reden
opleveren — ook wanneer de aanroep zelf slaagde en tokens verbruikte.

Een respons die wél leesbaar is maar geen bevindingen bevat, MUST als geldig leeg oordeel
blijven gelden.

Het onderscheid tussen die twee MUST uit de trail te halen zijn.

Rationale: `_parse_json_list("")` returnde stil een lege lijst, waardoor "het model vond
niets" en "we konden het antwoord niet lezen" dezelfde uitkomst gaven. Voor een audittool is
dat de ernstigste vorm van valse dekking: het rapport is leeg en meldt zich compleet.

#### Scenario: Onleesbaar antwoord

- **WHEN** een aanroep slaagt maar er geen tekstblok uit te halen is
- **THEN** gaat de foutenteller omhoog en staat de reden in het log
- **AND** is de run zichtbaar niet compleet

#### Scenario: Leesbaar antwoord zonder bevindingen

- **WHEN** het model expliciet geen bevindingen rapporteert
- **THEN** is dat een geldig leeg oordeel zonder foutmelding

### Requirement: Het output-budget houdt rekening met thinking

Wanneer thinking aanstaat, MUST het output-budget ruimte laten voor thinking én antwoord.

De berekening van het budget MUST bij de constante uitleggen waar het getal vandaan komt en
dat het mee moet bewegen zodra thinking aangaat.

Rationale: op deze modellen begrenst `max_tokens` thinking en responstekst samen. Bij vijf
clausules was het budget 814 tokens; met thinking aan eet dat het antwoord op en wordt de JSON
halverwege afgekapt — zonder dat er een foutmelding tegenover staat.

#### Scenario: Thinking aan met een krap budget

- **WHEN** thinking aanstaat en het budget alleen op het antwoord is gedimensioneerd
- **THEN** faalt de suite in plaats van dat een run afgekapte JSON oplevert

### Requirement: De kosten van een run staan in de trail

Het run-record MUST de totale kosten bevatten, met de peildatum van de tarieven én de
prijsgrondslag.

Rationale: het tokengebruik wordt al per classificatie vastgelegd in
`classifications.usage_json` — gemeten op 2026-08-17: 215 van 215 rijen gevuld in de
referentie-checkout — en `Kostenteller.kosten_usd` rekent de kosten uit. Maar het bedrag
belandt alleen in het log, niet in het run-record. Een auditor die later vraagt wat een run
kostte moet dan door logs zoeken, terwijl de rest van de runhistorie wel in de trail staat.

#### Scenario: Run met classificaties

- **WHEN** een run classificaties heeft uitgevoerd
- **THEN** staat in het run-record een kostenbedrag met peildatum en grondslag

### Requirement: Een cache-instelling die niets doet, doet dat niet stil

Een `cache_control` die geen effect heeft MUST zichtbaar zijn in het log of het run-record,
in plaats van stil te blijven — dat geldt zodra de prompt onder het cache-minimum van het
gekozen model blijft.

Documentatie MUST NOT een cache-besparing beloven die bij de huidige promptgroottes niet
optreedt.

Rationale: `_maak_system_param` zet `cache_control: ephemeral`, maar de systeem-prompts zijn
122–726 tokens terwijl het minimum cacheerbare prefix 4096 tokens is op Haiku 4.5, 1024 op
Sonnet 5 en 512 op Opus 5. Gemeten over 215 classificaties: `cache_read_input_tokens` en
`cache_creation_input_tokens` allebei nul. De module-docstring belooft desondanks "~10x
goedkoper" uit cache. Een belofte die niet uitkomt is erger dan geen belofte, omdat niemand
hem nog controleert.

#### Scenario: Prompt onder het cache-minimum

- **WHEN** de systeem-prompt korter is dan het cache-minimum van het gekozen model
- **THEN** blijkt uit het log dat er niet gecachet wordt
- **AND** belooft de documentatie geen besparing die niet optreedt

### Requirement: De prijsgrondslag is benoemd

De prijzentabel MUST expliciet vermelden of de tarieven lijstprijs zijn of het werkelijk
geldende tarief inclusief tijdelijke acties.

De tabel MUST NOT zelf datums evalueren om een tarief te kiezen.

Rationale: Sonnet 5 stond op $3,00/$15,00 terwijl er tot 31 augustus 2026 een introtarief van
$2,00/$10,00 gold — een verschil van een derde in elk gerapporteerd bedrag. De peildatum van
2026-08-14 lag al binnen die periode. Een bedrag met een peildatum maar zonder grondslag is
niet navertelbaar. Datumlogica in de tabel zou een tweede administratie zijn die achterloopt
op de leverancier, precies wat de peildatum moet voorkomen.

#### Scenario: Tarief met een tijdelijke actie

- **WHEN** een model een tijdelijk tarief heeft dat afwijkt van de lijstprijs
- **THEN** blijkt uit de tabel welke van de twee er staat
- **AND** rapporteert het auditrapport die grondslag mee
