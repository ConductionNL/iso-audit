"""Vraagassistent — leest het corpus, velt geen oordeel.

Vier agents met elk één bronregel; deze module bevat de eerste, de **Bronbevrager**:
antwoordt uitsluitend uit de vier bronnen van de organisatie (documentenlandschap,
bevindingen en trail, opvolgpunten, normteksten) en zegt "staat er niet in" als het
antwoord daar niet staat.

De scheiding op bronregel is het ontwerp, niet het onderwerp: een agent die niet uit
ons corpus put, kan ook niet per ongeluk als bewijs gelden. Zie
`openspec/changes/iso-agents/` voor de vier agents en hun grenzen.

Wat deze module **niet** doet: bevindingen aanmaken of wijzigen, triage voorstellen, of
de werkset aanraken. De auditor-spiegel is de capability die dit tool draagt — op vaste
punten houdt een mens het oordeel.
"""

from __future__ import annotations

from iso_audit.assistent.ophalen import Bron, Corpus, haal_bronnen_op
from iso_audit.assistent.vraag import (
    AntwoordOnverifieerbaarError,
    Assistentantwoord,
    beantwoord,
)

__all__ = [
    "AntwoordOnverifieerbaarError",
    "Assistentantwoord",
    "Bron",
    "Corpus",
    "beantwoord",
    "haal_bronnen_op",
]
