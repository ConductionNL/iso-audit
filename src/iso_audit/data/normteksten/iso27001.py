"""ISO 27001:2022 normteksten — gemigreerd uit Ops_to_Biz/audit/normteksten.py.

Schema identiek aan iso9001.py. Annex A-beheersmaatregelen (5.x, 6.x, 7.x, 8.x)
zijn opgenomen onder dezelfde keys als reguliere clausules.
"""

from __future__ import annotations

from typing import Any

NORMTEKSTEN_27001: dict[str, dict[str, Any]] = {
    # ---- Organisatorische beheersmaatregelen (5.x) ----
    "A.5.1": {
        "normtekst": (
            "Beleid voor informatiebeveiliging en themaspecifieke beleidslijnen "
            "moeten worden vastgesteld, goedgekeurd door de directie, "
            "gepubliceerd, gecommuniceerd aan medewerkers en relevante "
            "belanghebbenden, en op geplande tijdstippen worden beoordeeld."
        ),
        "interpretatie": (
            "Zonder een duidelijk beleid weet niemand wat de spelregels zijn "
            "op het gebied van informatiebeveiliging. Het beleid geeft richting "
            "aan alle andere maatregelen. Een beleid dat alleen in een la ligt "
            "telt niet; het moet bekend en actueel zijn."
        ),
        "bewijslast": [
            "Informatiebeveiligingsbeleid ondertekend door directie",
            "Themaspecifieke beleidslijnen (toegang, cryptografie, BYOD, etc.)",
            "Bewijs van communicatie (intranet, onboarding, e-mail)",
            "Versiehistorie en datum laatste beoordeling",
        ],
    },
    "A.5.2": {
        "normtekst": (
            "Rollen en verantwoordelijkheden voor informatiebeveiliging moeten "
            "worden gedefinieerd en toegewezen overeenkomstig de behoeften van "
            "de organisatie."
        ),
        "interpretatie": (
            "Als niemand specifiek verantwoordelijk is voor beveiliging, is "
            "iedereen het in theorie maar niemand in de praktijk. Duidelijke "
            "rollen (CISO, data-eigenaar, systeembeheerder) voorkomen gaten in "
            "de beveiliging."
        ),
        "bewijslast": [
            "Organogram met informatiebeveiligingsrollen",
            "Functiebeschrijvingen met beveiligingsverantwoordelijkheden",
            "Benoemingsbesluit CISO of equivalent",
        ],
    },
    "A.5.3": {
        "normtekst": (
            "Conflicterende taken en conflicterende verantwoordelijkheden moeten "
            "worden gescheiden om de kans op ongeautoriseerde of onbedoelde "
            "wijziging of misbruik van activa van de organisatie te verkleinen."
        ),
        "interpretatie": (
            "Functiescheiding (segregation of duties) voorkomt dat één persoon "
            "fraude kan plegen of fouten kan verbergen. Denk aan het scheiden "
            "van aanvragen, goedkeuren en uitvoeren van toegangsrechten of "
            "financiële transacties."
        ),
        "bewijslast": [
            "Functiescheidingsmatrix of SOD-analyse",
            "Bewijs dat kritieke processtappen door verschillende personen worden uitgevoerd",
            "Compenserende maatregelen waar volledige scheiding niet mogelijk is",
        ],
    },
    "A.5.4": {
        "normtekst": (
            "Het management moet van alle medewerkers verlangen dat zij "
            "informatiebeveiliging toepassen in overeenstemming met het beleid "
            "en de procedures van de organisatie."
        ),
        "interpretatie": (
            "Beveiliging is niet alleen een IT-verantwoordelijkheid. Het "
            "management moet actief uitdragen en afdwingen dat medewerkers "
            "zich aan beveiligingsregels houden. Dit vraagt om duidelijke "
            "verwachtingen en consequenties bij niet-naleving."
        ),
        "bewijslast": [
            "Arbeidsovereenkomst of gedragscode met beveiligingsverplichtingen",
            "Bewijs van managementcommunicatie over beveiligingsverwachtingen",
            "Disciplinaire procedure bij schending beveiligingsbeleid",
        ],
    },
    "A.5.5": {
        "normtekst": (
            "De organisatie moet contacten onderhouden met relevante overheids- "
            "en regelgevende autoriteiten op het gebied van informatiebeveiliging."
        ),
        "interpretatie": (
            "Bij een incident of datalek moet je weten wie je moet bellen: "
            "de AP, het NCSC, of sectorale toezichthouders. Het gaat erom "
            "dat deze contacten vooraf zijn vastgelegd, niet dat je ze pas "
            "zoekt als het te laat is."
        ),
        "bewijslast": [
            "Contactenlijst relevante autoriteiten (AP, NCSC, sectortoezichthouder)",
            "Procedure voor melding datalekken met contactgegevens",
            "Bewijs van periodiek contact of deelname aan informatiedeling",
        ],
    },
    "A.5.6": {
        "normtekst": (
            "De organisatie moet contacten onderhouden met speciale "
            "belangengroepen, beveiligingsforums en professionele verenigingen "
            "op het gebied van informatiebeveiliging."
        ),
        "interpretatie": (
            "Dreigingen en kwetsbaarheden ontwikkelen zich snel. Door deel te "
            "nemen aan communities (ISAC's, NCSC-meldkringen, vakverenigingen) "
            "blijf je op de hoogte van relevante ontwikkelingen voordat ze je "
            "treffen."
        ),
        "bewijslast": [
            "Lijst van lidmaatschappen of abonnementen op dreigingsinformatie",
            "Bewijs van deelname aan sector-ISAC of vergelijkbaar netwerk",
            "Procedure voor verwerking van ontvangen dreigingsinformatie",
        ],
    },
    "A.5.7": {
        "normtekst": (
            "Informatie over informatiebeveiligingsdreigingen moet worden "
            "verzameld en geanalyseerd om dreigingsinformatie te produceren die "
            "kan worden gebruikt om beveiligingsbeslissingen te ondersteunen."
        ),
        "interpretatie": (
            "Threat intelligence is meer dan het lezen van nieuwsberichten. "
            "Je moet actief informatie verzamelen over relevante dreigingen, "
            "deze analyseren op relevantie voor jouw context en er "
            "beslissingen op baseren over maatregelen."
        ),
        "bewijslast": [
            "Threat intelligence bronnen en abonnementen",
            "Proces voor analyse en verwerking van dreigingsinformatie",
            "Bewijs van aanpassing van maatregelen op basis van threat intel",
        ],
    },
    "A.5.8": {
        "normtekst": (
            "Informatiebeveiliging moet worden geïntegreerd in projectmanagement "
            "zodat informatiebeveiligingsrisico's worden geïdentificeerd en "
            "aangepakt als onderdeel van projecten."
        ),
        "interpretatie": (
            "Beveiliging achteraf inbouwen is duurder en minder effectief dan "
            "security by design. Door beveiliging in projectgateway's op te "
            "nemen voorkom je dat nieuwe systemen en processen gaten in je "
            "beveiligingslandschap creëren."
        ),
        "bewijslast": [
            "Projectmethodologie met beveiligingscheckpoints",
            "Privacy/security impact assessment (PIA/DPIA) voor projecten",
            "Bewijs van beveiligingsbeoordeling bij oplevering projecten",
        ],
    },
    "A.5.9": {
        "normtekst": (
            "Een inventaris van informatie en andere daarmee samenhangende "
            "activa, inclusief eigenaren, moet worden opgesteld en onderhouden."
        ),
        "interpretatie": (
            "Je kunt geen activa beschermen die je niet kent. Een bijgewerkt "
            "activa-register is de basis voor risicoanalyse, classificatie en "
            "beveiligingsmaatregelen. Activa zonder eigenaar worden stelselmatig "
            "verwaarloosd."
        ),
        "bewijslast": [
            "Informatieactiva-register met eigenaar per actief",
            "Procedure voor registratie van nieuwe activa",
            "Bewijs van periodieke actualisatie van het register",
        ],
    },
    "A.5.10": {
        "normtekst": (
            "Regels voor acceptabel gebruik en procedures voor de omgang met "
            "informatie en andere daarmee samenhangende activa moeten worden "
            "geïdentificeerd, gedocumenteerd en geïmplementeerd."
        ),
        "interpretatie": (
            "Medewerkers moeten weten wat wel en niet mag met bedrijfsinformatie "
            "en -apparatuur. Onduidelijkheid leidt tot risicovol gedrag zonder "
            "kwade wil. Acceptabel gebruiksbeleid stelt duidelijke grenzen."
        ),
        "bewijslast": [
            "Acceptable use policy (AUP) voor informatiesystemen",
            "Bewijs van communicatie en acceptatie door medewerkers",
            "Specifieke regels voor mobiele apparaten, cloud en sociale media",
        ],
    },
    "A.5.11": {
        "normtekst": (
            "Procedures voor de teruggave of vernietiging van informatie en "
            "andere daarmee samenhangende activa bij beëindiging of wijziging "
            "van het dienstverband of contract moeten worden gedefinieerd en "
            "geïmplementeerd."
        ),
        "interpretatie": (
            "Als medewerkers of leveranciers vertrekken, moeten toegangsrechten "
            "worden ingetrokken en bedrijfsmiddelen worden teruggegeven. Dit "
            "is een kritiek moment dat geregeld gedrag vereist, niet "
            "improvisatie."
        ),
        "bewijslast": [
            "Offboarding-checklist voor medewerkers en contractanten",
            "Bewijs van tijdige intrekking van toegangsrechten bij uitdiensttreding",
            "Records van teruggave of vernietiging van activa",
        ],
    },
    "A.5.12": {
        "normtekst": (
            "Informatie moet worden geclassificeerd op basis van de "
            "informatiebeveiligingsbehoeften van de organisatie, rekening "
            "houdend met vertrouwelijkheid, integriteit en beschikbaarheid."
        ),
        "interpretatie": (
            "Niet alle informatie is even gevoelig. Door te classificeren "
            "(bijv. openbaar, intern, vertrouwelijk, geheim) kun je "
            "proportionele maatregelen treffen. Zonder classificatie "
            "behandel je alles hetzelfde, wat inefficiënt en onveilig is."
        ),
        "bewijslast": [
            "Informatieclassificatiebeleid met classificatieniveaus",
            "Classificatieschema toegepast op activa-register",
            "Bewijs van gebruik van classificatielabels op documenten",
        ],
    },
    "A.5.13": {
        "normtekst": (
            "Een passende set procedures voor labeling van informatie moet worden "
            "ontwikkeld en geïmplementeerd in overeenstemming met het "
            "informatieclassificatieschema."
        ),
        "interpretatie": (
            "Classificatie heeft alleen waarde als informatie ook daadwerkelijk "
            "wordt gelabeld. Labels op documenten, e-mails en systemen maken "
            "het voor medewerkers eenvoudig om te weten hoe ze informatie "
            "moeten behandelen."
        ),
        "bewijslast": [
            "Labelingsprocedure per classificatieniveau",
            "Bewijs van labelgebruik (voorbeelddocumenten, e-mailheaders)",
            "Technische implementatie van labels (DLP, Azure Information Protection)",
        ],
    },
    "A.5.14": {
        "normtekst": (
            "Regels voor informatieoverdracht moeten worden gedefinieerd voor "
            "alle soorten overdrachtsvoorzieningen en moeten overeenkomsten "
            "voor informatieoverdracht omvatten voor externe partijen."
        ),
        "interpretatie": (
            "Informatieoverdracht via e-mail, FTP, USB of fysieke post draagt "
            "beveiligingsrisico's. Door hiervoor expliciete regels te stellen "
            "en afspraken met externe partijen te maken, reduceer je de kans "
            "op datalekken bij overdracht."
        ),
        "bewijslast": [
            "Beleid voor informatieoverdracht (intern en extern)",
            "Non-disclosure agreements (NDA's) met externe partijen",
            "Technische maatregelen voor veilige overdracht (encryptie, VPN)",
        ],
    },
    "A.5.15": {
        "normtekst": (
            "Regels voor toegangsbeheersing tot informatie en andere "
            "daarmee samenhangende activa moeten worden vastgesteld en "
            "geïmplementeerd op basis van bedrijfs- en "
            "informatiebeveiligingseisen."
        ),
        "interpretatie": (
            "Toegangsbeheersing is de kern van informatiebeveiliging: alleen "
            "de juiste personen hebben toegang tot de juiste informatie op het "
            "juiste moment. Het beleid stelt de regels; technische maatregelen "
            "en processen voeren ze uit."
        ),
        "bewijslast": [
            "Toegangsbeheersingsbeleid",
            "Rolgebaseerde toegangsmatrix (RBAC)",
            "Procedure voor aanvraag, goedkeuring en intrekking van toegangsrechten",
        ],
    },
    "A.5.16": {
        "normtekst": (
            "De volledige levenscyclus van identiteiten moet worden beheerd "
            "in overeenstemming met het toegangsbeheersingsbeleid."
        ),
        "interpretatie": (
            "Identiteitsbeheer gaat over het aanmaken, wijzigen en verwijderen "
            "van accounts. Slapende accounts van ex-medewerkers zijn een "
            "veelvoorkomend beveiligingsrisico. Geautomatiseerd identiteitsbeheer "
            "vermindert handmatige fouten."
        ),
        "bewijslast": [
            "Identity lifecycle management procedure",
            "Bewijs van tijdige deactivering accounts bij uitdiensttreding",
            "Periodieke toegangsreview (user access review) resultaten",
        ],
    },
    "A.5.17": {
        "normtekst": (
            "Beheer van authenticatie-informatie moet worden beheerst door middel "
            "van een formeel beheersproces, inclusief advies aan gebruikers over "
            "het omgaan met authenticatie-informatie."
        ),
        "interpretatie": (
            "Wachtwoorden en andere authenticatiegegevens zijn de sleutels tot "
            "systemen. Zwak wachtwoordbeleid, gedeelde accounts of onversleutelde "
            "opslag zijn directe risico's. MFA is inmiddels de norm voor "
            "kritieke systemen."
        ),
        "bewijslast": [
            "Wachtwoordbeleid met complexiteits- en verloopvereisten",
            "Bewijs van MFA-implementatie op kritieke systemen",
            "Procedure voor beheer van privileged accounts en service-accounts",
        ],
    },
    "A.5.18": {
        "normtekst": (
            "Toegangsrechten tot informatie en andere daarmee samenhangende "
            "activa moeten worden verstrekt, beoordeeld, gewijzigd en "
            "ingetrokken overeenkomstig het themaspecifieke beleid en de "
            "regels van de organisatie."
        ),
        "interpretatie": (
            "Toegangsrechten slijten: functies veranderen, projecten eindigen, "
            "mensen vertrekken. Periodieke review van toegangsrechten (access "
            "recertification) zorgt ervoor dat alleen actuele rechten actief zijn "
            "en voorkomt privilege creep."
        ),
        "bewijslast": [
            "Procedure voor toekenning en intrekking van toegangsrechten",
            "Records van toegangsreviews (halfjaarlijks of jaarlijks)",
            "Bewijs van prompte intrekking bij functiewijziging of vertrek",
        ],
    },
    "A.5.19": {
        "normtekst": (
            "Processen en procedures moeten worden gedefinieerd en "
            "geïmplementeerd om de informatiebeveiligingsrisico's die verband "
            "houden met het gebruik van producten of diensten van leveranciers "
            "te beheersen."
        ),
        "interpretatie": (
            "Leveranciers en dienstverleners hebben toegang tot systemen en "
            "data. Als zij niet dezelfde beveiligingsnorm hanteren als jij, "
            "ontstaan kwetsbaarheden buiten je directe controle. "
            "Leveranciersrisicobeheer is essentieel in een uitbestede omgeving."
        ),
        "bewijslast": [
            "Leveranciersbeveiligingsbeleid",
            "Risicobeoordelingsproces voor leveranciers",
            "Contractuele beveiligingsvereisten voor leveranciers",
        ],
    },
    "A.5.20": {
        "normtekst": (
            "Informatiebeveiligingseisen moeten worden vastgesteld en "
            "overeengekomen met elke leverancier op basis van het type "
            "leveranciersrelatie en het risiconiveau."
        ),
        "interpretatie": (
            "Het is niet voldoende om intern beveiligingseisen te hebben; "
            "leveranciers moeten deze contractueel accepteren. SLA's en "
            "contracten moeten beveiligingsvereisten bevatten die "
            "afdwingbaar zijn."
        ),
        "bewijslast": [
            "Standaard beveiligingsbijlage bij leverancierscontracten",
            "Getekende verwerkersovereenkomsten (AVG-verplichting)",
            "Bewijs van beveiligingseisen in offertetraject (RFP/RFI)",
        ],
    },
    "A.5.21": {
        "normtekst": (
            "Procedures en eisen voor het beheer van informatiebeveiligingsrisico's "
            "in verband met de ICT-toeleveringsketen moeten worden vastgesteld "
            "en geïmplementeerd."
        ),
        "interpretatie": (
            "De toeleveringsketen voor software en hardware bevat risico's die "
            "je niet direct controleert (SolarWinds, XZ-utils). Je moet weten "
            "welke componenten je gebruikt en nadenken over risico's van "
            "gecompromitteerde toeleveranciers."
        ),
        "bewijslast": [
            "Software Bill of Materials (SBOM) of componentenregister",
            "Procedure voor beoordeling van ICT-toeleveranciers",
            "Bewijs van monitoring op kwetsbaarheden in gebruikte componenten",
        ],
    },
    "A.5.22": {
        "normtekst": (
            "De organisatie moet regelmatig de informatiebeveiligingspraktijken "
            "en dienstverlening van leveranciers monitoren, beoordelen, evalueren "
            "en wijzigingen beheren."
        ),
        "interpretatie": (
            "Leveranciersbeheer stopt niet bij contractondertekening. Periodieke "
            "reviews van leveranciersprestaties en beveiligingsnaleving zorgen "
            "ervoor dat afspraken ook daadwerkelijk worden nagekomen en dat je "
            "veranderingen tijdig signaleert."
        ),
        "bewijslast": [
            "Leveranciersbeoordelingsrapportages",
            "Bewijs van periodieke beveiligingsreviews met leveranciers",
            "Proces voor beheer van leverancierswijzigingen (wijzigingsbeheer)",
        ],
    },
    "A.5.23": {
        "normtekst": (
            "Processen voor het verwerven, gebruiken, beheren en beëindigen van "
            "informatiebeveiligingsdiensten in de cloud moeten worden vastgesteld "
            "overeenkomstig de informatiebeveiligingseisen van de organisatie."
        ),
        "interpretatie": (
            "Cloud introduceert specifieke risico's rondom dataresidenentie, "
            "gedeelde verantwoordelijkheid (shared responsibility model) en "
            "lock-in. Je moet expliciete afspraken maken met cloudproviders "
            "en weten wie verantwoordelijk is voor welk beveiligingsaspect."
        ),
        "bewijslast": [
            "Cloud security beleid en shared responsibility matrix",
            "Contractuele beveiligingsafspraken met cloudproviders",
            "Bewijs van configuratiebeheer cloudomgevingen (CIS benchmarks)",
        ],
    },
    "A.5.24": {
        "normtekst": (
            "De organisatie moet plannen en zich voorbereiden op het beheren van "
            "informatiebeveiligingsincidenten door rollen, verantwoordelijkheden "
            "en procedures te definiëren voor incidentrespons."
        ),
        "interpretatie": (
            "Improviseren tijdens een beveiligingsincident is kostbaar. "
            "Een vooraf gedefinieerd incidentresponsplan zorgt voor een "
            "gecontroleerde aanpak, snellere herstel en minder schade. "
            "Rollen moeten vooraf zijn belegd, niet pas bij een incident."
        ),
        "bewijslast": [
            "Informatiebeveiligingsincident respons procedure",
            "RACI voor incidentresponsteam",
            "Bewijs van oefening of test van het incidentresponsplan",
        ],
    },
    "A.5.25": {
        "normtekst": (
            "De organisatie moet informatiebeveiligingsgebeurtenissen beoordelen "
            "en beslissen of ze als informatiebeveiligingsincidenten moeten worden "
            "geclassificeerd."
        ),
        "interpretatie": (
            "Niet elke beveiligingsgebeurtenis is een incident. Door een heldere "
            "classificatieprocedure te hebben voorkom je zowel overreactie als "
            "onderrapportage. De drempel voor melding moet laag zijn; "
            "de drempel voor escalatie proportioneel."
        ),
        "bewijslast": [
            "Incidentclassificatieschema of -criteria",
            "Incidentenregister met classificatierecords",
            "Bewijs van triageprocedure voor beveiligingsgebeurtenissen",
        ],
    },
    "A.5.26": {
        "normtekst": (
            "Op informatiebeveiligingsincidenten moet worden gereageerd "
            "overeenkomstig de gedocumenteerde procedures."
        ),
        "interpretatie": (
            "Bij een incident telt elke minuut. Procedures moeten de "
            "response structureren: insluiting, onderzoek, herstel en "
            "communicatie. Na afloop moet een lessons-learned plaatsvinden "
            "om herhaling te voorkomen."
        ),
        "bewijslast": [
            "Incidentresponslogboek of ticketregistratie",
            "Bewijs van uitgevoerde respons conform procedure",
            "Post-incident review verslagen (lessons learned)",
        ],
    },
    "A.5.27": {
        "normtekst": (
            "Kennis opgedaan uit informatiebeveiligingsincidenten moet worden "
            "gebruikt om de kans op of gevolgen van toekomstige incidenten te "
            "verkleinen."
        ),
        "interpretatie": (
            "Elk incident is een leerkans. Structurele analyse van incidenten "
            "levert inzichten die preventieve maatregelen rechtvaardigen. "
            "Organisaties die hier geen gebruik van maken, lopen dezelfde "
            "incidenten steeds opnieuw op."
        ),
        "bewijslast": [
            "Post-incident review verslagen",
            "Bewijs van implementatie van verbeteringen na incidenten",
            "Trendanalyse incidentenregister (periodiek)",
        ],
    },
    "A.5.28": {
        "normtekst": (
            "De organisatie moet procedures vaststellen voor de identificatie, "
            "verzameling, verwerving en bewaring van bewijsmateriaal dat "
            "gerelateerd is aan informatiebeveiligingsincidenten."
        ),
        "interpretatie": (
            "Digitaal bewijsmateriaal kan nodig zijn voor disciplinaire "
            "procedures, rechtszaken of forensisch onderzoek. Als bewijsverzameling "
            "niet forensisch correct verloopt, is het bewijs onbruikbaar. "
            "Forensische procedures moeten van tevoren zijn vastgesteld."
        ),
        "bewijslast": [
            "Digitale forensics procedure (chain of custody)",
            "Bewijs van logging en log-retentiebeleid",
            "Procedure voor bewaring van forensisch bewijsmateriaal",
        ],
    },
    "A.5.29": {
        "normtekst": (
            "De organisatie moet plannen en maatregelen implementeren voor het "
            "handhaven van informatiebeveiliging tijdens verstoring."
        ),
        "interpretatie": (
            "Bij een calamiteit (brand, DDoS, uitval leverancier) staan "
            "informatiebeveiliging en bedrijfscontinuïteit op gespannen voet. "
            "Beveiliging mag niet worden opgeofferd voor snelheid van herstel. "
            "Continuïteitsplannen moeten beveiligingsvereisten integreren."
        ),
        "bewijslast": [
            "Business continuity plan met beveiligingsparagraaf",
            "Bewijs van integratie van beveiligingseisen in herstelplannen",
            "BCP-oefenverslagen inclusief beveiligingsaspecten",
        ],
    },
    "A.5.30": {
        "normtekst": (
            "ICT-gereedheid moet worden gepland, geïmplementeerd, onderhouden "
            "en getest op basis van bedrijfscontinuïteitsdoelstellingen en "
            "ICT-continuïteitseisen."
        ),
        "interpretatie": (
            "ICT-continuïteit gaat over het kunnen herstellen van systemen "
            "binnen de gestelde RTO en RPO. Dit vereist technische maatregelen "
            "(back-ups, redundantie) én procedures én regelmatig testen. "
            "Ongeteste continuïteitsplannen zijn geen plannen maar wensen."
        ),
        "bewijslast": [
            "ICT-continuïteitsplan met RTO/RPO per systeem",
            "Back-upbeleid en back-uptestresultaten",
            "DR-oefenverslagen (disaster recovery tests)",
        ],
    },
    "A.5.31": {
        "normtekst": (
            "Wettelijke, statutaire, regelgevende en contractuele eisen die "
            "relevant zijn voor informatiebeveiliging moeten worden "
            "geïdentificeerd, gedocumenteerd en actueel gehouden."
        ),
        "interpretatie": (
            "AVG, NIS2, sectorale wetgeving en contractuele verplichtingen "
            "creëren beveiligingseisen die je niet kunt negeren. Door een "
            "actueel register te onderhouden weet je wat je moet naleven en "
            "kun je aantonen dat je dit ook doet."
        ),
        "bewijslast": [
            "Wettelijk en regelgevend complianceregister",
            "Bewijs van periodieke beoordeling op nieuwe wet- en regelgeving",
            "Koppeling tussen wettelijke eisen en geïmplementeerde maatregelen",
        ],
    },
    "A.5.32": {
        "normtekst": (
            "De organisatie moet procedures implementeren om intellectuele "
            "eigendomsrechten te beschermen en het gebruik van propriëtaire "
            "software te beheren."
        ),
        "interpretatie": (
            "Illegaal software gebruik en schending van auteursrechten zijn "
            "juridische risico's. Softwarelicenties moeten worden bijgehouden "
            "en nageleefd. Open source software vereist begrip van licentie- "
            "voorwaarden (GPL, MIT, etc.)."
        ),
        "bewijslast": [
            "Software Asset Management (SAM) register",
            "Bewijs van naleving licentievoorwaarden",
            "Procedure voor gebruik van open source componenten",
        ],
    },
    "A.5.33": {
        "normtekst": (
            "Registraties moeten worden beschermd tegen verlies, vernietiging, "
            "vervalsing en onbevoegde toegang en vrijgave, overeenkomstig "
            "wettelijke, statutaire, regelgevende en contractuele eisen."
        ),
        "interpretatie": (
            "Bedrijfsregistraties (contracten, financiële records, auditrails) "
            "zijn juridisch en operationeel van groot belang. Goede bescherming "
            "en retentie zorgen dat records beschikbaar zijn wanneer nodig en "
            "vernietigd worden wanneer ze niet meer nodig zijn."
        ),
        "bewijslast": [
            "Retentiebeleid voor registraties met bewaartermijnen",
            "Bewijs van bescherming van kritieke registraties (toegangsbeheersing, back-up)",
            "Procedure voor veilige verwijdering na verloop retentietermijn",
        ],
    },
    "A.5.34": {
        "normtekst": (
            "De organisatie moet de privacy en bescherming van persoonsgegevens "
            "waarborgen zoals vereist door relevante wet- en regelgeving."
        ),
        "interpretatie": (
            "AVG-naleving is niet optioneel. Privacy moet worden ingebouwd in "
            "processen en systemen (privacy by design). De overlap tussen "
            "informatiebeveiliging en privacy is groot; goede samenwerking "
            "tussen CISO en FG is essentieel."
        ),
        "bewijslast": [
            "Privacybeleid en verwerkingsregister (AVG artikel 30)",
            "DPIA's voor risicovolle verwerkingen",
            "Bewijs van privacy by design bij nieuwe systemen",
        ],
    },
    "A.5.35": {
        "normtekst": (
            "Een onafhankelijke beoordeling van de aanpak van de organisatie "
            "voor het beheren van informatiebeveiliging en de implementatie "
            "ervan moet op geplande tijdstippen of bij significante wijzigingen "
            "worden uitgevoerd."
        ),
        "interpretatie": (
            "Interne beoordelingen hebben blinde vlekken. Een onafhankelijke "
            "review (interne audit door onafhankelijke partij, externe audit, "
            "of penetratietest) biedt een objectiever beeld van de volwassenheid "
            "van het ISMS."
        ),
        "bewijslast": [
            "Rapporten van onafhankelijke ISMS-beoordelingen",
            "Bewijs van opvolging van bevindingen",
            "Planning van periodieke onafhankelijke reviews",
        ],
    },
    "A.5.36": {
        "normtekst": (
            "Naleving van het informatiebeveiligingsbeleid, themaspecifieke "
            "beleidslijnen en technische normen van de organisatie moet "
            "regelmatig worden beoordeeld."
        ),
        "interpretatie": (
            "Beleid schrijven is stap één; handhaven is stap twee. Periodieke "
            "compliancereviews (technisch en procedureel) tonen aan dat beleid "
            "niet alleen op papier bestaat maar ook in de praktijk wordt "
            "nageleefd."
        ),
        "bewijslast": [
            "Compliancereview rapporten per beleidsdocument",
            "Technische compliancescans (vulnerability assessments, configuratiereviews)",
            "Bewijs van opvolging van non-compliant bevindingen",
        ],
    },
    "A.5.37": {
        "normtekst": (
            "Gedocumenteerde bedieningsprocedures voor informatie- "
            "verwerkingsfaciliteiten moeten beschikbaar worden gesteld aan "
            "alle gebruikers die deze nodig hebben."
        ),
        "interpretatie": (
            "Procedures voor het bedienen van systemen moeten beschikbaar en "
            "actueel zijn zodat systemen consistent en correct worden gebruikt. "
            "Dit geldt zowel voor reguliere operatie als voor noodsituaties."
        ),
        "bewijslast": [
            "Operationele procedures voor kritieke systemen",
            "Bewijs van beschikbaarheid voor relevante gebruikers",
            "Versiehistorie en goedkeuringsrecords van procedures",
        ],
    },
    # ---- Mensgerichte beheersmaatregelen (6.x) ----
    "A.6.1": {
        "normtekst": (
            "Achtergrondverificaties van alle kandidaten voor een dienstverband "
            "moeten worden uitgevoerd voordat zij toetreden tot de organisatie "
            "en op doorlopende basis, rekening houdend met wet- en regelgeving "
            "en ethische overwegingen."
        ),
        "interpretatie": (
            "Personeel is een van de grootste risicofactoren voor "
            "informatiebeveiliging. Screening voor indiensttreding verlaagt "
            "het risico op insider threats. De diepte van screening moet "
            "proportioneel zijn aan de gevoeligheid van de functie."
        ),
        "bewijslast": [
            "Screeningbeleid voor nieuwe medewerkers en contractanten",
            "Records van uitgevoerde screenings (VOG, referentiecheck)",
            "Procedure voor periodieke rescreening bij gevoelige functies",
        ],
    },
    "A.6.2": {
        "normtekst": (
            "Arbeidsovereenkomsten en contracten moeten de verantwoordelijkheden "
            "van de medewerkers en de organisatie voor informatiebeveiliging "
            "vastleggen."
        ),
        "interpretatie": (
            "Beveiligingsverplichtingen moeten contractueel zijn vastgelegd "
            "zodat ze afdwingbaar zijn. Medewerkers moeten begrijpen wat ze "
            "tekenen. Dit geldt ook voor contractanten en externe medewerkers."
        ),
        "bewijslast": [
            "Arbeidscontract met beveiligingsclausules",
            "Geheimhoudingsverklaringen (NDA's)",
            "Bewijs van acceptatie door medewerker",
        ],
    },
    "A.6.3": {
        "normtekst": (
            "Medewerkers en relevante contractanten moeten passend bewustzijn, "
            "onderwijs en opleiding ontvangen over informatiebeveiliging en "
            "regelmatige updates van het beleid."
        ),
        "interpretatie": (
            "Technische maatregelen falen als medewerkers niet begrijpen waarom "
            "beveiliging belangrijk is en hoe ze moeten handelen. Awareness "
            "training is de meest kosteneffectieve maatregel tegen social "
            "engineering en menselijke fouten."
        ),
        "bewijslast": [
            "Security awareness trainingsprogramma en -planning",
            "Trainingscompletierecords per medewerker",
            "Phishing simulatieresultaten en follow-up trainingen",
        ],
    },
    "A.6.4": {
        "normtekst": (
            "Er moet een formeel en gecommuniceerd disciplinair proces bestaan "
            "en worden geactiveerd om actie te ondernemen tegen medewerkers en "
            "andere relevante betrokken partijen die een informatiebeveiligings- "
            "overtreding begaan hebben."
        ),
        "interpretatie": (
            "Zonder consequenties voor beleidsovertredingen heeft beleid geen "
            "afschrikkende werking. Het disciplinaire proces moet eerlijk, "
            "proportioneel en vooraf bekend zijn. Dit werkt preventief en "
            "beschermt de organisatie juridisch."
        ),
        "bewijslast": [
            "Disciplinaire procedure met beveiligingsovertredingen",
            "Arbeidsreglement of gedragscode met sancties",
            "Bewijs van toepassing van procedure (geanonimiseerde cases)",
        ],
    },
    "A.6.5": {
        "normtekst": (
            "Informatiebeveiligingsverantwoordelijkheden en -verplichtingen die "
            "van kracht blijven na beëindiging of wijziging van het "
            "dienstverband moeten worden gedefinieerd, gecommuniceerd en "
            "gehandhaafd."
        ),
        "interpretatie": (
            "Geheimhouding eindigt niet op de laatste werkdag. Medewerkers "
            "moeten weten dat hun beveiligingsverplichtingen (NDA, "
            "geheimhouding) doorlopen na vertrek. Dit moet expliciet zijn "
            "vastgelegd in het contract."
        ),
        "bewijslast": [
            "Arbeidscontract met post-employment beveiligingsverplichtingen",
            "Exit-procedure met bevestiging van doorlopende verplichtingen",
            "NDA met expliciete doorlooptermijn na beëindiging dienstverband",
        ],
    },
    "A.6.6": {
        "normtekst": (
            "Informatiebeveiligingseisen moeten worden opgenomen in overeenkomsten "
            "met personeel en contractanten."
        ),
        "interpretatie": (
            "Externe medewerkers en ZZP'ers vormen net zo'n risico als vaste "
            "medewerkers, maar hebben vaak minder binding met de organisatie. "
            "Contractuele beveiligingseisen maken verwachtingen expliciet en "
            "afdwingbaar."
        ),
        "bewijslast": [
            "Standaard beveiligingsbijlage bij inhuurcontracten",
            "Getekende geheimhoudingsverklaringen voor contractanten",
            "Onboarding-checklist voor externe medewerkers met beveiligingsvereisten",
        ],
    },
    "A.6.7": {
        "normtekst": (
            "Maatregelen voor informatiebeveiliging moeten worden geïmplementeerd "
            "wanneer medewerkers op afstand werken om de informatie die buiten "
            "het terrein van de organisatie wordt benaderd, verwerkt of opgeslagen "
            "te beschermen."
        ),
        "interpretatie": (
            "Thuiswerken en onderweg werken vergroot het aanvalsoppervlak. "
            "Thuis-wifi, persoonlijke apparaten en gedeelde werkruimtes "
            "introduceren risico's die op kantoor niet bestaan. Remote work "
            "beleid moet deze risico's adresseren."
        ),
        "bewijslast": [
            "Remote work beveiligingsbeleid",
            "Technische maatregelen (VPN, MDM, versleutelde apparaten)",
            "Bewijs van communicatie van regels voor thuiswerken",
        ],
    },
    "A.6.8": {
        "normtekst": (
            "De organisatie moet een mechanisme bieden waarmee medewerkers "
            "waargenomen of vermoede informatiebeveiligingsgebeurtenissen "
            "kunnen rapporteren via passende kanalen."
        ),
        "interpretatie": (
            "Medewerkers zijn de eerste verdedigingslinie. Als het onduidelijk "
            "is hoe en waar je een verdacht incident meldt, worden veel "
            "incidenten nooit gemeld. Meldkanalen moeten laagdrempelig, "
            "bekend en veilig zijn."
        ),
        "bewijslast": [
            "Procedure voor melden van beveiligingsincidenten door medewerkers",
            "Bewijs van communicatie van meldkanalen (intranet, poster, onboarding)",
            "Registratie van ontvangen meldingen en opvolging",
        ],
    },
    # ---- Fysieke beheersmaatregelen (7.x) ----
    "A.7.1": {
        "normtekst": (
            "Beveiligde fysieke perimeters moeten worden gedefinieerd en gebruikt "
            "om gebieden die informatie en andere daarmee samenhangende activa "
            "bevatten te beschermen."
        ),
        "interpretatie": (
            "Fysieke beveiliging begint bij de buitendeur. Perimeters (hekken, "
            "deuren, toegangspassen) bepalen wie het gebouw, de serverruimte "
            "en gevoelige zones kan betreden. Meerdere beveiligingslagen "
            "(defense in depth) zijn de norm."
        ),
        "bewijslast": [
            "Plattegrond met beveiligingszones en toegangspunten",
            "Toegangsbeheersingsysteem (badlezers, sleutelregistratie)",
            "Procedure voor beheer van fysieke toegangsmiddelen",
        ],
    },
    "A.7.2": {
        "normtekst": (
            "Beveiligde zones moeten worden beschermd door passende "
            "toegangsbeheersmaatregelen en toegangspunten."
        ),
        "interpretatie": (
            "Niet iedereen hoeft overal te komen. Toegang tot serverruimtes, "
            "archieven en andere gevoelige zones moet worden beperkt tot "
            "geautoriseerde personen. Bezoekers moeten worden begeleid."
        ),
        "bewijslast": [
            "Toegangsrechtenmatrix voor fysieke zones",
            "Bezoekersregistratie en begeleidingsprocedure",
            "Bewijs van periodieke review van fysieke toegangsrechten",
        ],
    },
    "A.7.3": {
        "normtekst": (
            "Fysieke beveiligingsmaatregelen voor kantoren, ruimtes en "
            "faciliteiten moeten worden ontworpen en geïmplementeerd."
        ),
        "interpretatie": (
            "Kantoren bevatten gevoelige documenten, apparaten en gesprekken. "
            "Clean desk policy, vergrendelde kasten en privacyschermen zijn "
            "eenvoudige maar effectieve maatregelen. Sensitiviteit van het "
            "kantoor bepaalt de vereiste maatregelen."
        ),
        "bewijslast": [
            "Clean desk en clean screen policy",
            "Bewijs van beveiligde opslag voor gevoelige documenten (kluizen, afgesloten kasten)",
            "Bewijs van afdoende beveiliging vergaderruimtes voor vertrouwelijke gesprekken",
        ],
    },
    "A.7.4": {
        "normtekst": (
            "Fysieke locaties moeten continu worden gemonitord op onbevoegde fysieke toegang."
        ),
        "interpretatie": (
            "Monitoring detecteert indringers en onbevoegde toegang die "
            "preventieve maatregelen ontwijken. CCTV, alarmsystemen en "
            "toegangslogboeken vormen samen een detectielaag. Monitoring "
            "heeft alleen waarde als iemand ook reageert op alerts."
        ),
        "bewijslast": [
            "CCTV-systeem en retentiebeleid voor opnamen",
            "Alarmsysteem en respons procedure",
            "Toegangslogboeken en bewijs van periodieke review",
        ],
    },
    "A.7.5": {
        "normtekst": (
            "Bescherming tegen fysieke en omgevingsdreigingen, zoals "
            "natuurrampen en andere opzettelijke of onopzettelijke fysieke "
            "bedreigingen voor de infrastructuur, moet worden ontworpen en "
            "geïmplementeerd."
        ),
        "interpretatie": (
            "Brand, overstroming, stroomuitval en extreme temperaturen kunnen "
            "systemen vernietigen. Fysieke omgevingsmaatregelen (brandblusser, "
            "watermelding, UPS, airconditioning) beschermen de hardware. "
            "Risicolocaties vereisen extra aandacht."
        ),
        "bewijslast": [
            "Risicoanalyse fysieke omgevingsdreigingen",
            "Bewijs van aanwezigheid brandblussers, rookmelders en watermelders",
            "UPS/noodstroomvoorziening testresultaten",
            "Klimaatbeheersingssysteem en monitoringrecords",
        ],
    },
    "A.7.6": {
        "normtekst": (
            "Maatregelen voor beveiliging in beveiligde zones of zones met een "
            "hoog risico moeten worden ontworpen en toegepast."
        ),
        "interpretatie": (
            "Activiteiten in beveiligde zones (serverruimtes, datacenters) "
            "vereisen extra gedragsregels: geen eenzame aanwezigheid, logging "
            "van alle activiteiten, verbod op camera's of voedsel. Deze "
            "maatregelen reduceren insider threats."
        ),
        "bewijslast": [
            "Gedragsregels voor beveiligde zones",
            "Logboek van toegang en activiteiten in serverruimte",
            "Procedure voor duo-controle bij kritieke handelingen",
        ],
    },
    "A.7.7": {
        "normtekst": (
            "Medewerkers en externe partijen die gebruikmaken van of toegang "
            "hebben tot activa van de organisatie moeten een clean desk beleid "
            "voor papieren documenten en verwijderbare opslagmedia toepassen "
            "en een clean screen beleid voor informatiefaciliteiten."
        ),
        "interpretatie": (
            "Documenten en schermen die zichtbaar zijn voor onbevoegden zijn "
            "een eenvoudig te misbruiken informatiebron. Clean desk/screen "
            "beleid is een basismaatregel die weinig kost maar veel oplevert. "
            "Effectiviteit vereist naleving en controle."
        ),
        "bewijslast": [
            "Clean desk en clean screen policy",
            "Bewijs van communicatie en naleving (steekproefcontroles)",
            "Screensaver- en vergrendelbeleid technisch afgedwongen",
        ],
    },
    "A.7.8": {
        "normtekst": (
            "Apparatuur moet op geschikte locaties worden geplaatst en beschermd "
            "om de risico's van omgevingsdreigingen en -gevaren en de "
            "mogelijkheid van onbevoegde toegang te verminderen."
        ),
        "interpretatie": (
            "Servers in een overstroombare kelder of beeldschermen zichtbaar "
            "vanaf de straat zijn onnodige risico's. De plaatsing van apparatuur "
            "moet weloverwogen zijn. Bekabeling moet worden beschermd tegen "
            "afluisteren en beschadiging."
        ),
        "bewijslast": [
            "Locatieplan apparatuur met verantwoording beveiligingskeuzes",
            "Bewijs van bescherming bekabeling (kabelgoten, afscherming)",
            "Datacenterinrichtingsdocumentatie",
        ],
    },
    "A.7.9": {
        "normtekst": (
            "Activa buiten het terrein moeten worden beschermd. Het risiconiveau "
            "van activa buiten het terrein van de organisatie moet in acht worden "
            "genomen en passende maatregelen moeten worden toegepast."
        ),
        "interpretatie": (
            "Laptops, smartphones en USB-sticks worden meegenomen buiten "
            "het beveiligde kantoor. Diefstal of verlies is een reëel risico. "
            "Encryptie van apparaten en data is de meest effectieve maatregel "
            "voor assets buiten de deur."
        ),
        "bewijslast": [
            "Beleid voor gebruik van activa buiten het terrein",
            "Bewijs van versleuteling van mobiele apparaten",
            "Procedure voor melding en opvolging van verlies of diefstal",
        ],
    },
    "A.7.10": {
        "normtekst": (
            "Opslagmedia moeten worden beheerd gedurende hun levenscyclus van "
            "verwerving, gebruik, transport en verwijdering in overeenstemming "
            "met het classificatieschema en de behandelingseisen van de organisatie."
        ),
        "interpretatie": (
            "USB-sticks, harde schijven en back-uptapes bevatten gevoelige data "
            "die niet zomaar in de prullenbak mogen. Veilige verwijdering "
            "(wissen, degaussen, fysiek vernietigen) voorkomt datalekken. "
            "Transport van media vereist ook bescherming."
        ),
        "bewijslast": [
            "Mediabeheerprocedure (registratie, gebruik, transport, verwijdering)",
            "Records van veilige mediaverwijdering (certificaten van vernietiging)",
            "Bewijs van versleuteling van verwijderbare media",
        ],
    },
    "A.7.11": {
        "normtekst": (
            "Informatiefaciliteiten moeten worden beschermd tegen "
            "stroomonderbrekingen en andere storingen als gevolg van "
            "uitval van ondersteunende nutsvoorzieningen."
        ),
        "interpretatie": (
            "Stroomuitval kan leiden tot dataverlies, systeemschade en "
            "bedrijfsonderbreking. UPS-systemen, noodgeneratoren en "
            "meervoudige stroomtoevoer zijn standaard maatregelen voor "
            "kritieke informatiesystemen."
        ),
        "bewijslast": [
            "UPS-systemen en testresultaten",
            "Noodstroomgenerator en periodieke testtrapport",
            "Meervoudige stroomvoeding documentatie voor kritieke systemen",
        ],
    },
    "A.7.12": {
        "normtekst": (
            "Bekabeling voor elektriciteit en telecommunicatie die gegevens "
            "transporteert of ondersteunende informatiediensten ondersteunt, "
            "moet worden beschermd tegen onderschepping, interferentie of schade."
        ),
        "interpretatie": (
            "Netwerkbekabeling die fysiek toegankelijk is kan worden afgeluisterd "
            "of beschadigd. Kabelgoten, afsluitbare patchkasten en scheiding "
            "van stroom- en datakabels reduceren dit risico."
        ),
        "bewijslast": [
            "Bekabelingsdocumentatie en -plattegrond",
            "Bewijs van bescherming van kritieke bekabeling (kabelgoten, afscherming)",
            "Inspectierecords van bekabelingsinfrastructuur",
        ],
    },
    "A.7.13": {
        "normtekst": (
            "Apparatuur moet correct worden onderhouden om de continue "
            "beschikbaarheid en integriteit te waarborgen."
        ),
        "interpretatie": (
            "Apparatuur die niet wordt onderhouden valt vaker uit en heeft "
            "een kortere levensduur. Gepland onderhoud voorkomt ongeplande "
            "uitval. Onderhoud door externe partijen moet worden beheerd "
            "vanuit beveiligingsperspectief."
        ),
        "bewijslast": [
            "Onderhoudsschema voor kritieke apparatuur",
            "Onderhoudsrecords (interne en externe onderhoud)",
            "Procedure voor beveiligingsbeheer bij extern onderhoud",
        ],
    },
    "A.7.14": {
        "normtekst": (
            "Onderdelen van apparatuur die opslagmedia bevatten, moeten worden "
            "geverifieerd om te waarborgen dat gevoelige gegevens en gelicentieerde "
            "software zijn gewist of veilig overschreven of vernietigd voordat "
            "de apparatuur wordt afgestoten of hergebruikt."
        ),
        "interpretatie": (
            "Laptops, servers en printers die worden afgedankt of verkocht "
            "bevatten vaak nog gevoelige data. Simpelweg formatteren is "
            "onvoldoende; gespecialiseerde wissprocedures of fysieke vernietiging "
            "zijn noodzakelijk voor kritieke data."
        ),
        "bewijslast": [
            "Procedure voor veilige dataverwijdering voor afstoting apparatuur",
            "Records van gegevenswissing (NIST 800-88 of equivalent)",
            "Certificaten van vernietiging bij fysieke vernietiging",
        ],
    },
    # ---- Technologische beheersmaatregelen (8.x) ----
    "A.8.1": {
        "normtekst": (
            "Informatie op gebruikerseindpuntapparaten moet worden beschermd. "
            "De organisatie moet beleid en ondersteunende technische maatregelen "
            "vaststellen voor het veilig beheren van gebruikerseindpuntapparaten."
        ),
        "interpretatie": (
            "Laptops, smartphones en tablets zijn de meest kwetsbare schakel "
            "in de beveiligingsketen. Ze gaan mee naar buiten, worden verloren "
            "en gerepareerd door derden. MDM, encryptie en remote-wipe zijn "
            "basismaatregelen."
        ),
        "bewijslast": [
            "Eindpuntbeveiligingsbeleid (BYOD, corporate devices)",
            "MDM-configuratie en compliance rapport",
            "Bewijs van encryptie op alle beheerde eindpunten",
        ],
    },
    "A.8.2": {
        "normtekst": (
            "Privileged access rights moeten worden beperkt en beheerd "
            "overeenkomstig het toegangsbeheersingsbeleid en de regels voor "
            "toegangsbeheersing."
        ),
        "interpretatie": (
            "Beheerdersaccounts zijn de meest waardevolle doelwitten voor "
            "aanvallers. Het principe van least privilege beperkt de schade "
            "als een account wordt gecompromitteerd. PAM-tools en aparte "
            "beheerdersaccounts zijn standaard praktijk."
        ),
        "bewijslast": [
            "Privileged Access Management (PAM) procedure",
            "Register van privileged accounts",
            "Bewijs van scheiding van beheerdersaccounts van reguliere accounts",
            "Periodieke review van privileged accounts",
        ],
    },
    "A.8.3": {
        "normtekst": (
            "Toegang tot informatie en andere daarmee samenhangende activa "
            "moet worden beperkt overeenkomstig het vastgestelde themaspecifieke "
            "beleid voor toegangsbeheersing."
        ),
        "interpretatie": (
            "Informatiebeperkingen worden technisch afgedwongen via bestandsrechten, "
            "databasepermissies en applicatiemachtigingen. Het beleid stelt de "
            "regels; technische implementatie zorgt voor naleving. "
            "Periodieke controle sluit de cirkel."
        ),
        "bewijslast": [
            "Toegangsrechtenconfiguratie per systeem/applicatie",
            "Resultaten van access review per systeem",
            "Bewijs van need-to-know principe in rechtenstructuur",
        ],
    },
    "A.8.4": {
        "normtekst": (
            "Toegang tot broncode, ontwikkelgereedschappen en software libraries "
            "moet op passende wijze worden beheerd."
        ),
        "interpretatie": (
            "Broncode bevat intellectueel eigendom en vaak hardcoded credentials "
            "of beveiligingsgevoelige logica. Ongecontroleerde toegang tot "
            "broncode vergroot het risico op sabotage, diefstal en kwetsbaarheden "
            "in productiesystemen."
        ),
        "bewijslast": [
            "Toegangsbeheersing op broncoderepositories (Git, SVN)",
            "Bewijs van code review procedure voor wijzigingen",
            "Bewijs dat productie-credentials niet in broncode worden opgeslagen",
        ],
    },
    "A.8.5": {
        "normtekst": (
            "Veilige authenticatieprocedures en -technologieën moeten worden "
            "geïmplementeerd op basis van beperkingen voor informatiebeheer "
            "en in overeenstemming met het themaspecifieke beleid voor "
            "toegangsbeheersing."
        ),
        "interpretatie": (
            "Wachtwoorden alleen zijn onvoldoende voor kritieke systemen. "
            "Multi-factor authenticatie, SSO en sterke authenticatieprotocollen "
            "reduceren het risico van gecompromitteerde credentials significant. "
            "De methode moet passen bij de sensitiviteit van het systeem."
        ),
        "bewijslast": [
            "MFA-implementatie op kritieke en externe toegangspunten",
            "Authenticatieconfiguratie per systeem",
            "Wachtwoordbeleid technisch afgedwongen (complexity, length, history)",
        ],
    },
    "A.8.6": {
        "normtekst": (
            "Het gebruik van middelen moet worden gemonitord en aangepast "
            "overeenkomstig de actuele en verwachte capaciteitseisen."
        ),
        "interpretatie": (
            "Systemen die vol raken of overbelast zijn, presteren slecht of "
            "vallen uit. Capaciteitsmonitoring voorkomt verrassingen en "
            "maakt proactieve opschaling mogelijk. Dit is ook relevant voor "
            "het voorkomen van denial-of-service effecten."
        ),
        "bewijslast": [
            "Capaciteitsmonitoringssysteem en dashboards",
            "Procedure voor capaciteitsplanning en -uitbreiding",
            "Historische capaciteitsdata en trendanalyses",
        ],
    },
    "A.8.7": {
        "normtekst": (
            "Bescherming tegen malware moet worden geïmplementeerd en "
            "ondersteund door passend bewustzijn van gebruikers."
        ),
        "interpretatie": (
            "Malware is een van de meest voorkomende en schadelijke dreigingen. "
            "Anti-malwareoplossingen moeten worden bijgehouden, gecombineerd "
            "met gebruikersbewustzijn over phishing en verdachte downloads. "
            "Alleen techniek of alleen bewustzijn is onvoldoende."
        ),
        "bewijslast": [
            "Anti-malware configuratie en updatebeleid",
            "Malwarescan resultaten en respons op detecties",
            "Security awareness training inclusief phishing-simulaties",
        ],
    },
    "A.8.8": {
        "normtekst": (
            "Informatie over technische kwetsbaarheden van gebruikte "
            "informatiesystemen moet tijdig worden verkregen, de blootstelling "
            "van de organisatie aan dergelijke kwetsbaarheden moet worden "
            "beoordeeld en passende maatregelen moeten worden genomen."
        ),
        "interpretatie": (
            "Kwetsbaarheden worden dagelijks ontdekt en gepubliceerd. Een "
            "systematisch patchproces en kwetsbaarhedenbeheer verkleint het "
            "venster van blootstelling. Niet patchen is de meest voorkomende "
            "oorzaak van succesvolle cyberaanvallen."
        ),
        "bewijslast": [
            "Kwetsbaarhedenscanresultaten (bijv. Nessus, Qualys)",
            "Patchbeheer procedure en patchstatus per systeem",
            "SLA voor patchimplementatie op basis van risiconiveau",
        ],
    },
    "A.8.9": {
        "normtekst": (
            "Configuraties, inclusief beveiligingsconfiguraties, van hardware, "
            "software, diensten en netwerken moeten worden vastgesteld, "
            "gedocumenteerd, geïmplementeerd, gemonitord en beoordeeld."
        ),
        "interpretatie": (
            "Standaard configuraties zijn zelden veilig. Hardening op basis "
            "van CIS benchmarks of vergelijkbare standaarden verwijdert onnodige "
            "services en sluit bekende kwetsbaarheden. Configuratiedrift is "
            "een sluipend beveiligingsrisico."
        ),
        "bewijslast": [
            "Hardening-baselines per systeem/platform (CIS benchmarks)",
            "Configuratiebeheer database (CMDB) of gelijkwaardig",
            "Bewijs van configuratiemonitoring en detectie van drift",
        ],
    },
    "A.8.10": {
        "normtekst": (
            "Informatie die is opgeslagen in informatiesystemen, apparaten of "
            "andere opslagmedia moet worden verwijderd wanneer deze niet langer "
            "benodigd is."
        ),
        "interpretatie": (
            "Data die je niet meer nodig hebt maar wel bewaart, is een onnodige "
            "blootstelling. Data minimalisatie (AVG-principe) en veilige "
            "verwijdering verkleinen het risico bij een datalek. "
            "Retentiebeleid bepaalt wanneer data weg mag."
        ),
        "bewijslast": [
            "Dataverwerkings- en retentiebeleid",
            "Procedure voor veilige dataverwijdering",
            "Records van uitgevoerde dataverwijdering",
        ],
    },
    "A.8.11": {
        "normtekst": (
            "Maatregelen voor data masking moeten worden geïmplementeerd "
            "overeenkomstig het themaspecifieke beleid voor toegangsbeheersing "
            "van de organisatie en andere gerelateerde themaspecifieke beleidslijnen "
            "en bedrijfseisen, rekening houdend met toepasselijke wetgeving."
        ),
        "interpretatie": (
            "Test- en ontwikkelomgevingen mogen geen echte persoonsgegevens "
            "bevatten. Data masking, anonimisering en pseudonimisering "
            "beschermen privacy in niet-productieomgevingen. Dit is ook een "
            "AVG-verplichting."
        ),
        "bewijslast": [
            "Beleid voor gebruik van testdata",
            "Bewijs van data masking in test-/ontwikkelomgevingen",
            "Procedure voor pseudonimisering of anonimisering",
        ],
    },
    "A.8.12": {
        "normtekst": (
            "Maatregelen voor preventie van datalekken moeten worden toegepast "
            "op systemen, netwerken en andere apparaten die gevoelige informatie "
            "verwerken, opslaan of transporteren."
        ),
        "interpretatie": (
            "DLP-technologie detecteert en blokkeert ongeautoriseerde "
            "informatieoverdracht (e-mail, USB, cloud upload). Het is een "
            "technische vangnet voor gevallen waar beleid en training "
            "onvoldoende zijn gebleken."
        ),
        "bewijslast": [
            "DLP-beleid en technische implementatie",
            "DLP-incidentenrapportage en opvolging",
            "Bewijs van monitoring op uitvoer van gevoelige data",
        ],
    },
    "A.8.13": {
        "normtekst": (
            "Back-upkopieën van informatie, software en systemen moeten worden "
            "gemaakt en regelmatig worden getest overeenkomstig het overeengekomen "
            "themaspecifieke beleid voor back-up."
        ),
        "interpretatie": (
            "Back-ups zijn de laatste verdedigingslinie tegen ransomware, "
            "datastoringen en menselijke fouten. Ongeteste back-ups zijn "
            "geen garantie. 3-2-1 regel (3 kopieën, 2 media, 1 offsite) "
            "is de basisnorm."
        ),
        "bewijslast": [
            "Back-upbeleid met RPO/RTO per systeem",
            "Back-uptestresultaten (restore tests)",
            "Bewijs van offsite of offline back-upopslag",
        ],
    },
    "A.8.14": {
        "normtekst": (
            "Informatiefaciliteiten moeten met voldoende redundantie worden "
            "geïmplementeerd om te voldoen aan beschikbaarheidseisen."
        ),
        "interpretatie": (
            "Kritieke systemen mogen geen single point of failure hebben. "
            "Redundantie (dubbele stroomtoevoer, failover-servers, "
            "load balancing) waarborgt beschikbaarheid ook bij storingen. "
            "De mate van redundantie moet aansluiten bij de bedrijfsbehoefte."
        ),
        "bewijslast": [
            "Architectuurdocumentatie met redundantiemaatregelen",
            "SLA's met beschikbaarheidsgaranties",
            "Failover-testresultaten",
        ],
    },
    "A.8.15": {
        "normtekst": (
            "Logboeken die activiteiten, uitzonderingen, fouten en andere "
            "relevante gebeurtenissen vastleggen, moeten worden geproduceerd, "
            "opgeslagen, beschermd en geanalyseerd."
        ),
        "interpretatie": (
            "Logging is de basis voor detectie, forensisch onderzoek en "
            "compliance. Logs moeten volledig, integer en voldoende lang "
            "bewaard zijn. Logs die alleen worden aangemaakt maar nooit "
            "worden geanalyseerd, hebben beperkte waarde."
        ),
        "bewijslast": [
            "Logbeleid (welke systemen loggen wat, retentietermijn)",
            "Bewijs van gecentraliseerde logopslag (SIEM)",
            "Bewijs van log-integriteitsbeveiliging (tamper protection)",
            "Bewijs van periodieke loganalyse of alerting",
        ],
    },
    "A.8.16": {
        "normtekst": (
            "Netwerken en systemen moeten worden gemonitord op afwijkend "
            "gedrag en passende maatregelen moeten worden genomen om potentiële "
            "informatiebeveiligingsincidenten te evalueren."
        ),
        "interpretatie": (
            "Monitoring detecteert aanvallen die preventieve maatregelen hebben "
            "omzeild. SIEM, IDS/IPS en anomaliedetectie zijn standaard tools. "
            "Monitoring heeft alleen waarde als er ook wordt gereageerd op "
            "alerts: een SOC of on-call procedure is noodzakelijk."
        ),
        "bewijslast": [
            "Monitoring- en alertingsysteem (SIEM, IDS)",
            "Alert response procedure",
            "Bewijs van opvolging van monitoringwaarschuwingen",
        ],
    },
    "A.8.17": {
        "normtekst": (
            "Klokken van informatieverwerkingssystemen die door de organisatie "
            "worden gebruikt, moeten worden gesynchroniseerd met goedgekeurde "
            "tijdbronnen."
        ),
        "interpretatie": (
            "Tijdsynchronisatie (NTP) is essentieel voor log-correlatie bij "
            "incidentonderzoek. Als systemen verschillende tijden hebben, "
            "is het reconstrueren van een aanval veel moeilijker. "
            "Dit is een eenvoudige maar kritieke maatregel."
        ),
        "bewijslast": [
            "NTP-configuratie op alle systemen",
            "Bewijs van gecentraliseerde tijdbron",
            "Monitoring op tijdafwijkingen",
        ],
    },
    "A.8.18": {
        "normtekst": (
            "Het gebruik van programma's met speciale beheerdersrechten "
            "die systeembeheersing kunnen omzeilen, moet worden beperkt "
            "en nauwkeurig worden bewaakt."
        ),
        "interpretatie": (
            "Utilities als netwerk-scanners, password crackers en directe "
            "databasetoegang zijn krachtige tools die ook door kwaadwillenden "
            "worden gebruikt. Gebruik moet geautoriseerd, beperkt en gelogd "
            "zijn."
        ),
        "bewijslast": [
            "Register van geautoriseerde beheerhulpprogramma's",
            "Procedure voor gebruik en logging van privileged utilities",
            "Bewijs van beperkte toegang tot systeembeheerhulpmiddelen",
        ],
    },
    "A.8.19": {
        "normtekst": (
            "Procedures en maatregelen voor de installatie van software op "
            "operationele systemen moeten worden geïmplementeerd."
        ),
        "interpretatie": (
            "Ongecontroleerde software-installatie is een veelvoorkomende "
            "bron van kwetsbaarheden en malware-infecties. Whitelisting, "
            "applicatiecatalogi en goedkeuringsprocessen beperken dit risico. "
            "Eindgebruikers mogen geen software installeren zonder toestemming."
        ),
        "bewijslast": [
            "Software installatie- en goedkeuringsbeleid",
            "Technische afdwinging (applicatie whitelisting of AppLocker)",
            "Bewijs van softwareinventarisatie en compliance",
        ],
    },
    "A.8.20": {
        "normtekst": (
            "Netwerken en netwerkapparaten moeten worden beveiligd, beheerd "
            "en bewaakt om informatie en informatiefaciliteiten te beschermen."
        ),
        "interpretatie": (
            "Het netwerk is de ruggengraat van informatieverwerking. "
            "Firewalls, netwerksegmentatie, veilige protocollen en "
            "netwerkmapping zijn basisvereisten. Een slecht beveiligd netwerk "
            "maakt andere maatregelen minder effectief."
        ),
        "bewijslast": [
            "Netwerkarchitectuurdocumentatie",
            "Firewallregels en change management procedure",
            "Bewijs van netwerksegmentatie (VLAN, DMZ)",
            "Netwerkmonitoringrapportages",
        ],
    },
    "A.8.21": {
        "normtekst": (
            "Beveiligingsmechanismen, service niveaus en beheersvereisten voor "
            "alle netwerkdiensten moeten worden geïdentificeerd, geïmplementeerd "
            "en gemonitord, of deze diensten nu intern worden geleverd of "
            "uitbesteed zijn."
        ),
        "interpretatie": (
            "Netwerkdiensten (DNS, DHCP, e-mail, VPN) moeten elk hun eigen "
            "beveiligingsconfiguratie hebben. Uitbestede netwerkdiensten "
            "vereisen contractuele beveiligingsgaranties en monitoring op "
            "naleving."
        ),
        "bewijslast": [
            "Inventaris van netwerkdiensten met beveiligingsconfiguratie",
            "SLA's voor externe netwerkdiensten met beveiligingseisen",
            "Bewijs van monitoring op netwerkdienstenprestaties en beveiliging",
        ],
    },
    "A.8.22": {
        "normtekst": (
            "Groepen van informatiediensten, gebruikers en informatiesystemen "
            "moeten in netwerken worden gesegmenteerd."
        ),
        "interpretatie": (
            "Netwerksegmentatie beperkt de schade als een aanvaller toegang "
            "krijgt tot één segment: laterale beweging wordt bemoeilijkt. "
            "Kritieke systemen (OT, financieel, HR) moeten in aparte segmenten "
            "met strikte toegangsregels."
        ),
        "bewijslast": [
            "Netwerksegmentatiearchitectuur (VLAN, firewall zones)",
            "Bewijs van scheiding productie-, test- en beheersegmenten",
            "Firewallregels tussen segmenten en audit van regelsets",
        ],
    },
    "A.8.23": {
        "normtekst": (
            "Toegang tot externe websites moet worden beheerd om blootstelling "
            "aan kwaadaardige content te verminderen."
        ),
        "interpretatie": (
            "Webfiltering blokkeert toegang tot kwaadaardige, ongepaste of "
            "niet-zakelijke websites. Dit verkleint het risico van drive-by "
            "downloads, phishing en datalekkage. De filterregels moeten "
            "worden bijgehouden en afgestemd op bedrijfsbehoeften."
        ),
        "bewijslast": [
            "Webfilterbeleid en categorie-instellingen",
            "Webfilter configuratie en rapportages",
            "Procedure voor whitelist/blacklist uitzonderingen",
        ],
    },
    "A.8.24": {
        "normtekst": (
            "Regels voor het gebruik van cryptografie, inclusief beheer van "
            "cryptografische sleutels, moeten worden vastgesteld en geïmplementeerd."
        ),
        "interpretatie": (
            "Cryptografie beschermt data in rust en in transit. Maar slecht "
            "sleutelbeheer ondermijnt de sterkste encryptie. Je moet expliciet "
            "bepalen welke algoritmen worden gebruikt, hoe sleutels worden "
            "opgeslagen en wanneer ze worden vervangen."
        ),
        "bewijslast": [
            "Cryptografiebeleid (algoritmen, sleutellengtes, protocollen)",
            "Sleutelbeheer procedure (generatie, opslag, rotatie, intrekking)",
            "Bewijs van encryptie in transit (TLS-configuratie) en in rust",
        ],
    },
    "A.8.25": {
        "normtekst": (
            "Regels voor de veilige ontwikkeling van software en systemen moeten "
            "worden vastgesteld en toegepast op ontwikkelingen binnen de organisatie."
        ),
        "interpretatie": (
            "Security moet worden ingebakken in het ontwikkelproces, niet er "
            "achteraf in worden gestopt. Secure coding standards, security "
            "reviews en SAST-tools zijn onderdeel van een volwassen "
            "ontwikkelproces."
        ),
        "bewijslast": [
            "Secure development lifecycle (SDLC) procedure",
            "Secure coding guidelines",
            "Bewijs van security reviews in het ontwikkelproces",
        ],
    },
    "A.8.26": {
        "normtekst": (
            "Informatiebeveiligingseisen moeten worden geïdentificeerd, "
            "gespecificeerd en goedgekeurd bij het ontwikkelen of verwerven "
            "van applicaties."
        ),
        "interpretatie": (
            "Applicatiebeveiligingseisen moeten worden bepaald voordat "
            "ontwikkeling of inkoop begint. Achteraf toevoegen van beveiliging "
            "is duurder en levert minder robuuste resultaten. Dit geldt ook "
            "voor SaaS en commerciële pakketten."
        ),
        "bewijslast": [
            "Beveiligingseisen in systeemspecificaties of RFP's",
            "Security requirements per applicatieclassificatie",
            "Bewijs van beveiligingsbeoordeling bij aanschaf of oplevering",
        ],
    },
    "A.8.27": {
        "normtekst": (
            "Principes voor het ontwerpen van veilige systemen moeten worden "
            "vastgesteld, gedocumenteerd, onderhouden en toegepast op "
            "informatiecysteem-implementatiewerkzaamheden."
        ),
        "interpretatie": (
            "Principes als least privilege, defense in depth, fail secure "
            "en zero trust moeten worden verankerd in het ontwerpproces. "
            "Door deze principes expliciet te maken, worden ze reproduceerbaar "
            "toegepast in nieuwe systemen."
        ),
        "bewijslast": [
            "Security by design principes document",
            "Bewijs van toepassing in architectuurreviews",
            "Security architecture review records voor nieuwe systemen",
        ],
    },
    "A.8.28": {
        "normtekst": ("Veilige codeerpraktijken moeten worden toegepast op softwareontwikkeling."),
        "interpretatie": (
            "OWASP Top 10 kwetsbaarheden (SQL-injectie, XSS, etc.) zijn "
            "al decennia bekend en toch komen ze nog steeds voor. Secure "
            "coding training, peer reviews en SAST-tools reduceren deze "
            "kwetsbaarheden systematisch."
        ),
        "bewijslast": [
            "Secure coding standaard (OWASP of equivalent)",
            "SAST/DAST-toolresultaten in CI/CD pipeline",
            "Bewijs van code review voor beveiligingsgerelateerde wijzigingen",
        ],
    },
    "A.8.29": {
        "normtekst": (
            "Beveiligingstestprocessen moeten worden gedefinieerd en "
            "geïmplementeerd in de ontwikkellevenscyclus."
        ),
        "interpretatie": (
            "Testen voor ingebruikname detecteert beveiligingsfouten voordat "
            "ze in productie komen. Penetratietests, vulnerability scans en "
            "security acceptance tests zijn onderdeel van een volwassen "
            "testproces."
        ),
        "bewijslast": [
            "Beveiligingstestprocedure in SDLC",
            "Penetratietestrapportages en opvolging bevindingen",
            "Security acceptance test criteria en resultaten",
        ],
    },
    "A.8.30": {
        "normtekst": (
            "Uitbestede ontwikkeling moet worden gesuperviseerd en gemonitord door de organisatie."
        ),
        "interpretatie": (
            "Als ontwikkeling wordt uitbesteed, behoud je als organisatie "
            "de verantwoordelijkheid voor de beveiliging van het eindproduct. "
            "Contractuele eisen, code reviews en beveiligingstests moeten "
            "ook bij uitbesteding worden gewaarborgd."
        ),
        "bewijslast": [
            "Contractuele beveiligingseisen voor uitbestede ontwikkeling",
            "Bewijs van beveiligingsbeoordeling opgeleverde code",
            "Procedure voor acceptatietests bij uitbestede ontwikkeling",
        ],
    },
    "A.8.31": {
        "normtekst": (
            "Ontwikkel-, test- en productieomgevingen moeten van elkaar worden "
            "gescheiden en beveiligd."
        ),
        "interpretatie": (
            "Ontwikkelaars die directe toegang hebben tot productiesystemen "
            "zijn een significant risico. Omgevingsscheiding voorkomt dat "
            "testactiviteiten productie verstoren en dat productiedata in "
            "ontwikkelomgevingen terechtkomen."
        ),
        "bewijslast": [
            "Documentatie van omgevingsscheiding (DTAP)",
            "Toegangsbeheersing per omgeving",
            "Procedure voor promotie van code tussen omgevingen",
        ],
    },
    "A.8.32": {
        "normtekst": (
            "Wijzigingen in informatiefaciliteiten en informatiesystemen moeten "
            "worden beheerst door middel van wijzigingsbeheer procedures."
        ),
        "interpretatie": (
            "Ongecontroleerde wijzigingen zijn een van de grootste oorzaken "
            "van storingen en beveiligingsincidenten. Change management "
            "zorgt voor beoordeling, goedkeuring, testen en documentatie "
            "van elke wijziging in productieomgevingen."
        ),
        "bewijslast": [
            "Change management procedure (CAB of equivalent)",
            "Change log met alle wijzigingen en goedkeuringsrecords",
            "Bewijs van impact- en risicoanalyse per change",
            "Rollback procedure per change",
        ],
    },
    "A.8.33": {
        "normtekst": ("Testinformatie moet worden geselecteerd, beschermd en beheerd."),
        "interpretatie": (
            "Testomgevingen bevatten vaak kopieën van productiedata. Als "
            "testdata niet wordt beschermd, kan gevoelige informatie lekken "
            "via ontwikkelaars of leveranciers. Data masking of synthetische "
            "testdata zijn de oplossing."
        ),
        "bewijslast": [
            "Beleid voor gebruik en bescherming van testdata",
            "Bewijs van data masking of anonimisering in testomgevingen",
            "Toegangsbeheersing op testomgevingen met gevoelige data",
        ],
    },
    "A.8.34": {
        "normtekst": (
            "Informatiesystemen moeten worden beschermd tijdens audittests om "
            "verstoring van bedrijfsprocessen en gebruikte auditgereedschappen "
            "te minimaliseren."
        ),
        "interpretatie": (
            "Audittests (penetratietests, vulnerability scans) kunnen systemen "
            "belasten of tijdelijk verstoren. Door goede afspraken te maken "
            "over scope, timing en autorisatie voorkom je onnodige verstoring "
            "en juridische problemen."
        ),
        "bewijslast": [
            "Geautoriseerde scope en planning voor audittests",
            "Schriftelijke toestemming voor penetratietests",
            "Procedure voor beheer van audittools en -toegang",
        ],
    },
    "4.1": {
        "titel": "Inzicht verkrijgen in de organisatie en haar context",
        "normtekst": "De organisatie moet externe en interne onderwerpen vaststellen die relevant zijn voor haar doelstelling en die haar vermogen beïnvloeden om het (de) beoogde resulta(a)t(en) van haar managementsysteem voor informatiebeveiliging te behalen.",
        "interpretatie": "De organisatie moet weten waarin zij opereert voordat zij kan bepalen wat zij moet beschermen. Zonder vastgelegde context is de scope een aanname en zijn de risico's niet herleidbaar naar iets buiten de organisatie.",
        "bewijslast": [
            "Contextanalyse of SWOT met interne en externe onderwerpen",
            "Vastlegging wanneer de analyse voor het laatst is herzien",
            "Aantoonbare doorwerking naar de risicobeoordeling",
        ],
    },
    "4.2": {
        "titel": "Inzicht verkrijgen in de behoeften en verwachtingen van belanghebbenden",
        "normtekst": "De organisatie moet vaststellen: a) welke belanghebbenden relevant zijn voor het managementsysteem voor informatiebeveiliging, en b) welke eisen van deze belanghebbenden relevant zijn voor informatiebeveiliging. Dit document is door NEN onder licentie verstrekt aan: / This document has been supplied under license by NEN to: European Certification Bureau B.V. H.J. Bloemers 2018/11/26 NEN-EN-ISO/IEC 27001:2017 9",
        "interpretatie": "Belanghebbenden stellen eisen die de organisatie niet zelf kiest: klanten, toezichthouders, leveranciers. Wie ze niet in kaart heeft, ontdekt hun eisen pas bij een incident of een audit.",
        "bewijslast": [
            "Overzicht van belanghebbenden met hun eisen",
            "Herleiding van contractuele en wettelijke eisen naar deze lijst",
            "Datum van laatste actualisatie",
        ],
    },
    "4.3": {
        "titel": "Het toepassingsgebied van het managementsysteem voor informatiebeveiliging",
        "normtekst": "vaststellen De organisatie moet de grenzen en toepasselijkheid van het managementsysteem voor informatiebeveiliging bepalen om het toepassingsgebied ervan vast te stellen. Bij het vaststellen van dit toepassingsgebied moet de organisatie: a) de in 4.1 genoemde externe en interne onderwerpen overwegen, evenals; b) de in 4.2 genoemde eisen, en c) raakvlakken en afhankelijkheden tussen de activiteiten die door de organisatie en de activiteiten die door andere organisaties worden verricht. Het toepassingsgebied moet als gedocumenteerde informatie beschikbaar zijn.",
        "interpretatie": "Het toepassingsgebied bepaalt waarover het certificaat iets zegt. Een scope die te ruim is, belooft meer dan er wordt beheerst; een die te krap is, laat gaten waar niemand naar kijkt.",
        "bewijslast": [
            "Scope statement met wat erbinnen en erbuiten valt",
            "Motivering van uitsluitingen",
            "Overeenstemming met de contextanalyse en de belanghebbenden",
        ],
    },
    "4.4": {
        "titel": "Managementsysteem voor informatiebeveiliging",
        "normtekst": "De organisatie moet een managementsysteem voor informatiebeveiliging inrichten, implementeren, onderhouden en continu verbeteren, in overeenstemming met de eisen van deze Internationale Norm. 5 Leiderschap",
        "interpretatie": "Een managementsysteem is meer dan een map documenten: het zijn processen die op elkaar aansluiten en die aantoonbaar draaien. Losse procedures zonder samenhang vormen geen systeem.",
        "bewijslast": [
            "Procesbeschrijving of -kaart van het ISMS",
            "Aantoonbare samenhang tussen processen",
            "Bewijs dat de processen daadwerkelijk draaien",
        ],
    },
    "5.1": {
        "titel": "Leiderschap en betrokkenheid",
        "normtekst": "De directie moet leiderschap en betrokkenheid tonen met betrekking tot het managementsysteem voor informatiebeveiliging door: a) te bewerkstelligen dat het informatiebeveiligingsbeleid en de informatiebeveiligingsdoelstellingen worden vastgesteld en aansluiten bij de strategische richting van de organisatie; b) te bewerkstelligen dat de eisen van het managementsysteem voor informatiebeveiliging in de processen van de organisatie worden geïntegreerd; c) te bewerkstelligen dat de voor het managementsysteem voor informatiebeveiliging benodigde middelen beschikbaar zijn; d) het belang van een doel",
        "interpretatie": "De directie kan informatiebeveiliging niet delegeren en er verder van wegblijven. Zonder zichtbare betrokkenheid krijgt het onderwerp geen middelen en geen voorrang zodra het botst met iets anders.",
        "bewijslast": [
            "Notulen waarin de directie besluiten over informatiebeveiliging neemt",
            "Toegewezen middelen en budget",
            "Directiebeoordeling met aantoonbare opvolging",
        ],
    },
    "5.2": {
        "titel": "Beleid",
        "normtekst": "De directie moet een informatiebeveiligingsbeleid vaststellen dat: a) passend is voor het doel van de organisatie; b) informatiebeveiligingsdoelstellingen bevat (zie 6.2) of het kader biedt voor het vaststellen van informatiebeveiligingsdoelstellingen; c) een verbintenis bevat om te voldoen aan van toepassing zijnde eisen in verband met informatiebeveiliging; en d) een verbintenis bevat tot continue verbetering van het managementsysteem voor informatiebeveiliging. Het beleid voor informatiebeveiliging moet: e) beschikbaar zijn als gedocumenteerde informatie; f) worden gecommuniceerd binnen de ",
        "interpretatie": "Beleid is de plek waar de organisatie vastlegt wat zij wil. Een beleid dat niet is gecommuniceerd of jaren niet is herzien, stuurt niets aan.",
        "bewijslast": [
            "Vastgesteld informatiebeveiligingsbeleid met datum en eigenaar",
            "Bewijs van communicatie naar medewerkers",
            "Versiehistorie en datum van de laatste beoordeling",
        ],
    },
    "5.3": {
        "titel": "Rollen, verantwoordelijkheden en bevoegdheden binnen de organisatie",
        "normtekst": "De directie moet bewerkstelligen dat de verantwoordelijkheden en bevoegdheden voor rollen die relevant zijn voor informatiebeveiliging worden toegekend en gecommuniceerd. De directie moet de verantwoordelijkheid en bevoegdheid toekennen met betrekking tot: a) het bewerkstelligen dat het managementsysteem voor informatiebeveiliging voldoet aan de eisen van deze Internationale Norm; en b) het rapporteren over de prestaties van het managementsysteem voor informatiebeveiliging aan de directie.",
        "interpretatie": "Wie is waarvoor verantwoordelijk, en met welke bevoegdheid. Zonder die toewijzing valt werk tussen wal en schip en is achteraf niet vast te stellen wie had moeten handelen.",
        "bewijslast": [
            "Rollenoverzicht met verantwoordelijkheden en bevoegdheden",
            "Aantoonbare communicatie van die rollen",
            "Vervanging bij afwezigheid of vertrek",
        ],
    },
    "6.1": {
        "titel": "Maatregelen om risico’s te beperken en kansen te benutten",
        "normtekst": "6.1.1 Algemeen Bij het plannen voor het managementsysteem voor informatiebeveiliging moet de organisatie de in 4.1 genoemde onderwerpen en de in 4.2 genoemde eisen overwegen, en de risico’s en kansen vaststellen die moeten worden aangepakt om: a) te bewerkstelligen dat het managementsysteem voor informatiebeveiliging zijn beoogde resulta(a)t(en) behaalt; Dit document is door NEN onder licentie verstrekt aan: / This document has been supplied under license by NEN to: European Certification Bureau B.V. H.J. Bloemers 2018/11/26 NEN-EN-ISO/IEC 27001:2017 11 b) ongewenste effecten te voorkomen of t",
        "interpretatie": "Risico's en kansen bepalen waar de organisatie haar aandacht heenbrengt. Een systeem dat alleen op incidenten reageert, loopt per definitie achter.",
        "bewijslast": [
            "Vastgelegde aanpak voor risico's en kansen",
            "Herleiding naar de context uit 4.1 en 4.2",
            "Bewijs dat maatregelen zijn geëvalueerd op doeltreffendheid",
        ],
    },
    "6.1.2": {
        "titel": "Risicobeoordeling van informatiebeveiliging",
        "normtekst": "De organisatie moet een risicobeoordelingsprocedure voor informatiebeveiliging definiëren en toepassen die: a) risicocriteria voor informatiebeveiliging vaststelt en onderhoudt, waaronder: 1) de risicoacceptatiecriteria; en 2) criteria voor het verrichten van risicobeoordelingen van informatiebeveiliging; b) waarborgt dat herhaalde risicobeoordelingen van informatiebeveiliging consistente, geldige en vergelijkbare resultaten opleveren; c) de informatiebeveiligingsrisico’s identificeert: 1) het risicobeoordelingsproces voor informatiebeveiliging toepassen om de risico’s in verband met het verli",
        "interpretatie": "Zonder vaste criteria is elke risicobeoordeling een momentopname van wie hem toevallig deed. Reproduceerbaarheid is hier de eis, niet de precisie.",
        "bewijslast": [
            "Risicocriteria voor aanvaarding en voor het uitvoeren van beoordelingen",
            "Risicoregister met eigenaren",
            "Twee opeenvolgende beoordelingen die vergelijkbaar zijn",
        ],
    },
    "6.1.3": {
        "titel": "Behandeling van informatiebeveiligingsrisico’s",
        "normtekst": "De organisatie moet een behandelprocedure voor informatiebeveiligingsrisico’s definiëren en toepassen om: a) passende opties voor het behandelen van informatiebeveiligingsrisico’s te kiezen, rekening houdend met de resultaten van de risicobeoordeling; b) alle beheersmaatregelen vast te stellen die nodig zijn om de gekozen optie(s) voor het behandelen van informatiebeveiligingsrisico’s te implementeren;",
        "interpretatie": "De Verklaring van Toepasselijkheid is het scharnier van de norm: zij verbindt de risico's aan de maatregelen en verantwoordt wat níet is toegepast.",
        "bewijslast": [
            "Verklaring van Toepasselijkheid met motivering per maatregel",
            "Risicobehandelplan met eigenaren en termijnen",
            "Goedkeuring door de risico-eigenaren",
        ],
    },
    "6.2": {
        "titel": "Informatiebeveiligingsdoelstellingen en de planning om ze te bereiken",
        "normtekst": "De organisatie moet voor relevante functies en op relevante niveaus informatiebeveiligingsdoelstellingen vaststellen. De informatiebeveiligingsdoelstellingen moeten: Dit document is door NEN onder licentie verstrekt aan: / This document has been supplied under license by NEN to: European Certification Bureau B.V. H.J. Bloemers 2018/11/26 NEN-EN-ISO/IEC 27001:2017 13 a) consistent zijn met het informatiebeveiligingsbeleid; b) meetbaar zijn (indien praktisch uitvoerbaar); c) rekening houden met van toepassing zijnde informatiebeveiligingseisen en resultaten van risicobeoordeling en -behandeling;",
        "interpretatie": "Doelstellingen maken het verschil tussen willen en sturen. Een doel zonder meetpunt en termijn is een intentie.",
        "bewijslast": [
            "Meetbare doelstellingen met termijn en eigenaar",
            "Voortgangsrapportage",
            "Aantoonbare samenhang met het beleid",
        ],
    },
    "6.3": {
        "titel": "Planning van wijzigingen",
        "normtekst": "Wanneer de organisatie vaststelt dat het managementsysteem voor informatiebeveiliging moet worden gewijzigd, moeten de wijzigingen op een geplande wijze worden uitgevoerd.",
        "interpretatie": "Wijzigingen aan het managementsysteem zelf zijn een risico: wie de scope of een proces aanpast zonder plan, verliest de aansluiting met de rest.",
        "bewijslast": [
            "Vastlegging van wijzigingen aan het ISMS",
            "Onderbouwing en planning per wijziging",
            "Doorwerking naar de betrokken documenten",
        ],
    },
    "7.1": {
        "titel": "Middelen",
        "normtekst": "De organisatie moet de middelen vaststellen en beschikbaar stellen die nodig zijn voor het inrichten, implementeren, onderhouden en continu verbeteren van het managementsysteem voor informatiebeveiliging.",
        "interpretatie": "Middelen zijn de toets of de rest van het systeem meer is dan papier. Een plan zonder mensen, tijd of budget wordt niet uitgevoerd.",
        "bewijslast": [
            "Toegewezen budget of formatie voor informatiebeveiliging",
            "Aantoonbare beschikbaarheid van de benodigde middelen",
            "Besluitvorming bij schaarste",
        ],
    },
    "7.2": {
        "titel": "Competentie",
        "normtekst": "De organisatie moet: a) de noodzakelijke competentie vaststellen van de perso(o)n(en) die onder haar gezag werkzaamheden verricht(en) die de prestaties van de organisatie op het gebied van informatiebeveiliging beïnvloeden; b) bewerkstelligen dat deze personen competent zijn op basis van de juiste scholing, opleiding of ervaring; c) waar van toepassing, maatregelen nemen om de benodigde competentie te verwerven, en de doeltreffendheid van de genomen maatregelen evalueren; en d) geschikte gedocumenteerde informatie als bewijsmateriaal van competentie bewaren.",
        "interpretatie": "Competentie is aantoonbaar kunnen, niet aanwezig zijn. De organisatie moet weten welke kennis nodig is en of die er is.",
        "bewijslast": [
            "Competentieprofiel per rol",
            "Bewijs van opleiding, certificering of ervaring",
            "Actie bij een geconstateerd hiaat",
        ],
    },
    "7.3": {
        "titel": "Bewustzijn",
        "normtekst": "Personen die werkzaamheden verrichten onder het gezag van de organisatie, moeten zich bewust zijn van: a) het informatiebeveiligingsbeleid; b) hun bijdrage aan de doeltreffendheid van het managementsysteem voor informatiebeveiliging, met inbegrip van de voordelen van verbeterde informatiebeveiligingsprestaties; c) de gevolgen van het niet voldoen aan de eisen van het managementsysteem voor informatiebeveiliging.",
        "interpretatie": "Bewustzijn gaat over de mensen die geen beveiligingsrol hebben. Zij nemen dagelijks de beslissingen waar de meeste incidenten uit voortkomen.",
        "bewijslast": [
            "Bewustwordingsprogramma met bereik en frequentie",
            "Deelnameregistratie",
            "Meting van het effect, bijvoorbeeld via phishing-oefeningen",
        ],
    },
    "7.4": {
        "titel": "Communicatie",
        "normtekst": "De organisatie moet de behoefte vaststellen aan interne en externe communicatie die relevant is voor het managementsysteem voor informatiebeveiliging, waaronder: a) waarover te communiceren; b) wanneer te communiceren; c) met wie te communiceren; d) wie moet communiceren; en e) volgens welke processen de communicatie moet plaatsvinden.",
        "interpretatie": "Communicatie is vastleggen wat er wanneer aan wie wordt gemeld. Zonder afspraak vooraf wordt tijdens een incident geïmproviseerd.",
        "bewijslast": [
            "Communicatieplan met onderwerp, moment, doelgroep en zender",
            "Bewijs van uitgevoerde communicatie",
            "Afspraken voor communicatie tijdens incidenten",
        ],
    },
    "7.5": {
        "titel": "Gedocumenteerde informatie",
        "normtekst": "7.5.1 Algemeen Het managementsysteem voor informatiebeveiliging van de organisatie moet onder andere bevatten: a) gedocumenteerde informatie die deze Internationale Norm vereist; en b) de gedocumenteerde informatie die de organisatie vaststelt als noodzakelijk voor de doeltreffendheid van het managementsysteem voor informatiebeveiliging.",
        "interpretatie": "Gedocumenteerde informatie is wat het systeem overdraagbaar maakt. Kennis die alleen in hoofden zit, verdwijnt met de persoon.",
        "bewijslast": [
            "Documentenoverzicht met eigenaar en status",
            "Bewijs dat documenten vindbaar zijn voor wie ze nodig heeft",
            "Beheer van verouderde versies",
        ],
    },
    "7.5.2": {
        "titel": "Creëren en actualiseren",
        "normtekst": "Bij het creëren en actualiseren van gedocumenteerde informatie moet de organisatie zorgen voor de/het passende: a) identificatie en beschrijving (bijv. een titel, datum, auteur of referentienummer); b) format (bijv. taal, softwareversie, afbeeldingen) en media (bijv. papier, elektronisch); en Dit document is door NEN onder licentie verstrekt aan: / This document has been supplied under license by NEN to: European Certification Bureau B.V. H.J. Bloemers 2018/11/26 NEN-EN-ISO/IEC 27001:2017 15 c) beoordeling en goedkeuring van geschiktheid en adequaatheid.",
        "interpretatie": "Een document zonder versie, datum en eigenaar is niet te beoordelen op actualiteit. Dat is de meest voorkomende bevinding in dit hoofdstuk.",
        "bewijslast": [
            "Versienummer, datum en eigenaar op elk document",
            "Vastgelegde reviewcyclus",
            "Bewijs van uitgevoerde herzieningen",
        ],
    },
    "7.5.3": {
        "titel": "Beheer van gedocumenteerde informatie",
        "normtekst": "Gedocumenteerde informatie zoals het managementsysteem voor informatiebeveiliging en deze Internationale Norm vereisen, moet worden beheerd om te bewerkstelligen dat: a) de informatie beschikbaar is en geschikt is voor gebruik, waar en wanneer het nodig is; b) de informatie adequaat is beveiligd (bijv. tegen verlies van vertrouwelijkheid, oneigenlijk gebruik en aantasting). Voor het beheren van gedocumenteerde informatie moet de organisatie, voor zover van toepassing, invulling geven aan de volgende activiteiten: c) distributie, toegang, het terugvinden alsmede het gebruik; d) opslag en behoud",
        "interpretatie": "Beheersing gaat over toegang en behoud: wie mag lezen, wie mag wijzigen, en blijft het bewaard zolang het nodig is.",
        "bewijslast": [
            "Toegangsrechten op documentniveau",
            "Bewaartermijnen",
            "Bescherming tegen ongewenste wijziging of verlies",
        ],
    },
    "8.1": {
        "titel": "Operationele planning en beheersing",
        "normtekst": "Om te voldoen aan de informatiebeveiligingseisen en om de in 6.1 vastgestelde maatregelen te implementeren moet de organisatie de benodigde processen plannen, implementeren en beheersen. De organisatie moet ook plannen implementeren om de in 6.2 vastgestelde informatiebeveiligingsdoelstellingen te bereiken. De organisatie moet gedocumenteerde informatie bijhouden in de omvang die nodig is om het vertrouwen te hebben dat de processen volgens planning zijn uitgevoerd. De organisatie moet geplande wijzigingen beheersen en de consequenties van onbedoelde wijzigingen beoordelen, en zo nodig maatreg",
        "interpretatie": "Operationele beheersing is het verschil tussen een plan en de praktijk. Uitbestede processen tellen mee: uitbesteden is geen overdragen van verantwoordelijkheid.",
        "bewijslast": [
            "Vastgelegde processen met beheersmaatregelen",
            "Afspraken met leveranciers over uitbestede processen",
            "Bewijs dat de processen worden uitgevoerd zoals vastgelegd",
        ],
    },
    "8.2": {
        "titel": "Risicobeoordeling van informatiebeveiliging",
        "normtekst": "De organisatie moet risicobeoordelingen van informatiebeveiliging met geplande tussenpozen uitvoeren, of als significante veranderingen worden voorgesteld of zich voordoen, rekening houdend met de criteria die zijn vastgesteld in 6.1.2 a). Dit document is door NEN onder licentie verstrekt aan: / This document has been supplied under license by NEN to: European Certification Bureau B.V. H.J. Bloemers 2018/11/26 NEN-EN-ISO/IEC 27001:2017 16 De organisatie moet gedocumenteerde informatie bewaren van de resultaten van de risicobeoordelingen van informatiebeveiliging.",
        "interpretatie": "Een risicobeoordeling die één keer is gedaan, veroudert. De norm vraagt om herhaling op geplande momenten en bij belangrijke wijzigingen.",
        "bewijslast": [
            "Uitgevoerde risicobeoordelingen met datum",
            "Aanleiding per beoordeling",
            "Vergelijking met de vorige ronde",
        ],
    },
    "8.3": {
        "titel": "Informatiebeveiligingsrisico’s behandelen",
        "normtekst": "De organisatie moet het behandelplan van informatiebeveiligingsrisico’s implementeren. De organisatie moet gedocumenteerde informatie bewaren van de resultaten van het behandelen van informatiebeveiligingsrisico’s. 9 Evaluatie van de prestaties",
        "interpretatie": "De behandeling is waar risicomanagement iets verandert. Een behandelplan zonder uitvoering is een lijst voornemens.",
        "bewijslast": [
            "Uitgevoerde maatregelen uit het behandelplan",
            "Status per maatregel met eigenaar",
            "Restrisico expliciet aanvaard",
        ],
    },
    "9.1": {
        "titel": "Monitoren, meten, analyseren en evalueren",
        "normtekst": "De organisatie moet de informatiebeveiligingsprestaties en de doeltreffendheid van het managementsysteem voor informatiebeveiliging evalueren. De organisatie moet vaststellen: a) wat moet worden gemonitord en gemeten, met inbegrip van informatiebeveiligingsprocessen en -beheersmaatregelen; b) welke methoden worden toegepast voor het, voor zover van toepassing, monitoren, meten, analyseren en evalueren, om geldige resultaten te bewerkstelligen;",
        "interpretatie": "Meten maakt zichtbaar of maatregelen werken. Zonder meetpunten is de conclusie 'het gaat goed' niet te onderbouwen.",
        "bewijslast": [
            "Meetplan met wat, hoe, wanneer en door wie",
            "Meetresultaten over meerdere perioden",
            "Analyse en conclusie, niet alleen cijfers",
        ],
    },
    "9.2": {
        "titel": "Interne audit",
        "normtekst": "De organisatie moet met geplande tussenpozen interne audits uitvoeren om informatie te verkrijgen of het managementsysteem voor informatiebeveiliging: a) overeenkomt met: 1) de eigen eisen van de organisatie voor haar managementsysteem voor informatiebeveiliging; en 2) de eisen van deze Internationale norm; b) doeltreffend is geïmplementeerd en onderhouden. Dit document is door NEN onder licentie verstrekt aan: / This document has been supplied under license by NEN to: European Certification Bureau B.V. H.J. Bloemers 2018/11/26 NEN-EN-ISO/IEC 27001:2017 17 De organisatie moet: c) (een) auditpr",
        "interpretatie": "Interne audit is de zelfcontrole van het systeem. Een auditprogramma dat alleen op papier bestaat, levert geen bevindingen en dus geen verbetering.",
        "bewijslast": [
            "Auditprogramma met planning en scope",
            "Auditrapporten met bevindingen",
            "Onafhankelijkheid van de auditor ten opzichte van het geauditeerde",
        ],
    },
    "9.3": {
        "titel": "Directiebeoordeling",
        "normtekst": "De directie moet met geplande tussenpozen het managementsysteem voor informatiebeveiliging van de organisatie beoordelen, om de continue geschiktheid, adequaatheid en doeltreffendheid te bewerkstelligen. Bij de directiebeoordeling moet onder andere in overweging worden genomen: a) de status van acties als gevolg van voorgaande directiebeoordelingen; b) wijzigingen in externe en interne onderwerpen die relevant zijn voor het managementsysteem voor informatiebeveiliging; c) feedback over de informatiebeveiligingsprestaties, met inbegrip van trends in: 1) afwijkingen en corrigerende maatregelen; ",
        "interpretatie": "De directiebeoordeling is het moment waarop de leiding oordeelt of het systeem nog past. Een beoordeling zonder besluiten is een verslag.",
        "bewijslast": [
            "Verslag met de verplichte onderwerpen uit de norm",
            "Genomen besluiten met eigenaar en termijn",
            "Opvolging van besluiten uit de vorige beoordeling",
        ],
    },
    "10.1": {
        "titel": "Continue verbetering",
        "normtekst": "De organisatie moet continu de geschiktheid, adequaatheid en doeltreffendheid van het managementsysteem voor informatiebeveiliging verbeteren. Dit document is door NEN onder licentie verstrekt aan: / This document has been supplied under license by NEN to: European Certification Bureau B.V. H.J. Bloemers 2018/11/26 NEN-EN-ISO/IEC 27001:2017 19 Bijlage A (normatief) Referentiebeheersdoelstellingen en -maatregelen De beheersdoelstellingen en beheersmaatregelen die zijn opgenomen in tabel A.1 zijn rechtstreeks afgeleid van en in overeenstemming met die in ISO/IEC 27002:2013 [1], hoofdstukken 5 t.",
        "interpretatie": "Continue verbetering is de reden dat het systeem geen eindpunt heeft. Zonder aantoonbare verbetering is de conclusie dat alles goed gaat, niet te toetsen.",
        "bewijslast": [
            "Verbeterregister met status",
            "Aantoonbare verbeteringen over meerdere perioden",
            "Herleiding naar bevindingen, metingen of incidenten",
        ],
    },
    "10.2": {
        "titel": "Afwijkingen en corrigerende maatregelen",
        "normtekst": "Wanneer zich een afwijking voordoet, moet de organisatie: a) op de afwijking reageren, en indien van toepassing: 1) maatregelen treffen om de afwijking te beheersen en te corrigeren, en 2) de consequenties aanpakken; b) de noodzaak evalueren om maatregelen te treffen om de oorzaken van de afwijking weg te nemen, zodat de afwijking zich niet herhaalt of zich elders voordoet, door: 1) de afwijking te beoordelen; 2) de oorzaken van de afwijking vast te stellen, en 3) vast te stellen of zich gelijksoortige afwijkingen voordoen of zouden kunnen voordoen; c) de benodigde maatregelen implementeren; d",
        "interpretatie": "Een afwijking vraagt om meer dan herstel: de oorzaak moet weg, anders komt hij terug. Dat onderscheid is waar de meeste corrigerende maatregelen op stranden.",
        "bewijslast": [
            "Registratie van afwijkingen met oorzaakanalyse",
            "Corrigerende maatregelen met eigenaar en termijn",
            "Verificatie dat de maatregel doeltreffend was",
        ],
    },
}
