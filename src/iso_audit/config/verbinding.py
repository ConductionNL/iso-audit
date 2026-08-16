"""Foutmeldingen van leveranciers normaliseren voordat ze de UI bereiken.

## Waarom dit bestaat

`api/session.py:_check_source` gaf tot 2026-08-14 `str(exc)[:200]` door aan het
configuratiescherm. Die tekst komt rechtstreeks uit de client van de leverancier en kan
een URL met credential, een tokenfragment of een volledige request-dump bevatten — die
belandde dan in de browser en in alles wat de browser logt.

Deze module zet zo'n exception om naar **één van vier soorten** plus een vaste, leesbare
tekst. De ruwe melding gaat naar het serverlog (waar hij thuishoort voor diagnose) en
nooit naar de client.

## Geen tweede administratie

Dit is expliciet géén parallelle healthcheck: elke bron rapporteert zijn eigen status via
`healthcheck()`/`probe()`, en `bron_health` blijft de enige bron van waarheid daarvoor.
Hier zit alleen de vertaling van een *fout*, plus de Anthropic-check die geen
Source-adapter heeft.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

_log = logging.getLogger("iso_audit.audit")

Soort = Literal["niet_geconfigureerd", "auth", "niet_gevonden", "netwerk", "onbekend"]

TEKST: dict[Soort, str] = {
    # Deze soort komt **nooit** uit `classificeer()`: hij hoort bij een fout die wij zelf
    # vaststellen (een leeg verplicht veld), niet bij een respons van een leverancier. Er
    # is dan ook niets te beschermen, dus adapters mogen hier hun eigen tekst meegeven.
    "niet_geconfigureerd": "Deze bron is nog niet volledig ingevuld.",
    "auth": (
        "De credential is geweigerd. Controleer of hij nog geldig is en de juiste rechten heeft."
    ),
    "niet_gevonden": "De opgegeven bron bestaat niet of is niet gedeeld met dit account.",
    "netwerk": "De bron was niet bereikbaar. Probeer het opnieuw.",
    "onbekend": "De verbinding kon niet worden gelegd. Zie het serverlog voor details.",
}

# Patronen per soort. Bewust ruw en op woordniveau: een precieze mapping per leverancier
# zou een tweede administratie zijn die achterloopt op hun foutteksten.
_PATRONEN: tuple[tuple[Soort, re.Pattern[str]], ...] = (
    (
        "auth",
        re.compile(
            r"\b(401|403)\b|unauthor|forbidden|permission[ _]denied|invalid[ _-]?grant"
            # `api[ _-]?key` los, niet als `invalid api key`: de echte Anthropic-fout
            # luidt "invalid x-api-key" en die matchte niet op de nauwere vorm.
            r"|api[ _-]?key|authentication|unauthenticated|credential",
            re.I,
        ),
    ),
    ("niet_gevonden", re.compile(r"\b404\b|not[ _]?found|notfound|does not exist", re.I)),
    (
        "netwerk",
        re.compile(
            r"timed?[ _]?out|timeout|connection|unreachable|temporarily|name resolution"
            r"|dns|\b5\d\d\b|ssl|certificate",
            re.I,
        ),
    ),
)


def classificeer(melding: str) -> Soort:
    """Bepaal de soort fout uit een ruwe melding. Alleen de soort komt eruit."""
    for soort, patroon in _PATRONEN:
        if patroon.search(melding):
            return soort
    return "onbekend"


def normaliseer(exc: BaseException, *, bron: str) -> tuple[Soort, str]:
    """Zet een exception om naar `(soort, veilige tekst)` en log de ruwe melding.

    De ruwe melding gaat naar het serverlog omdat je zonder hem niets kunt diagnosticeren.
    Hij gaat **niet** naar de client, want daar hoort geen leveranciersrespons.
    """
    ruw = f"{type(exc).__name__}: {exc}"
    soort = classificeer(ruw)
    _log.warning(
        '{"event": "verbinding_fout", "bron": "%s", "soort": "%s", "detail": %r}',
        bron,
        soort,
        ruw[:500],
    )
    return soort, TEKST[soort]


def anthropic_check(model: str) -> dict[str, object]:
    """Lichtste read-only call die bewijst dat de credential werkt.

    `models.retrieve` kost geen tokens en raakt geen auditdata. Een classificatie
    draaien om te testen of de key werkt, zou geld kosten en de trail vervuilen.
    """
    try:
        import anthropic

        anthropic.Anthropic().models.retrieve(model)
    except Exception as exc:
        soort, tekst = normaliseer(exc, bron="anthropic")
        return {"connected": False, "soort": soort, "reden": tekst}
    return {"connected": True, "soort": "", "reden": ""}
