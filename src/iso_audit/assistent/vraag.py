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
        }


_BRONMARKERING = re.compile(r"\[bron:([^\]]+)\]")
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


def verifieer_verwijzingen(antwoord: str, corpus: Corpus) -> list[str]:
    """Controleer dat het antwoord alleen naar meegegeven bronnen verwijst.

    Retourneert de gebruikte bron-ID's. Raist `AntwoordOnverifieerbaarError` bij een
    verwijzing naar een bron die niet is meegegeven, of naar een clausule die in geen enkele
    meegegeven bron voorkomt.

    Een antwoord zónder verwijzing is ook een storing: dan is er niets na te trekken, en
    juist dat is waar een antwoord uit modelkennis op lijkt.
    """
    gebruikt = _BRONMARKERING.findall(antwoord)
    onbekend = sorted({g for g in gebruikt if g not in corpus.ids})
    if onbekend:
        raise AntwoordOnverifieerbaarError(
            f"antwoord verwijst naar bronnen die niet zijn meegegeven: {', '.join(onbekend)}"
        )
    if not gebruikt:
        raise AntwoordOnverifieerbaarError(
            "antwoord bevat geen enkele bronverwijzing; niets om na te trekken"
        )
    toegestaan = corpus.genoemde_clausules | set(corpus.clausules_in_vraag)
    verzonnen = sorted({c for c in _CLAUSULE_IN_ANTWOORD.findall(antwoord) if c not in toegestaan})
    if verzonnen:
        raise AntwoordOnverifieerbaarError(
            f"antwoord noemt clausules die niet in de bronnen staan: {', '.join(verzonnen)}"
        )
    # Volgorde van eerste voorkomen, zonder duplicaten — dat is hoe het in de trail leest.
    uniek: list[str] = []
    for g in gebruikt:
        if g not in uniek:
            uniek.append(g)
    return uniek


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
        logger.info("Assistent: geen dekking in het corpus voor deze vraag")
        return Assistentantwoord(
            vraag=vraag,
            antwoord=GEEN_DEKKING,
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
