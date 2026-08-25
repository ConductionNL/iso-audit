"""Autonome review: een tweede zeef over de bevindingen van de classificatie.

De classificatie oordeelt per document en draait op een goedkoop model over honderden
documenten. Dat is een verdedigbare eerste zeef, maar er zit geen tweede achter, en de auditor
is de enige die het verschil moet maken tussen "dit document noemt encryptie niet" en "hier
ontbreekt aantoonbaar een beheersmaatregel".

Gemeten op 2026-08-24, na invoering van de formele NC-definitie: 347 bevindingen over 67
clausules, waarvan 79 NC's. Beter dan de 800 en 387 daarvoor, maar nog steeds een lijst waar
niemand één voor één doorheen gaat — en dat is precies wat er gebeurde: 902 bevindingen in vier
bulkacties op `valide`.

**Aan of uit.** De review draait over honderden bevindingen op een zwaarder model en is de
duurste stap van de pipeline. Hij staat uit tenzij iemand hem aanzet: geen impliciete defaults,
en zeker niet voor iets dat geld kost en een oordeel voorbereidt.

**Hij adviseert, hij beslist niet.** Zelfde grens als bij de clausule-agent, waar
`VERBODEN_VELDEN` dat met een test afdwingt. De auditor-spiegel is de capability die dit tool
draagt; een agent die een status zet maakt van beoordelen bevestigen.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

ENV_VAR = "ISO_AUDIT_REVIEW"
"""Env-var-fallback voor cron-runs, zoals `ISO_AUDIT_DEFAULT_SOURCE` en `_MODE`."""

_AAN = frozenset({"1", "true", "ja", "aan", "on", "yes", "y"})
"""Wat als "aan" telt. Alles wat hier niet in staat is uit — inclusief lege waarden en
typefouten. Bij een schakelaar die geld kost is stil aanstaan erger dan stil uitstaan."""


@dataclass(frozen=True)
class ReviewInstelling:
    """Of de review draait, en waar die keuze vandaan komt.

    De herkomst hoort in de trail: "waarom draaide deze stap wel of niet" moet achteraf te
    beantwoorden zijn zonder de startopdracht terug te zoeken — dezelfde reden dat de
    bron-configuratie per veld zijn herkomst meegeeft.
    """

    aan: bool
    herkomst: str  # "vlag" | "omgeving" | "standaard"

    @classmethod
    def bepaal(cls, vlag: bool | None) -> ReviewInstelling:
        """Bepaal de instelling: expliciete vlag > env-var > uit.

        De vlag wint van de omgeving. Andersom zou een cron-instelling een handmatige run stil
        overrulen, en dan weet degene die de run start niet wat er draait.
        """
        if vlag is not None:
            return cls(aan=vlag, herkomst="vlag")
        ruw = os.environ.get(ENV_VAR)
        if ruw is None:
            return cls(aan=False, herkomst="standaard")
        aan = ruw.strip().lower() in _AAN
        logger.info(
            "Autonome review %s via %s=%r (env-var-fallback)",
            "aan" if aan else "uit",
            ENV_VAR,
            ruw,
        )
        return cls(aan=aan, herkomst="omgeving")

    def mag_model_aanroepen(self) -> bool:
        """De schakelaar zit vóór de aanroep, niet erna.

        Een review die draait en zijn uitkomst weggooit kost hetzelfde als een review die telt.
        """
        return self.aan


def review_aan(vlag: bool | None) -> bool:
    """Korte vorm voor aanroepers die alleen ja/nee nodig hebben."""
    return ReviewInstelling.bepaal(vlag).aan


GEWICHT = {"NC": 0, "OFI": 1, "positief": 2}
"""Volgorde waarin de review de dure aanroepen doet: een clausule met een NC eerst.

