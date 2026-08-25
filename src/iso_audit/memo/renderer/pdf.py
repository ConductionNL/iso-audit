"""PDF-rendering via WeasyPrint, met een paginabudget.

Gescheiden module omdat WeasyPrint zware systeem-libs (pango/cairo) vereist; zo blijft de rest
van de memo-package importeerbaar zonder die afhankelijkheid.

**Het paginabudget is een klanteis en geen opmaakvoorkeur.** De managementmemo is één tot drie
A4; al het andere is verantwoording en hoort in de bijlage. Een memo die stil op vier pagina's
uitkomt breekt die eis zonder dat iemand het merkt — hetzelfde patroon als de PDF die maandenlang
ontbrak omdat de melding een `logger.warning` was.

Daarom wordt er geteld en gemeld, en wordt de memo **wel** geschreven: een auditor die hem te
lang vindt kan comprimeren, maar een memo die weigert helpt niemand. Het verschil met de
weigering bij ontbrekende normtekst is dat daar inhoud ontbrak; hier is de inhoud er en is
alleen de vorm te ruim.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_PAGINAS = 3
"""De harde klanteis: één tot drie A4."""


@dataclass(frozen=True)
class PaginaBudget:
    """Hoeveel pagina's de memo werd, en of dat binnen de eis valt.

    Afleesbaar zonder de PDF te openen, zodat de aanroeper erop kan sturen: loggen, in de
    run-samenvatting zetten, of in het portaal tonen.
    """

    pad: Path
    paginas: int
    past: bool
    melding: str = ""


def schrijf_pdf(html: str, output: Path | str) -> PaginaBudget:
    """Schrijf een (self-contained) HTML-string naar een PDF en tel de pagina's."""
    from weasyprint import HTML

    pad = Path(output)
    pad.parent.mkdir(parents=True, exist_ok=True)
    document = HTML(string=html).render()
    document.write_pdf(str(pad))

    paginas = len(document.pages)
    past = paginas <= MAX_PAGINAS
    melding = ""
    if not past:
        melding = (
            f"De memo is {paginas} pagina's; de eis is maximaal {MAX_PAGINAS} A4. "
            "Comprimeer de NC-blokken of verplaats verbeterpunten naar de bijlage."
        )
        logger.warning("%s", melding)
    return PaginaBudget(pad=pad, paginas=paginas, past=past, melding=melding)
