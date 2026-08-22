"""De Bronbevrager: één vraag, één antwoord, alleen uit het meegegeven corpus.

## Drie regels, en één ervan is gecontroleerd

De systeem-prompt legt drie dingen op: antwoord alleen uit de meegegeven bronnen, verwijs
zonder te citeren, en benoem tegenspraak in plaats van hem op te lossen. Dat zijn
instructies, geen garanties — het model kent ISO 27001 en 9001 uit zijn training en kan een
plausibel antwoord geven zonder één bron aan te raken.

Daarom twee harde maatregelen bovenop de prompt:

1. **Leeg corpus, geen aanroep.** Levert het ophalen niets op, dan gaat er geen vraag naar
   het model. Een antwoord zonder bronnen kan per definitie niet uit de bronnen komen, en
   dat is met een `if` af te dwingen in plaats van met een verzoek.
2. **Verwijzingen worden nagelopen.** Het antwoord verwijst met `[bron:<id>]`, en elk id
   moet in het meegegeven corpus voorkomen. Zo niet, dan is het antwoord een storing en
   geen antwoord — dezelfde regel als bij de classificatie, waar een onleesbaar of afgekapt
   antwoord sinds 2026-08-17 ook geen leeg oordeel meer is.

Dat tweede is het verschil tussen "we hebben het gevraagd" en "we hebben het gecontroleerd".
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from iso_audit import modellen
from iso_audit.assistent.ophalen import Bron, Corpus, haal_bronnen_op
from iso_audit.classification.findings import (
    PRIJZEN_GRONDSLAG,
    PRIJZEN_PEILDATUM,
    Kostenteller,
)
from iso_audit.classification.respons import GEEN_THINKING, OnleesbaarAntwoordError, tekst_uit

logger = logging.getLogger(__name__)

MAX_TOKENS = 2000
"""Ruim, en bewust op de langste variant en niet op de gemiddelde.

Bij een krap budget kapt het antwoord af, en wat er dan als eerste sneuvelt is de
bronvermelding aan het eind — precies het deel dat dit antwoord bruikbaar maakt. Dezelfde
fout stond op 2026-08-17 in de classificatie: een budget dat op één modelstijl was
gekalibreerd, gaf op andere modellen een afgekapt antwoord dat als "niets gevonden" las."""

MAX_SAMENVATTING = 600
"""Tekens per bron in de user-prompt. Genoeg om te wegen, te weinig om te citeren."""

GEEN_DEKKING = (
    "Dit staat niet in de bronnen die ik kan zien: het documentenlandschap, de "
    "bevindingen en audithistorie, de opvolgpunten en de normteksten. Ik geef geen "
    "antwoord uit algemene ISO-kennis — dat is voor een audit niet na te trekken."
)
"""Het antwoord bij een leeg corpus. Vast geformuleerd en niet door het model geschreven:
een model dat mag uitleggen dat het niets weet, legt in de praktijk alsnog uit wat de norm
volgens hem eist."""


def geen_dekking_tekst(corpus: Corpus, norm: str) -> str:
    """De tekst bij een leeg corpus — met de reden erbij als die vast te stellen is.

    Drie gevallen die verschillende dingen betekenen, en "staat er niet in" dekt ze alle
    drie toe: de clausule bestaat niet in deze norm (een typefout), de clausule bestaat maar
    er is niets aan gekoppeld (een dekkingsgat, en dus een auditbevinding in de dop), of de
    vraag had geen clausule en de tekstzoekopdracht leverde niets op.

    Alleen een oorzaak noemen die is vastgesteld — een verzonnen oorzaak stuurt de auditor
    net zo hard het verkeerde bos in als geen melding. Zelfde regel als bij de
    locatiestatus in `sources/drive.py`.
    """
    if not corpus.onbekende_clausules:
        return GEEN_DEKKING
    delen: list[str] = []
    for clausule in corpus.onbekende_clausules:
        suggestie = corpus.suggesties.get(clausule)
        if suggestie:
            delen.append(
                f"Clausule {clausule} bestaat niet in ISO {norm}. Bedoelde je "
                f"{' of '.join(suggestie)}?"
            )
        else:
            delen.append(f"Clausule {clausule} bestaat niet in ISO {norm}.")
    return " ".join(delen) + " " + GEEN_DEKKING


SYSTEEM = """Je bent de Bronbevrager in een ISO-auditwerktuig. Je antwoordt de auditor in \
het Nederlands, kort en zakelijk.

