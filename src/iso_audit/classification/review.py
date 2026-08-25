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

import logging
import os
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
