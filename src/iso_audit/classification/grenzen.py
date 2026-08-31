"""Een profielregel kan een oordeel verlagen, nooit ophogen.

Na de volledige run van 2026-08-31 wees de auditor twee NC's aan die het niet zijn: A.8.14
(redundantie) omdat de organisatie data bij de bron ophaalt in plaats van zelf te bewaren, en
A.8.9 (configuratiebeheer) omdat de versies in Git staan. Beide keren ís er een maatregel, alleen
niet gedocumenteerd of gecentraliseerd — een verbeterkans, geen non-conformiteit.

Zonder vastlegging velt het model elke run opnieuw hetzelfde verkeerde oordeel, en sleept de
auditor elke run dezelfde twee bevindingen met de hand naar OFI.

**Alleen verlagen.** Ophogen naar NC is een auditoordeel dat een mens hoort te vellen, in de
triage, met zijn naam in de trail — dezelfde regel als `MACHINE_ACTOREN` in `api/session.py`.

**Nooit stil.** Elke verlaging draagt de motivering uit het profiel mee, zodat in de bevinding
zelf te lezen is dát er een profielregel gold en waarom. Een verlaging die je niet ziet, is
precies wat een externe auditor niet accepteert.
"""

from __future__ import annotations

from typing import Any

RANGORDE = {"POSITIVE": 0, "OFI": 1, "NC": 2}
"""Zwaarte van een classificatie. `UNCLASSIFIED` staat er niet in: die is geen oordeel."""


def pas_grens_toe(klasse: str, regel: Any) -> str:
    """Verlaag `klasse` tot de grens uit de profielregel, of laat hem staan.

    Een plafond en geen vloer: een positieve bevinding wordt niet opgehoogd naar OFI.
    """
    grens = _grens(regel)
    if not grens:
        return klasse
    if RANGORDE.get(klasse, 0) <= RANGORDE.get(grens, 0):
        return klasse
    return grens


def verlagingsnotitie(van: str, naar: str, regel: Any) -> str:
    """De zin die bij een verlaagde bevinding komt te staan."""
    motivering = _veld(regel, "motivering")
    return f"Beoordeeld als {van}, verlaagd naar {naar} op grond van een profielregel: {motivering}"


def _grens(regel: Any) -> str:
    return _veld(regel, "hoogste_klasse")


def _veld(regel: Any, naam: str) -> str:
    """Leest zowel een dict (uit YAML) als een pydantic-model."""
    if regel is None:
        return ""
    if isinstance(regel, dict):
        return str(regel.get(naam) or "")
    return str(getattr(regel, naam, "") or "")