Drie regels, en ze gaan voor op behulpzaamheid:

1. ALLEEN UIT DE MEEGEGEVEN BRONNEN. Je krijgt hieronder een lijst bronnen. Alles wat je \
beweert moet daaruit komen. Staat het antwoord er niet in, dan zeg je dat het er niet in \
staat. Je vult niets aan uit eigen kennis van ISO 27001 of ISO 9001, ook niet als je het \
zeker weet en ook niet gemarkeerd als algemene kennis: een bewering zonder bron van deze \
organisatie is voor een audit waardeloos, terwijl hij op bewijs lijkt.

2. VERWIJZEN, NIET CITEREN. Je parafraseert. Je neemt geen letterlijke tekst over uit een \
document of uit een normtekst. Elke bewering krijgt een verwijzing in de vorm [bron:<id>], \
met het id precies zoals het in de lijst staat. Verwijs nooit naar een id dat niet in de \
lijst staat.

3. TEGENSPRAAK BENOEM JE. Spreken twee bronnen elkaar tegen — een document dat dekking \
claimt terwijl een bevinding een afwijking noemt — dan noem je ze beide met hun bron en \
constateer je dat ze niet overeenkomen. Je kiest niet, en je laat niet de nieuwste of de \
specifiekste winnen. Die spanning is vaak zelf de interessantste uitkomst.

Je velt geen oordeel. Vraagt de auditor of iets een afwijking is, dan toon je het bewijs en \
de eerdere oordelen met hun bron; de auditor beslist. Je stelt geen bevinding en geen \
classificatie voor.

Beantwoorden de meegegeven bronnen de vraag niet, dan zeg je dat en zet je het merkteken \
[niets-gevonden] in je antwoord. Een antwoord zonder enige verwijzing wordt hoe dan ook \
vervangen door een vaste tekst — er valt dan niets na te trekken — dus verwijs waar je kunt.

Je antwoord is een aanwijzing naar bewijs, niet het bewijs zelf."""


class AntwoordOnverifieerbaarError(Exception):
    """Het antwoord verwijst naar iets dat niet in het meegegeven corpus zit.

    Geen antwoord met een waarschuwing eronder: een auditor die een plausibel antwoord ziet
    met een voetnoot leest het antwoord. Dit is een storing.
    """


@dataclass
class Assistentantwoord:
    """Wat één vraag oplevert, inclusief alles wat de trail nodig heeft.

    `meegegeven` is het punt waarop dit later na te trekken is: een antwoord dat achteraf
    verkeerd blijkt, is alleen te begrijpen als je weet wat de assistent op dat moment kon
    zien.
    """

    vraag: str
    antwoord: str
    meegegeven: list[Bron] = field(default_factory=list)
    gebruikt: list[str] = field(default_factory=list)
    model: str = ""
    usd: float = 0.0
    peildatum: str = PRIJZEN_PEILDATUM
    grondslag: str = PRIJZEN_GRONDSLAG
    via_clausule: bool = False
    afgekapt: dict[str, int] = field(default_factory=dict)
    geen_dekking: bool = False
    onverifieerbaar: bool = False
    """Het model antwoordde zonder verwijzing; de auditor ziet `ONVERIFIEERBAAR`."""
    ruw_antwoord: str = ""
    """Wat het model zei toen het antwoord niet na te trekken was.

    Niet getoond, wel vastgelegd: wat het model zei is onderdeel van hoe het oordeel tot stand
    kwam, en een auditor mag dat later kunnen nazien."""

    def als_record(self) -> dict[str, Any]:
        return {
            "vraag": self.vraag,
            "antwoord": self.antwoord,
            "meegegeven": [b.als_record() for b in self.meegegeven],
            "gebruikt": list(self.gebruikt),
            "model": self.model,
            "usd": round(self.usd, 6),
            "peildatum": self.peildatum,
            "grondslag": self.grondslag,
            "via_clausule": self.via_clausule,
            "afgekapt": dict(self.afgekapt),
            "geen_dekking": self.geen_dekking,
            "onverifieerbaar": self.onverifieerbaar,
            "ruw_antwoord": self.ruw_antwoord,
        }


ONVERIFIEERBAAR = (
    "De bronnen die ik bij deze vraag kon vinden, beantwoorden hem niet. Ik toon geen "
    "antwoord dat nergens naar verwijst: dan is er niets na te trekken, en juist zo ziet een "
    "antwoord uit modelkennis eruit."
)
"""Wat de auditor ziet als het antwoord nergens naar verwijst.

