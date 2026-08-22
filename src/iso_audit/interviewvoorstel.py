"""Voorstellen welk interview een ongedekte clausule kan opvullen — deterministisch.

## De vraag is omgedraaid

Het oorspronkelijke idee was: markeer per bewijslast-item of een mens het kan bevestigen, en
stel daar interviews voor. Gemeten op 2026-08-22: van de **481 bewijslast-items** in
`data/normteksten` beschrijven er ongeveer **drie** een waarneming. De catalogus is vrijwel
volledig artefact-gericht — "notulen directiebeoordeling", "toegangsrechtenmatrix",
"versiehistorie".

Die verrijken is inhoudelijk ISO-werk: vaststellen wát als bewijs telt, is een auditoroordeel.
481 items markeren zou betekenen dat dit tool zijn eigen bewijsstandaard verzint.

Dus andersom: **"we vinden dit artefact niet — bestaat het, en waar?"** Dat is wat een auditor in
een interview vraagt, het volgt volledig uit de bestaande catalogus, en het antwoord is een
aanwijzing naar bewijs in plaats van een vervanging ervan.

## Geen model

De vragen worden samengesteld uit de bewijslast-tekst, met een vaste formulering. Geen LLM: een
agent die vrije interviewvragen bedenkt, verzint eisen die niet in de norm staan, en dan staat er
in een auditdossier een vraag die niemand kan herleiden.

Consequentie die eerlijk is: de vragen klinken formulierachtig. Dat is de prijs van
herleidbaarheid, en een auditor formuleert in het gesprek zelf toch anders.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

from iso_audit.data import normteksten

ROL_ONBEKEND = "nog te bepalen"
"""Wat er staat waar het tool de rol niet weet.

Het tool kent geen personen en hoort ze niet te raden: een verzonnen naam in een auditplanning
ziet eruit als een afspraak die iemand heeft gemaakt. `ROLLEN` hieronder is de plek waar een
auditor de rol per clausule vastlegt; tot die tijd staat er eerlijk dat het nog moet."""

ROLLEN: dict[tuple[str, str], str] = {}
"""Rol per `(norm, clausule)`, in te vullen door de auditor.

Bewust leeg opgeleverd. De rol invullen is organisatiekennis — wie bij deze organisatie over
toegangsrechten gaat — en die kennis zit niet in de norm en niet in dit tool. Een lege tabel die
`nog te bepalen` toont, is eerlijker dan een gevulde tabel met aannames."""


@dataclass(frozen=True)
class Vraag:
    """Eén interviewvraag, met het bewijslast-item waar hij vandaan komt."""

    tekst: str
    bewijslast: str
    """Het item uit de norm-catalogus. Zonder dit is de vraag niet herleidbaar, en een vraag in
    een auditdossier die niemand kan herleiden is precies wat dit tool weert."""


@dataclass
class Interviewvoorstel:
    """Wat een gesprek over deze clausule zou moeten ophalen."""

    norm: str
    clausule_id: str
    titel: str
    rol: str
    vragen: list[Vraag] = field(default_factory=list)

    def als_record(self) -> dict[str, Any]:
        return {
            "norm": self.norm,
            "clausule_id": self.clausule_id,
            "titel": self.titel,
            "rol": self.rol,
            "vragen": [{"tekst": v.tekst, "bewijslast": v.bewijslast} for v in self.vragen],
        }


def _vraag_voor(bewijslast: str) -> Vraag:
    """Zet één bewijslast-item om in een vraag naar de vindplaats.

    Vaste formulering en geen variatie: twee verschillende vragen over hetzelfde item zouden
    suggereren dat er twee verschillende eisen zijn.
    """
    kern = bewijslast.rstrip(".")
    return Vraag(
        tekst=f"Waar is '{kern}' vastgelegd? Als het niet bestaat: waarom niet?",
        bewijslast=bewijslast,
    )


def ongedekte_clausules(conn: sqlite3.Connection, norm: str) -> list[str]:
    """Clausules van deze norm zonder enige `clause_match`.

    Hergebruikt de bestaande gap-detectie uit `interview._haal_gaps_op` — dezelfde vraag hoort
    één antwoord te hebben, en twee implementaties lopen uit elkaar.
    """
    from iso_audit.interview import _haal_gaps_op

    return [str(g["clausule_id"]) for g in _haal_gaps_op(conn, norm)]


def stel_voor(conn: sqlite3.Connection, norm: str) -> list[Interviewvoorstel]:
    """Eén voorstel per ongedekte clausule die bewijslast kent.

    Clausules zonder bewijslast in de catalogus leveren geen voorstel op: dan is er niets
    concreets te vragen, en een gesprek zonder onderwerp is erger dan geen gesprek.
    """
    # Titels komen uit de clause-map en niet uit `normteksten`: die laatste heeft geen `titel`
    # per clausule (nagemeten 2026-08-22 — leeg voor élke 27001-clausule), en een voorstel dat
    # alleen "5.28" zegt laat de auditor eerst opzoeken waar het over gaat.
    from iso_audit.classification.clause_mapping import laad_clause_map

    titels = laad_clause_map(norm).get("clausules", {})

    voorstellen: list[Interviewvoorstel] = []
    for clausule_id in ongedekte_clausules(conn, norm):
        entry = normteksten.lookup(norm, clausule_id)
        if not entry:
            continue
        items = [str(b) for b in (entry.get("bewijslast") or []) if str(b).strip()]
        if not items:
            continue
        voorstellen.append(
            Interviewvoorstel(
                norm=norm,
                clausule_id=clausule_id,
                titel=str(titels.get(clausule_id, {}).get("titel", "")),
                rol=ROLLEN.get((norm, clausule_id), ROL_ONBEKEND),
                vragen=[_vraag_voor(b) for b in items],
            )
        )
    return voorstellen
