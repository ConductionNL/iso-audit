"""Auto-triage: review-adviezen omzetten in triage-voorstellen, met een spoor.

Dit is de grens waar dit tool het meest voorzichtig moet zijn. De auditor-spiegel is de
capability die het draagt: op vaste punten houdt een mens het oordeel. Tegelijk is wat er op
2026-08-24 gebeurde — 902 bevindingen in vier bulkacties op `valide` — geen menselijk oordeel
maar capitulatie voor het aantal. Een lijst die te lang is om te wegen, wordt niet gewogen.

De uitweg is niet "de agent beslist" maar **de agent doet het onbetwiste voorwerk, expliciet
gemarkeerd**:

- **Alleen `bevestigen` op een positieve bevinding.** Dan betwist niemand iets: de review
  bevestigt wat de classificatie al zei, en er valt geen oordeel te vellen.
- **Nooit een NC.** Correctie, root-cause-analyse en formele verificatie zijn gevolgen die de
  certificering raken. Die beslissing is van de auditor, ook als de review de NC bevestigt.
- **Nooit een verlaging.** Verlagen is juist wél een oordeel: de review vindt het bewijs
  onvoldoende voor de zwaarste klasse.

Wat overblijft is de bulk die niemand wil wegen en waar niets op het spel staat. Dat is wat
autonoom draaien hier kan betekenen — en niet meer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from iso_audit.classification.review import Advies, Clausulegroep

logger = logging.getLogger(__name__)

AUTO_ACTOR = "auto-triage"
"""De actor in de trail. Bewust geen mens-achtige naam: een auditor moet in één blik kunnen zien
wat een mens heeft besloten en wat niet."""

AUTOMATISCH_TE_AFFRONTEREN = "positief"
"""De enige classificatie die automatisch mag worden afgedaan."""


@dataclass(frozen=True)
class Voorstel:
    """Eén automatische triage, klaar om vastgelegd te worden."""

    finding_id: str
    status: str
    reden: str
    actor: str = AUTO_ACTOR


def voorstellen(
    uitkomsten: list[tuple[Clausulegroep, Advies | None, str | None]],
) -> list[Voorstel]:
    """Zet review-uitkomsten om in triage-voorstellen voor het onbetwiste deel.

    Een storing levert niets op: geen advies is geen groen licht.
    """
    voorstellen_lijst: list[Voorstel] = []
    for groep, advies, storing in uitkomsten:
        if storing or advies is None:
            continue
        if advies.advies != "bevestigen":
            continue
        if advies.voorgestelde_klasse != AUTOMATISCH_TE_AFFRONTEREN:
            continue
        for bev in groep.bevindingen:
            if bev.get("classificatie") != AUTOMATISCH_TE_AFFRONTEREN:
                continue
            finding_id = str(bev.get("id") or "")
            if not finding_id:
                continue
            voorstellen_lijst.append(
                Voorstel(
                    finding_id=finding_id,
                    status="valide",
                    reden=(
                        f"auto-triage: de review bevestigde deze positieve bevinding op "
                        f"{groep.norm} §{groep.clausule}. {advies.reden}"
                    ),
                )
            )
    if voorstellen_lijst:
        logger.info(
            "Auto-triage: %d positieve bevinding(en) automatisch op valide; "
            "NC's en verlagingen blijven bij de auditor",
            len(voorstellen_lijst),
        )
    return voorstellen_lijst


def pas_toe(sessie: Any, voorstellen_lijst: list[Voorstel]) -> int:
    """Leg de voorstellen vast via de gewone triage-weg, dus mét trail.

    Bewust `apply_triage` en geen directe schrijfactie op de werkset: dan gelden dezelfde
    controles, hetzelfde slot en dezelfde append-only regel als bij een mens. Een automatische
    beslissing die buiten het spoor omgaat, is geen beslissing die je kunt verantwoorden.
    """
    gedaan = 0
    for voorstel in voorstellen_lijst:
        try:
            sessie.apply_triage(
                voorstel.finding_id,
                triage_status=voorstel.status,
                reason=voorstel.reden,
                actor=voorstel.actor,
            )
            gedaan += 1
        except Exception as fout:
            logger.warning("Auto-triage op %s mislukt: %s", voorstel.finding_id, fout)
    return gedaan
