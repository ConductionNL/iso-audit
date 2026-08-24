# Spec — componenten-splitsen (nieuw)

## ADDED Requirements

### Requirement: De afhankelijkheidsgraaf is vastgelegd en machinaal af te leiden

Er MUST een graaf zijn van welke module van welke afhangt, welke gedeelde toestand er is, en
welke paden hetzelfde bestand of dezelfde tabel schrijven.

De graaf MUST uit de code afgeleid worden en MUST NOT met de hand worden bijgehouden.

Rationale: een handgetekende graaf loopt achter en dan verplaatst een splitsing de koppeling in
plaats van hem weg te nemen. De gedeelde-schrijvers-kolom is niet theoretisch: `findings.json`
bleek op 2026-08-24 twee schrijvers te hebben, wat een halve werkset bij lezen opleverde.

#### Scenario: Nieuwe gedeelde schrijver

- **WHEN** iemand een tweede schrijfpad naar een gedeeld bestand toevoegt
- **THEN** verschijnt dat in de graaf en faalt de controle als het niet benoemd is

### Requirement: Elk component heeft een contract en een benoemde faalmodus

Per component MUST vastliggen: wat de invoer is, wat de uitvoer is, en **wat de auditor ziet als
dit component er niet is**.

Een component dat wegvalt MUST zichtbaar onbeschikbaar zijn en MUST NOT stil een leeg of
onvolledig resultaat opleveren.

Rationale: dit is de hele opbrengst. "PDF-conversie mislukt" was een `logger.warning`, en daardoor
ontbrak de PDF maandenlang bij elke run zonder dat iemand het merkte. Zichtbaar falen is het
verschil tussen een kapot onderdeel en een onbetrouwbaar rapport.

#### Scenario: Renderer onbereikbaar

- **WHEN** de rapportcomponent niet bereikbaar is
- **THEN** meldt de run expliciet dat het rapport ontbreekt, met de reden, en blijven de
  bevindingen en de dekking gewoon kloppen

#### Scenario: Assistent onbereikbaar

- **WHEN** de assistent-component niet bereikbaar is
- **THEN** toont het portaal dat op het vragen-scherm en blijft triage bruikbaar

### Requirement: Splitsen gebeurt één component tegelijk, met een meting vooraf en achteraf

Elke splitsing MUST vergezeld gaan van een meting van vóór en na: geheugen, duur en het gedrag
bij uitval.

Er MUST NOT meer dan één component tegelijk uit het portaalproces worden gehaald.

Rationale: vier splitsingen tegelijk maken niet vast te stellen welke iets opleverde of brak. De
rapportketen is de eerste kandidaat omdat hij een duidelijke invoer en uitvoer heeft, de zwaarste
is (350 MiB, 17 s gemeten op 2026-08-24) en nooit op een verzoek hoeft te antwoorden.

#### Scenario: Rapportketen los

- **WHEN** de rapportketen een eigen proces is
- **THEN** blijft het geheugengebruik van het portaalproces onder wat het vóór de splitsing was,
  en is dat gemeten en vastgelegd

### Requirement: De auditgrenzen blijven gelden over componenten heen

Elke handeling MUST met identiteit en tijdstip in de append-only trail komen, ongeacht welk
component hem uitvoert.

Een component MUST NOT een eigen, niet-gedeelde trail bijhouden.

Rationale: een deelbaar systeem met een verstrooide trail is een achteruitgang ten opzichte van
één proces met één trail. De trail is wat dit tool auditeerbaar maakt.

#### Scenario: Handeling in een los component

- **WHEN** een los component een bevinding of run-record wijzigt
- **THEN** staat die wijziging in dezelfde trail, met dezelfde velden, als vóór de splitsing

### Requirement: Gedeelde toestand tussen processen is expliciet benoemd

Voor elk stuk toestand dat door meer dan één component wordt gelezen of geschreven MUST
vastliggen wie eigenaar is en hoe gelijktijdige toegang wordt afgehandeld.

Rationale: `findings.json` wordt vandaag door de run-worker en door elk triage-verzoek geschreven.
Dat is opgelost met `fcntl.flock` en atomair schrijven — bewust een bestandsslot, want dat werkt
ook tussen processen. Maar een gedeeld bestand op een PVC tussen twee deployments is een zwakke
schakel, en die keuze hoort benoemd te zijn en niet ontdekt.

#### Scenario: Werkset gedeeld door twee deployments

- **WHEN** twee componenten de werkset schrijven
- **THEN** ligt vast wie eigenaar is, en is de gelijktijdigheid getest en niet aangenomen
