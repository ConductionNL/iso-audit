"""Bestaande 27001-clausuleverwijzingen omzetten naar de `A.`-nummering van Bijlage A.

Op 2026-08-28 kreeg Bijlage A de `A.`-prefix zodat de managementclausules 4 t/m 10 erbij konden.
Tot dat moment bevatte de norm-DB alleen de 93 maatregelen, genummerd `5.1` t/m `8.34` — de helft
van de certificeringseis werd nooit getoetst, en dat kwam pas boven water toen de auditor
hoofdstuk 4 koos en een foutmelding kreeg.

Zonder migratie wijst een bestaande bevinding op `5.1` na de wijziging naar "Leiderschap en
betrokkenheid" in plaats van naar "Beleid voor informatiebeveiliging". Een bevinding die naar een
andere eis verwijst dan waarop ze is vastgesteld, is erger dan geen bevinding.

**De migratie is eenduidig, maar eenmalig.** Vóór deze wijziging bestond er niets anders: élke
opgeslagen 27001-clausule was een Bijlage A-maatregel. Dat geldt niet meer zodra er een run met
de nieuwe nummering is geweest — daarom zet dit alleen nummers zonder prefix om die óók als
maatregel bestaan, en laat het alles wat al klopt met rust. Twee keer draaien verandert niets.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

NORM_DB = Path("examples/norms/iso-27001-2022.yaml")


@lru_cache(maxsize=1)
def _maatregelnummers() -> frozenset[str]:
    """De Bijlage A-nummers zónder prefix, uit de norm-DB zelf.

    Uit de DB en niet uit een tweede lijst: een hardgecodeerde opsomming van 93 nummers loopt
    uit de pas zodra de norm-DB verandert, en dan migreert deze functie naar clausules die niet
    bestaan.
    """
    import yaml

    if not NORM_DB.is_file():
        return frozenset()
    ruw = yaml.safe_load(NORM_DB.read_text(encoding="utf-8")) or {}
    return frozenset(k[2:] for k in (ruw.get("clauses") or {}) if k.startswith("A."))


def migreer_clausule(clausule: str, norm: str) -> str:
    """Zet één clausulenummer om. Alles wat niet eenduidig is, blijft ongewijzigd.

    `norm` is de code (`"27001"`, `"9001"`). ISO 9001 heeft geen Bijlage A; daar zou prefixen de
    clausule juist onvindbaar maken.
    """
    if norm != "27001" or clausule.startswith("A."):
        return clausule
    if clausule in _maatregelnummers():
        return f"A.{clausule}"
    return clausule
