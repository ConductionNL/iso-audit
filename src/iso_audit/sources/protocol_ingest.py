"""Generieke ingest via het `Source`-Protocol → pipeline-document-dicts.

Brug tussen de pluggable Source-adapters (`list_documents` + `fetch_content`)
en de bestaande pipeline, die met document-dicts werkt (zelfde shape als
`DriveSource.haal_documenten_op`). Hierdoor kan `run_audit` elke geselecteerde
bron (Jira, Planning, … en straks GitHub/Codeberg) inlezen — niet alleen de
historisch hardcoded Drive + Miro.

Boring & auditable: één pure-genoeg functie die per Document één dict bouwt;
leesfouten op één document zijn nooit fataal (gelogd + overgeslagen).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any

from iso_audit import sources

logger = logging.getLogger(__name__)


OPNIEUW_LEZEN_ENV = "ISO_AUDIT_OPNIEUW_LEZEN"
OPNIEUW_LEZEN = (os.environ.get(OPNIEUW_LEZEN_ENV) or "").strip().lower() in {
    "1",
    "true",
    "ja",
    "aan",
    "on",
    "yes",
}
"""Negeer de opgeslagen tekst en haal alles opnieuw op.

Na een wijziging in de lezers is de opgeslagen tekst verouderd zonder dat de bron dat weet: op
2026-08-24 werden 32 OpenDocument-bestanden voor het eerst leesbaar, en met alleen een
tijdstempel-vergelijking zouden die als "ongewijzigd" nooit binnen zijn gekomen. Een cache
zonder uitweg is een val."""


def bekende_teksten(conn: sqlite3.Connection, herkomst: str) -> dict[str, tuple[str, str]]:
    """Wat er al is ingelezen voor deze bron: id → (wijzigingstijd, tekst).

    Op herkomst gescheiden: twee bronnen kunnen hetzelfde document-id gebruiken, en dan zou de
    tekst van de ene voor de andere doorgaan.
    """
    rijen = conn.execute(
        "SELECT id, modified_at, tekst FROM documents WHERE herkomst = ?", (herkomst,)
    ).fetchall()
    return {str(r[0]): (str(r[1] or ""), str(r[2] or "")) for r in rijen}


def mag_overslaan(
    doc_id: str, gewijzigd: str | None, bekend: dict[str, tuple[str, str]]
) -> str | None:
    """De opgeslagen tekst als het document niet is veranderd, anders `None`.

    Drie redenen om tóch te lezen, elk gemeten:

    - **Geen wijzigingstijd.** Planning levert rijen uit een sheet zonder tijdstempel — 150 van
      de 709 documenten. Een geraden tijd zou een document als ongewijzigd markeren terwijl
      niemand dat weet.
    - **Leeg opgeslagen.** Leeg betekent niet gelezen; overslaan zou de leegte bevriezen.
    - **`--opnieuw-lezen`.** Zie `OPNIEUW_LEZEN`.
    """
    if OPNIEUW_LEZEN or not gewijzigd:
        return None
    vorige = bekend.get(doc_id)
    if not vorige:
        return None
    vorig_gewijzigd, tekst = vorige
    if not tekst.strip() or vorig_gewijzigd != gewijzigd:
        return None
    return tekst


def ingest_documenten(naam: str) -> list[dict[str, Any]]:
    """Lees alle documenten van bron ``naam`` in als pipeline-document-dicts.

    Mapt elk ``Document`` (+ ``fetch_content``) naar de dict-shape die
    ``koppel_documenten`` / ``classificeer_alle_bevindingen`` verwachten::

        {"naam", "id", "mime_type", "tekst", "herkomst", "modified_at"}

    ``herkomst`` is de bronnaam met hoofdletter (``"jira"`` → ``"Jira"``) en
    wordt zo in de ``bevindingen``-tabel vastgelegd, zodat een bevinding terug
    te voeren is op zijn bron. Documenten die niet leesbaar zijn worden
    overgeslagen (gelogd), nooit fataal.

    :raises KeyError: als ``naam`` geen geregistreerde Source-adapter is.
    """
    adapter = sources.get(naam)()
    herkomst = naam.capitalize()
    bekend = _bekend_voor(herkomst)
    docs: list[dict[str, Any]] = []
    hergebruikt = 0
    for d in adapter.list_documents():
        # De listing draait altijd volledig — dat is de enige manier om te merken dat een
        # document verdwenen of bijgekomen is, en het is 65 s van de 1.200 die Drive kost.
        # Alleen het ophalen van de inhoud (2,49 s per document) wordt overgeslagen.
        bewaard = mag_overslaan(d.id, d.laatst_gewijzigd, bekend)
        if bewaard is not None:
            hergebruikt += 1
            tekst = bewaard
        else:
            try:
                tekst = adapter.fetch_content(d)
            except Exception as e:  # één onleesbaar document mag de run niet breken
                logger.warning("Bron %s: kon document %r niet lezen: %s", naam, d.id, e)
                continue
        docs.append(
            {
                "naam": d.titel,
                "id": d.id,
                "mime_type": d.type or "",
                "tekst": tekst,
                "herkomst": herkomst,
                "modified_at": d.laatst_gewijzigd or None,
            }
        )
    # Hergebruik expliciet melden: een dekking die zwijgt over wat er niet opnieuw is gelezen,
    # laat de auditor denken dat alles vers is opgehaald.
    logger.info(
        "Bron %s: %d document(en) ingelezen via Source-Protocol (%d hergebruikt uit een "
        "eerdere run, %d opgehaald)",
        naam,
        len(docs),
        hergebruikt,
        len(docs) - hergebruikt,
    )
    return docs


def _bekend_voor(herkomst: str) -> dict[str, tuple[str, str]]:
    """Wat er al is ingelezen; een onbereikbare database betekent gewoon alles opnieuw lezen."""
    try:
        from iso_audit.store import initialiseer, verbinding

        conn = verbinding()
        try:
            initialiseer(conn)
            return bekende_teksten(conn, herkomst)
        finally:
            conn.close()
    except Exception as fout:
        logger.warning("Kon eerdere teksten niet lezen (alles wordt opnieuw opgehaald): %s", fout)
        return {}
