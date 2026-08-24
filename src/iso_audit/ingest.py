"""Audit ingest — bronnen (Drive, Miro, …) naar lokale SQLite DB.

Gemigreerd uit `Ops_to_Biz/audit/ingest.py` per milestone B §2.5.9.

Wijzigingen tegenover legacy versie:
- imports verwezen naar `iso_audit.*` modules (Drive via Source-adapter,
  Miro via `iso_audit.miro.ingest`);
- `--only` valideert tegen `sources.available()` zodat nieuwe Source-
  adapters automatisch herkenbaar zijn (Miro blijft als losse pseudo-
  source genoteerd zolang er geen `MiroSource`-adapter bestaat);
- type-hints toegevoegd voor mypy --strict.

Geen LLM nodig. Slaat alle tekst op zodat je later in Claude Code
direct kunt zoeken en vragen kunt stellen zonder API-kosten.

Gebruik:
    python -m iso_audit.ingest                  # Drive + Miro, beide normen
    python -m iso_audit.ingest --only drive     # alleen Drive
    python -m iso_audit.ingest --only miro      # alleen Miro
    python -m iso_audit.ingest --norm 9001      # alleen 9001-clausules matchen
"""

from __future__ import annotations

import argparse
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Miro is momenteel geen geregistreerde Source-adapter (zie §2.4.4); het
# blijft als pseudo-bron beschikbaar via deze module.
_PSEUDO_SOURCES: tuple[str, ...] = ("miro",)


def ingest_drive(norm: str) -> None:
    """Lees Drive-documenten in, koppel aan clausules, schrijf naar DB."""
    from iso_audit.classification.clause_mapping import koppel_alle_normen
    from iso_audit.sources.drive import haal_documenten_op
    from iso_audit.store import (
        initialiseer,
        log_ingest,
        upsert_clause_match,
        upsert_document,
        verbinding,
    )

    folder_id = os.environ.get("AUDIT_SOURCE_FOLDER_ID") or os.environ.get("AUDIT_DRIVE_FOLDER_ID")

    logger.info("=== Drive ingest gestart ===")
    documenten, handmatige_review = haal_documenten_op()

    logger.info("Clausule-mapping laden...")
    # Per norm koppelen: `laad_clause_map("beide")` laat 27001 de 9001-ingang overschrijven
    # bij een botsend nummer, en dan worden 18 van de 28 ISO 9001-clausules nooit getoetst.
    gekoppeld, niet_geclassificeerd = koppel_alle_normen(documenten, norm)

    conn = verbinding()
    initialiseer(conn)

    alle_docs = gekoppeld + niet_geclassificeerd
    for doc in alle_docs:
        upsert_document(conn, doc)
        for clausule_id, match_norm in doc.get("clausule_normen", []):
            upsert_clause_match(conn, doc["id"], "Drive", clausule_id, match_norm or norm)
        for clausule_id, sub_punt_id in doc.get("sub_punt_matches", []):
            match_norm = next(
                (n for c, n in doc.get("clausule_normen", []) if c == clausule_id), norm
            )
            upsert_clause_match(
                conn, doc["id"], "Drive", clausule_id, match_norm or norm, sub_punt_id
            )

    for item in handmatige_review:
        upsert_document(
            conn,
            {
                "id": item["id"],
                "naam": item["naam"],
                "tekst": f"[Handmatige review vereist: {item['reden']}]",
                "herkomst": "Drive",
                "mime_type": item.get("reden", ""),
            },
        )

    conn.commit()
    log_ingest(conn, "drive", folder_id, len(alle_docs))
    conn.close()

    logger.info(
        "Drive ingest klaar: %d documenten opgeslagen (%d gekoppeld, "
        "%d zonder match, %d handmatige review)",
        len(alle_docs),
        len(gekoppeld),
        len(niet_geclassificeerd),
        len(handmatige_review),
    )


def ingest_miro(norm: str) -> None:
    """Lees Miro-notities in, koppel aan clausules, schrijf naar DB."""
    from iso_audit.classification.clause_mapping import laad_clause_map
    from iso_audit.miro.ingest import haal_notities_op, koppel_aan_clausules
    from iso_audit.store import (
        initialiseer,
        log_ingest,
        upsert_clause_match,
        upsert_miro_note,
        verbinding,
    )

    board_id = os.environ.get("MIRO_BOARD_ID")
    if not board_id:
        logger.warning("MIRO_BOARD_ID niet ingesteld — Miro overgeslagen.")
        return

    logger.info("=== Miro ingest gestart (board: %s) ===", board_id)

    clause_map = laad_clause_map(norm)
    notities_raw = haal_notities_op()
    notities = koppel_aan_clausules(notities_raw, clause_map)

    conn = verbinding()
    initialiseer(conn)

    for notitie in notities:
        notitie_met_board = {**notitie, "board_id": board_id}
        upsert_miro_note(conn, notitie_met_board)
        if notitie.get("clausule"):
            upsert_clause_match(conn, notitie["miro_item_id"], "Miro", notitie["clausule"], norm)

    conn.commit()
    log_ingest(conn, "miro", board_id, len(notities))
    conn.close()

    logger.info("Miro ingest klaar: %d notities opgeslagen", len(notities))


def beschikbare_bronnen() -> list[str]:
    """Alle ingest-bare bronnen — Source-adapters + pseudo-sources.

    Trigger imports van de gebundelde adapters zodat hun ``@register``-
    decorator hen aan de Source-registry toevoegt voordat we deze opvragen.
    """
    from iso_audit import sources

    sources.laad_adapters()
    return sorted(set(sources.available()) | set(_PSEUDO_SOURCES))


def main(argv: list[str] | None = None) -> None:
    """CLI-entrypoint voor ingest."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Audit ingest — Drive + Miro naar lokale DB")
    parser.add_argument(
        "--norm",
        choices=["9001", "27001", "beide"],
        default=os.environ.get("AUDIT_NORM", "beide"),
    )
    parser.add_argument(
        "--only",
        choices=beschikbare_bronnen(),
        default=None,
        help="Alleen één bron inlezen (default: alle beschikbare)",
    )
    args = parser.parse_args(argv)

    if args.only != "miro":
        ingest_drive(args.norm)
    if args.only != "drive":
        try:
            ingest_miro(args.norm)
        except Exception as e:
            logger.warning("Miro ingest mislukt (niet kritiek): %s", e)

    logger.info(
        "=== Ingest klaar — DB: %s ===",
        os.environ.get("AUDIT_DB_PATH", "output/audit.db"),
    )


if __name__ == "__main__":
    main()