Niet om te beslissen — dat blijft de auditor — maar zodat een afgebroken of afgekapte run de
belangrijkste clausules al heeft gehad."""


@dataclass
class Clausulegroep:
    """Alle bruikbare bevindingen op één (norm, clausule), samen als één vraag.

    De classificatie oordeelt per document: 42 documenten die clausule 8.16 raken geven 42
    oordelen over dezelfde eis. Een auditor stelt één vraag — wordt deze eis gehaald, gegeven al
    het bewijs? — en dat is een vraag die je maar één keer stelt.

    Norm en clausule samen, nooit clausule alleen: §7.5 is in 9001 "Gedocumenteerde informatie"
    en in 27001 "Bescherming tegen fysieke en omgevingsbedreigingen". Op één hoop zou bewijs
    over het ene iets zeggen over het andere.
    """

    clausule: str
    norm: str
    bevindingen: list[dict[str, Any]] = field(default_factory=list)

    @property
    def documenten(self) -> int:
        return len({b.get("doc_id") for b in self.bevindingen})

    @property
    def zwaarste(self) -> str:
        """De zwaarste classificatie in de groep — bepaalt de volgorde, niet het oordeel."""
        return min(
            (str(b.get("classificatie")) for b in self.bevindingen),
            key=lambda c: GEWICHT.get(c, 9),
            default="positief",
        )


def groepeer_per_clausule(bevindingen: list[dict[str, Any]]) -> list[Clausulegroep]:
    """Bundel bevindingen per (norm, clausule), zwaarste eerst.

    Onbruikbare bevindingen — een oordeel zonder beschrijving én zonder onderbouwing — tellen
    niet mee: die dragen niets bij aan de vraag of de eis gehaald wordt. Blijft er niets over,
    dan komt de clausule niet terug; er valt dan niets te reviewen.
    """
    per_sleutel: dict[tuple[str, str], Clausulegroep] = defaultdict(
        lambda: Clausulegroep(clausule="", norm="")
    )
    for bev in bevindingen:
        if bev.get("onbruikbaar"):
            continue
        clausule = str(bev.get("clausule_id") or bev.get("clausule") or "")
        norm = str(bev.get("norm") or "")
        groep = per_sleutel[(clausule, norm)]
        groep.clausule, groep.norm = clausule, norm
        groep.bevindingen.append(bev)

    groepen = [g for g in per_sleutel.values() if g.bevindingen]
    return sorted(groepen, key=lambda g: (GEWICHT.get(g.zwaarste, 9), g.norm, g.clausule))


ADVIEZEN = frozenset({"bevestigen", "verlagen", "samenvoegen", "onvoldoende_bewijs"})
KLASSEN = frozenset({"NC", "OFI", "positief"})

_CODEBLOK = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class ReviewFoutError(Exception):
    """Het antwoord van de review is onbruikbaar.

    Bewust een storing en geen stil genegeerd advies: dat de review iets onbruikbaars teruggaf,
    is zelf een gegeven over de review — en zonder die melding lijkt "geen advies" hetzelfde als
    "niets aan de hand".
    """


@dataclass(frozen=True)
class Advies:
    """Wat de review over één clausule vindt. Een voorstel, geen besluit."""

    advies: str
    voorgestelde_klasse: str | None
    ernst: str | None
    kern: str
    reden: str
    zonder_inhoud: int


def _json_uit(tekst: str) -> dict[str, Any]:
    """Lees JSON, ook als er een codeblok omheen staat.

    Tolerant voor de vorm, streng op de inhoud — dezelfde regel als bij de Bronbevrager, waar
    dat drie iteraties kostte omdat het model zijn verwijzingen anders opschreef dan verwacht.
    """
    kandidaat = tekst.strip()
    blok = _CODEBLOK.search(kandidaat)
    if blok:
        kandidaat = blok.group(1).strip()
    try:
        gegevens = json.loads(kandidaat)
    except json.JSONDecodeError as fout:
        raise ReviewFoutError(f"antwoord is geen geldige JSON: {fout}") from fout
    if not isinstance(gegevens, dict):
        raise ReviewFoutError(f"antwoord is geen object maar {type(gegevens).__name__}")
    return gegevens


def lees_advies(ruw: str, groep: Clausulegroep) -> Advies:
    """Controleer en lees het antwoord van de review.

    Drie controles, elk met een reden uit de praktijk van 2026-08-24:

    - **Het advies moet een van de vier zijn.** Een vijfde waarde levert een regel op die geen
      enkel scherm kent; de classificatie gaf die dag twee keer de string `'null'` terug.
    - **De reden moet naar een meegegeven document verwijzen.** Zonder verwijzing is het advies
      niet na te trekken, en een verzonnen documentnaam is erger dan geen.
    - **De kernzin mag niet leeg zijn.** Die gaat naar de managementmemo; leeg betekent dat de
      memo niets te melden heeft over een clausule die wél aandacht kreeg.
    """
    gegevens = _json_uit(ruw)

    advies = str(gegevens.get("advies") or "").strip().lower()
    if advies not in ADVIEZEN:
        raise ReviewFoutError(f"onbekend advies {advies!r}; verwacht een van {sorted(ADVIEZEN)}")

    klasse = gegevens.get("voorgestelde_klasse")
    if klasse is not None and str(klasse) not in KLASSEN:
        raise ReviewFoutError(f"onbekende klasse {klasse!r}; verwacht een van {sorted(KLASSEN)}")

    kern = str(gegevens.get("kern") or "").strip()
    if not kern:
        raise ReviewFoutError("kern ontbreekt; die zin gaat naar de memo")

    reden = str(gegevens.get("reden") or "").strip()
    namen = {str(b.get("document_naam") or "") for b in groep.bevindingen}
    if not any(naam and naam in reden for naam in namen):
        raise ReviewFoutError(
            "de reden verwijst niet naar een meegegeven document; zonder verwijzing is het "
            "advies niet na te trekken"
        )

    return Advies(
        advies=advies,
        voorgestelde_klasse=str(klasse) if klasse is not None else None,
        ernst=str(gegevens["ernst"]) if gegevens.get("ernst") else None,
        kern=kern,
        reden=reden,
        zonder_inhoud=int(gegevens.get("zonder_inhoud") or 0),
    )


MAX_BEVINDINGEN_PER_GROEP = 25
"""Hoeveel bevindingen er per clausule aan het model meegaan.

