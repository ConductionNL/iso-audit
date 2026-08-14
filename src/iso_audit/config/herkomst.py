"""Herkomst vastleggen en geheimen maskeren.

Twee dingen die nergens anders mogen bestaan:

1. **`log_herkomst`** — bij het starten één regel per veld: welke bron won. Nooit een
   waarde. Dit is wat een auditor achteraf vraagt: liep die run op een cluster-Secret of
   op iets dat iemand in de UI had ingetypt?
2. **`masker`** — de enige plek die een bestaande geheime waarde gedeeltelijk toont. Eén
   implementatie, zodat er geen tweede maskering ontstaat die net iets meer laat zien.
"""

from __future__ import annotations

import json
import logging

from iso_audit.config.settings import VELDEN, Settings

_log = logging.getLogger("iso_audit.audit")

BULLET = "•"
ZICHTBAAR = 4
"""Aantal tekens dat `masker` laat staan — genoeg om te herkennen, te weinig om te
gebruiken."""

MINIMUM_BULLETS = 8
"""Vaste ondergrens, zodat de maskering de lengte van het geheim niet verraadt."""


def masker(waarde: str) -> str:
    """Maskeer een geheim voor weergave: `••••••••abcd`.

    De bullet-lengte is vast, niet proportioneel. Een proportionele maskering vertelt een
    lezer hoe lang het token is, en dat is informatie die hij niet nodig heeft.
    """
    if not waarde:
        return ""
    staart = waarde[-ZICHTBAAR:] if len(waarde) > ZICHTBAAR else ""
    return BULLET * MINIMUM_BULLETS + staart


def log_herkomst(settings: Settings) -> None:
    """Log per veld waar de waarde vandaan kwam. Nooit de waarde zelf."""
    for veld in VELDEN:
        w = settings[veld.sleutel]
        _log.info(
            json.dumps(
                {
                    "event": "config_herkomst",
                    "veld": veld.sleutel,
                    "bron": w.bron,
                    "ingesteld": w.ingesteld,
                    "geheim": veld.geheim,
                },
                ensure_ascii=False,
            )
        )


def overzicht(settings: Settings) -> list[dict[str, object]]:
    """Herkomst per veld, voor de UI en de API.

    Niet-geheime waarden komen mee zodat een auditor ziet wát er staat; geheime velden
    geven een maskering en verder niets.
    """
    rijen: list[dict[str, object]] = []
    for veld in VELDEN:
        w = settings[veld.sleutel]
        rijen.append(
            {
                "veld": veld.sleutel,
                "env": veld.env,
                "bron": w.bron,
                "ingesteld": w.ingesteld,
                "geheim": veld.geheim,
                "waarde": masker(w.waarde) if veld.geheim else w.waarde,
            }
        )
    return rijen