**Vervangen en niet weigeren, en zeker niet tonen met een waarschuwing.** Drie vormen zijn
geprobeerd en de eerste twee waren fout:

1. *Weigeren* (2026-08-22, eerste versie): een eerlijk "dit staat er niet in" heeft geen bron om
   naar te verwijzen, en werd daarmee als storing afgewezen. Twee van drie echte vragen faalden.
2. *Een merkteken dat het model moet zetten*: werkt zolang het model zich eraan houdt, en dat
   deed het niet. Een instructie is geen garantie — dezelfde les als bij de verwijzingen zelf.
3. *Vervangen*: is het antwoord niet na te trekken, dan komt de tekst van het model er niet in.
   Deterministisch, en het dekt beide gevallen tegelijk: een eerlijk "niet gevonden" én een
   antwoord uit modelkennis leveren allebei deze tekst op.

De tekst van het model gaat wél naar de trail (`ruw_antwoord`), want wat het zei is onderdeel van
hoe het oordeel tot stand kwam."""

NIETS_GEVONDEN = "[niets-gevonden]"
"""Merkteken dat het model zet als de meegegeven bronnen de vraag niet beantwoorden.

Bestaat omdat de verwijzingscontrole anders een eerlijk antwoord weigert. Gemeten op
2026-08-22 tegen het echte corpus: van drie vragen gaf één een antwoord met 25 bronnen, en
kwamen twee terug als storing met "antwoord bevat geen enkele bronverwijzing". Dat was niet
het model dat iets verzon — het zei correct dat het gevraagde niet in díe bronnen stond, en
had daarmee niets om naar te verwijzen.

Een merkteken en geen tekstherkenning: zoeken op zinsneden als "staat niet in" is een
tweede, onbetrouwbare administratie van hoe het model zich uitdrukt. Eén afgesproken token
is deterministisch, en de controle blijft daarmee een controle in plaats van een gok."""

_BRONMARKERING = re.compile(r"\[bron:([^\]]+)\]")
_VOORVOEGSEL = re.compile(r"^bron:\s*", re.IGNORECASE)
_SCHEIDING = re.compile(r"\s*(?:,|;|\ben\b|&)\s*")
"""Waarop een groep bron-ID's uiteenvalt.

`\ben\b` met woordgrenzen: een ID dat toevallig "en" bevat (`1eDQv1pQ8r2Sv...`) mag niet
uiteenvallen. Nagemeten tegen het echte corpus — die ID's bestaan echt."""
_CLAUSULE_IN_ANTWOORD = re.compile(r"\b(\d{1,2}(?:\.\d{1,2}){1,3})\b")