Clausule 10.2 had er 27 op 2026-08-24, en dat is de uitschieter. Afkappen is beter dan een
prompt die met de dataset meegroeit, maar het moet **gemeld** worden: een lijst die stil op 25
stopt leest als "dit is alles" — dezelfde regel als bij de Bronbevrager, die zijn afkapping in
het antwoord én in de trail zet."""


def bouw_reviewvraag(groep: Clausulegroep, normtekst: str = "") -> tuple[str, int]:
    """De gebruikersprompt voor één clausule. Geeft ook terug hoeveel er is afgekapt."""
    meegegeven = groep.bevindingen[:MAX_BEVINDINGEN_PER_GROEP]
    afgekapt = len(groep.bevindingen) - len(meegegeven)
    regels = [
        f"Clausule: {groep.norm} §{groep.clausule}",
        f"Bevindingen: {len(groep.bevindingen)} over {groep.documenten} document(en).",
    ]
    if normtekst:
        regels.append(f"Normtekst: {normtekst}")
    if afgekapt:
        regels.append(
            f"LET OP: {afgekapt} bevinding(en) zijn niet meegestuurd wegens de bovengrens van "
            f"{MAX_BEVINDINGEN_PER_GROEP}. Je oordeel gaat over wat je hier ziet."
        )
    regels.append("")
    for bev in meegegeven:
        regels.append(
            f"- [{bev.get('classificatie')}] {bev.get('document_naam')}: "
            f"{(bev.get('beschrijving') or '(geen beschrijving)')} "
            f"| onderbouwing: {(bev.get('onderbouwing') or '(geen)')}"
        )
    return "\n".join(regels), afgekapt


def _systeemprompt() -> str:
    from importlib.resources import files

    return (files("iso_audit.classification.prompts") / "v2-review.md").read_text(encoding="utf-8")


def beoordeel(
    groepen: list[Clausulegroep],
    *,
    instelling: ReviewInstelling,
    model: str,
    steekproef: int = 0,
    client: Any | None = None,
    conn: Any | None = None,
    door: str = "",
    normtekst_voor: Any | None = None,
) -> list[tuple[Clausulegroep, Advies | None, str | None]]:
    """Beoordeel clausulegroepen; geeft per groep `(groep, advies, storing)`.

    Draait alleen als de instelling aan staat — de schakelaar zit vóór de aanroep, niet erna.

    `steekproef` kapt af op de eerste N groepen. Die staan op zwaarte gesorteerd, dus een
    steekproef bekijkt de clausules met een NC eerst. Bedoeld om te meten wat de review eruit
    haalt vóórdat er zeventig groepen op een zwaar model doorheen gaan: 67 groepen op Opus is
    een uitgave die je één keer met de juiste prompt wil doen, niet een experiment dat tegelijk
    de rekening is.

    Een storing op één groep stopt de rest niet, maar wordt wel vastgelegd. Dat een groep geen
    advies opleverde is zelf een gegeven; zonder die melding lijkt het op "niets aan de hand".
    """
    if not instelling.mag_model_aanroepen():
        logger.info("Autonome review staat uit (%s); geen enkele aanroep", instelling.herkomst)
        return []

    import anthropic

    from iso_audit.classification.findings import _vraag_model, prijs_voor
    from iso_audit.classification.respons import GEEN_THINKING, tekst_uit

    te_doen = groepen[:steekproef] if steekproef else groepen
    if steekproef and len(groepen) > steekproef:
        logger.info(
            "Steekproef: %d van %d clausulegroepen (zwaarste eerst); %d niet beoordeeld",
            len(te_doen),
            len(groepen),
            len(groepen) - len(te_doen),
        )

    systeem = _systeemprompt()
    aanroeper = client or anthropic.Anthropic()
    tarief = prijs_voor(model)
    uitkomsten: list[tuple[Clausulegroep, Advies | None, str | None]] = []

    for groep in te_doen:
        normtekst = normtekst_voor(groep) if normtekst_voor else ""
        vraag, afgekapt = bouw_reviewvraag(groep, normtekst)
        storing: str | None = None
        advies: Advies | None = None
        usd = 0.0
        ruw = ""
        try:
            resp = _vraag_model(
                aanroeper,
                model=model,
                max_tokens=1200,
                system=systeem,
                messages=[{"role": "user", "content": vraag}],
                thinking=GEEN_THINKING,
            )
            ruw = tekst_uit(resp)
            if tarief:
                gebruik = getattr(resp, "usage", None)
                invoer = getattr(gebruik, "input_tokens", 0) or 0
                uitvoer = getattr(gebruik, "output_tokens", 0) or 0
                usd = invoer / 1e6 * tarief["input"] + uitvoer / 1e6 * tarief["output"]
            advies = lees_advies(ruw, groep)
        except ReviewFoutError as fout:
            storing = f"ReviewFoutError: {fout}"
        except Exception as fout:
            storing = f"{type(fout).__name__}: {fout}"

        if storing:
            logger.warning("Review %s §%s: %s", groep.norm, groep.clausule, storing)
        if conn is not None:
            _leg_vast(conn, groep, vraag, ruw, advies, storing, model, usd, afgekapt, door)
        uitkomsten.append((groep, advies, storing))

    return uitkomsten


def _leg_vast(
    conn: Any,
    groep: Clausulegroep,
    vraag: str,
    ruw: str,
    advies: Advies | None,
    storing: str | None,
    model: str,
    usd: float,
    afgekapt: int,
    door: str,
) -> None:
    """Elke aanroep in de append-only trail, storingen inbegrepen.

    Zonder de storingen is niet vast te stellen wat de review zag toen zij iets beweerde — en op
    2026-08-24 bleek dat een 500 op de assistent-route maandenlang geen spoor naliet.
    """
    from iso_audit.classification.findings import PRIJZEN_GRONDSLAG, PRIJZEN_PEILDATUM
    from iso_audit.store import bewaar_assistentvraag

    bewaar_assistentvraag(
        conn,
        agent="review",
        record={
            "vraag": vraag,
            "antwoord": ruw,
            "meegegeven": [
                {"id": str(b.get("doc_id")), "naam": str(b.get("document_naam"))}
                for b in groep.bevindingen
            ],
            "gebruikt": [advies.advies] if advies else [],
            "model": model,
            "usd": round(usd, 6),
            "peildatum": PRIJZEN_PEILDATUM,
            "grondslag": PRIJZEN_GRONDSLAG,
            "clausule": f"{groep.norm} §{groep.clausule}",
            "afgekapt": afgekapt,
        },
        storing=storing,
        gesteld_door=door,
    )
