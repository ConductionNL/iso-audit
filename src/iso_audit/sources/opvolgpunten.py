"""Openstaande punten uit een bron — de P-D-C-A-kant van een audit.

## Waarom dit apart staat van de documentingest

Niet elke bron levert bewijsmateriaal. Een Jira-ticket met label `iso27001` is een
**afgesproken verbeteractie die nog openstaat**, geen document waaruit je kunt afleiden of
een clausule wordt nageleefd.

Tot 2026-08-15 ging Jira toch via `list_documents`, waarna elk ticket tegen elke clausule
werd geclassificeerd. Het resultaat staat in de referentie-output van juni:

    9001, 4.1, …, NC, …, "Houden aan de afspraak", Jira,
    "Document behandelt procesuitvoering via Jira, niet inzicht in organisatiecontext…"

Een ticket krijgt een NC omdat het geen bewijs is voor iets waarvoor het nooit bedoeld was.
Dat is ruis, het kost LLM-tokens per ticket, en het vervuilt de spiegel die dit tool de
auditor voorhoudt.

Het `Source`-protocol modelleerde dit al met `list_findings`. Die had alleen nul
aanroepers: de weg bestond en was nooit aangesloten.

## Geen classificatie

Een opvolgpunt is al beoordeeld door degene die het aanmaakte. Het gaat daarom ongewijzigd
naar de triage, waar de auditor besluit of het nog steeds relevant is. Dat scheelt kosten
en het is bovendien eerlijker: het tool doet geen oordeel alsof het er zelf een had.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

HERKOMST_ACHTERVOEGSEL = "-opvolging"
"""Zodat een opvolgpunt in de trail te onderscheiden is van bewijs uit dezelfde bron."""

CLASSIFICATIE = "OFI"
"""Een openstaande verbeteractie is een verbeterpunt, geen door ons vastgestelde
afwijking. `NC` zou beweren dat wíj een tekortkoming constateerden; dat deden we niet — we
nemen over wat er al openstond."""

_ZONDER_CLAUSULE = "0"
"""Clausule-id voor een punt waarvan het label geen clausule aanwijst. Weglaten kan niet:
de `bevindingen`-tabel heeft `clausule_id` in zijn unieke sleutel. Zo blijft het punt
zichtbaar in plaats van stil te verdwijnen."""


def levert_opvolgpunten(naam: str) -> bool:
    """Levert deze bron opvolgpunten in plaats van documenten?

    Expliciet op de adapter (`levert_opvolgpunten = True`) en niet afgeleid uit "geeft
    `list_findings` iets terug": dat laatste zou een bron bij een lege lijst stilletjes van
    rol laten wisselen, en dan hangt het gedrag af van de data in plaats van van het model.
    """
    from iso_audit import sources

    try:
        adapter = sources.get(naam)
    except KeyError:
        return False
    return bool(getattr(adapter, "levert_opvolgpunten", False))


def haal_op(naam: str, sessie_id: str) -> list[dict[str, Any]]:
    """Openstaande punten uit bron ``naam``, in de vorm die de `bevindingen`-tabel kent.

    Dezelfde dict-shape als de classifier oplevert, zodat ze via het bestaande pad in de
    triage en de memo terechtkomen. Eén administratie, geen tweede tabel.
    """
    from iso_audit import sources

    adapter = sources.get(naam)()
    herkomst = naam.capitalize() + HERKOMST_ACHTERVOEGSEL
    punten: list[dict[str, Any]] = []
    for f in adapter.list_findings(sessie_id):
        clausules = list(f.clausule_ids) or [_ZONDER_CLAUSULE]
        for clausule in clausules:
            punten.append(
                {
                    "_doc_id": f.id,
                    "herkomst": herkomst,
                    "clausule": clausule,
                    "classificatie": CLASSIFICATIE,
                    "document_naam": f.omschrijving[:120] or f.id,
                    "beschrijving": f.omschrijving,
                    "onderbouwing": (
                        "Openstaande verbeteractie uit "
                        f"{naam}; overgenomen zonder classificatie. "
                        f"Bewijs: {', '.join(f.bewijs_uris) or '—'}"
                    ),
                    "pre_classificatie": None,
                }
            )
    logger.info("Bron %s: %d openstaand(e) punt(en)", naam, len(punten))
    return punten