def _bronnenblok(corpus: Corpus) -> str:
    regels: list[str] = []
    for b in corpus.bronnen:
        kop = f"- id: {b.id} | soort: {b.soort} | naam: {b.naam}"
        if b.clausules:
            kop += f" | clausules: {', '.join(b.clausules)}"
        regels.append(kop)
        if b.samenvatting:
            regels.append(f"  inhoud: {b.samenvatting[:MAX_SAMENVATTING]}")
    return "\n".join(regels)


def _user_prompt(vraag: str, corpus: Corpus) -> str:
    delen = [f"Vraag van de auditor:\n{vraag}", "", "Bronnen die je mag gebruiken:", ""]
    delen.append(_bronnenblok(corpus))
    if corpus.afgekapt:
        # Expliciet in de prompt, zodat het model niet "dit zijn alle documenten" beweert.
        meer = ", ".join(f"{n} extra {soort}(en)" for soort, n in sorted(corpus.afgekapt.items()))
        delen += ["", f"Let op: er zijn meer treffers dan hier staan ({meer}). Noem dat."]
    return "\n".join(delen)


def _bron_ids(antwoord: str) -> list[str]:
    """Alle bron-ID's uit de merktekens, in volgorde van voorkomen, zonder duplicaten.

    Eén merkteken kan **meerdere** ID's bevatten: het model schrijft in de praktijk
    `[bron:id1, id2, id3]` wanneer een bewering op meerdere documenten rust. Gemeten op
    2026-08-22 tegen het echte corpus: twaalf geldige ID's plus een normtekst werden als één
    onbekend ID gelezen, en het antwoord werd geweigerd als verzonnen terwijl elk ID bestond.

    Splitsen op komma, puntkomma én het woord "en" — dat laatste omdat het model in het
    Nederlands antwoordt en `[bron:a en b]` schrijft. Ook dat kwam pas boven water tegen het
    echte model (2026-08-22, tweede keer).

    Tolerant voor de vorm, niet voor de inhoud: élk los ID moet daarna nog steeds in het
    meegegeven corpus zitten. Een strengere prompt ("één bron per merkteken") zou hetzelfde
    willen bereiken door het model iets te vragen in plaats van door het te controleren — dat
    is precies de omgekeerde volgorde.
    """
    uniek: list[str] = []
    for groep in _BRONMARKERING.findall(antwoord):
        for ruw in _SCHEIDING.split(str(groep)):
            # Het voorvoegsel eraf: het model herhaalt het binnen één merkteken
            # (`[bron:a, bron:b]`). Derde vormvariant die pas tegen het echte model boven
            # water kwam, na de komma-lijst en het woord "en".
            bron_id = _VOORVOEGSEL.sub("", ruw.strip()).strip()
            if bron_id and bron_id not in uniek:
                uniek.append(bron_id)
    return uniek


def verifieer_verwijzingen(antwoord: str, corpus: Corpus) -> list[str]:
    """Controleer dat het antwoord alleen naar meegegeven bronnen verwijst.

    Retourneert de gebruikte bron-ID's. Raist `AntwoordOnverifieerbaarError` bij een
    verwijzing naar een bron die niet is meegegeven, of naar een clausule die in geen enkele
    meegegeven bron voorkomt.

    Een lege lijst is een geldige uitkomst: het antwoord verwijst nergens naar. Wat er dán
    gebeurt beslist `beantwoord()` — niet door de prose van het model te vertrouwen, maar door
    hem te vervangen. Zie `ONVERIFIEERBAAR`.
    """
    gebruikt = _bron_ids(antwoord)
    onbekend = sorted({g for g in gebruikt if g not in corpus.ids})
    if onbekend:
        raise AntwoordOnverifieerbaarError(
            f"antwoord verwijst naar bronnen die niet zijn meegegeven: {', '.join(onbekend)}"
        )

    toegestaan = corpus.genoemde_clausules | set(corpus.clausules_in_vraag)
    verzonnen = sorted({c for c in _CLAUSULE_IN_ANTWOORD.findall(antwoord) if c not in toegestaan})
    if verzonnen:
        raise AntwoordOnverifieerbaarError(
            f"antwoord noemt clausules die niet in de bronnen staan: {', '.join(verzonnen)}"
        )
    # `_bron_ids` levert al de volgorde van eerste voorkomen zonder duplicaten — dat is hoe
    # het in de trail leest.
    return gebruikt


def beantwoord(
    conn: sqlite3.Connection,
    vraag: str,
    *,
    norm: str = "27001",
    model: str | None = None,
    client: Any | None = None,
) -> Assistentantwoord:
    """Beantwoord één vraag uit het corpus. Schrijft niets — de caller legt vast.

    :raises AntwoordOnverifieerbaarError: het antwoord verwijst naar iets dat niet is
        meegegeven, of naar niets.
    :raises OnleesbaarAntwoordError: de respons had geen tekstblok.
    """
    gekozen = model or modellen.uit_omgeving()
    corpus = haal_bronnen_op(conn, vraag, norm=norm)

    if corpus.is_leeg():
        # Geen aanroep: een antwoord zonder bronnen kan niet uit de bronnen komen. Dat is
        # met een `if` af te dwingen en niet met een verzoek aan het model.
        logger.info(
            "Assistent: geen dekking in het corpus voor deze vraag (onbekende clausules: %s)",
            ", ".join(corpus.onbekende_clausules) or "geen",
        )
        return Assistentantwoord(
            vraag=vraag,
            antwoord=geen_dekking_tekst(corpus, norm),
            model=gekozen,
            via_clausule=corpus.via_clausule,
            geen_dekking=True,
        )

    import anthropic

    teller = Kostenteller(model=gekozen)
    begin = time.monotonic()
    resp = (client or anthropic.Anthropic()).messages.create(
        model=gekozen,
        max_tokens=MAX_TOKENS,
        # Expliciet uit, om de reden die in `classification/respons.py` staat: de parameter
        # weglaten maakt het gedrag afhankelijk van het gekozen model.
        thinking=GEEN_THINKING,
        system=SYSTEEM,
        messages=[{"role": "user", "content": _user_prompt(vraag, corpus)}],
    )
    teller.voeg_toe(getattr(resp, "usage", None), time.monotonic() - begin)

    if getattr(resp, "stop_reason", None) == "max_tokens":
        # Zelfde regel als bij de classificatie: afgekapt is een storing. Hier verdwijnt bij
        # afkapping juist de bronvermelding, en dan blijft er een bewering zonder spoor over.
        raise AntwoordOnverifieerbaarError(
            "antwoord afgekapt op max_tokens; de bronvermelding valt dan weg"
        )

    tekst = tekst_uit(resp)
    gebruikt = verifieer_verwijzingen(tekst, corpus)
    if not gebruikt:
        # Niet na te trekken: de tekst van het model bereikt de auditor niet. Zie
        # `ONVERIFIEERBAAR` voor waarom vervangen en niet weigeren of waarschuwen.
        logger.info("Assistent: antwoord zonder verwijzing vervangen door de vaste tekst")
        return Assistentantwoord(
            vraag=vraag,
            antwoord=ONVERIFIEERBAAR,
            ruw_antwoord=tekst,
            meegegeven=list(corpus.bronnen),
            model=gekozen,
            usd=teller.kosten_usd(),
            via_clausule=corpus.via_clausule,
            afgekapt=dict(corpus.afgekapt),
            onverifieerbaar=True,
        )
    return Assistentantwoord(
        vraag=vraag,
        antwoord=tekst,
        meegegeven=list(corpus.bronnen),
        gebruikt=gebruikt,
        model=gekozen,
        usd=teller.kosten_usd(),
        via_clausule=corpus.via_clausule,
        afgekapt=dict(corpus.afgekapt),
    )


__all__ = [
    "AntwoordOnverifieerbaarError",
    "Assistentantwoord",
    "OnleesbaarAntwoordError",
    "beantwoord",
    "verifieer_verwijzingen",
]
