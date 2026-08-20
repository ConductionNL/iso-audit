"""LLM-gebaseerde clausule-classifier voor ISO 9001-documenten.

Gebruikt Claude Haiku om documenten semantisch te koppelen aan ISO
9001:2015 sub-clausules. Vervangt de keyword-gebaseerde `clause_matches`
voor norm `'9001'`.

Gemigreerd uit `Ops_to_Biz/audit/llm_classifier.py` per milestone B §2.2.7.
Wijzigingen: imports geüpdatet naar `iso_audit.data.normteksten` en
`iso_audit.store`; `SUB_OVERZICHT` lazily opgebouwd zodat de module bij
import niet faalt als normteksten nog niet geladen kunnen worden.

Gebruik:
    python -m iso_audit.classification.llm              # volledige run
    python -m iso_audit.classification.llm --droog      # dry-run
    python -m iso_audit.classification.llm --batch 10
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import anthropic
from dotenv import load_dotenv

from iso_audit import modellen
from iso_audit.classification.respons import GEEN_THINKING, tekst_uit

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = modellen.STANDAARD
"""Niet de auditor-keuze: die raakt alleen `classification/findings.py`."""
NORM = "9001"
MAX_TEKST = 500  # chars documenttekst meegestuurd
DEFAULT_BATCH = 8


def _bouw_sub_overzicht() -> str:
    """Bouw het sub-clausule-overzicht voor het system-prompt.

    Lazy zodat module-load niet faalt als `iso_audit.data.normteksten`
    runtime-niet-beschikbaar is.
    """
    from iso_audit.data.normteksten import NORMTEKSTEN_9001

    regels: list[str] = []
    for cid, data in NORMTEKSTEN_9001.items():
        for sp in data.get("sub_punten", []):
            regels.append(f"{cid}{sp['id']}: {sp['eis']}")
    return "\n".join(regels)


def _bouw_system_prompt() -> str:
    """Build the strict-auditor system prompt; lazy zodat overzicht lazy is."""
    return (
        "Je bent een ISO 9001:2015 interne auditor bij Conduction, een "
        "Nederlands softwarebedrijf dat open-source software maakt voor de "
        "publieke sector.\n\n"
        "Jouw taak: bepaal voor elk aangeboden document welke ISO 9001:2015 "
        "sub-clausules het als BEWIJSLAST dekt. Een document is alleen "
        "bewijs als het aantoonbaar maakt dat de organisatie aan de eis "
        "voldoet — niet als het de eis slechts vermeldt of bespreekt.\n\n"
        f"Beschikbare sub-clausules:\n{_bouw_sub_overzicht()}\n\n"
        "Regels:\n"
        "- Wees strikt en conservatief: liever te weinig dan te veel "
        "matches.\n"
        "- Een document mag meerdere sub-clausules dekken.\n"
        "- Geef een lege matches-lijst als het document geen relevante "
        "bewijslast is.\n"
        "- Geef ook de clausule op hoofdniveau (bijv. '4.1' zonder "
        "sub_punt) alleen als het document de volledige clausule dekt.\n\n"
        "Retourneer uitsluitend geldig JSON in dit formaat:\n"
        '{"resultaten": [{"doc_id": "<id>", "matches": '
        '[{"clausule": "4.1", "sub_punt": "b"}]}]}\n\n'
        "Gebruik exact dezelfde doc_id als aangeleverd. Geen uitleg buiten "
        "de JSON."
    )


def _classificeer_batch(
    docs: list[dict[str, Any]], client: anthropic.Anthropic
) -> list[dict[str, Any]]:
    """Klassificeer één batch documenten. Returnt rauwe `resultaten`-lijst."""
    invoer = "\n\n".join(
        f"DOC_ID: {d['id']}\nNAAM: {d['naam']}\nINHOUD: {d['tekst'][:MAX_TEKST]}" for d in docs
    )
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            thinking=GEEN_THINKING,
            system=_bouw_system_prompt(),
            messages=[{"role": "user", "content": invoer}],
        )
        tekst: str = tekst_uit(resp)
        start = tekst.find("{")
        eind = tekst.rfind("}") + 1
        if start == -1 or eind <= start:
            logger.warning("Geen JSON in response: %s", tekst[:100])
            return []
        resultaten: list[dict[str, Any]] = json.loads(tekst[start:eind]).get("resultaten", [])
        return resultaten
    except (json.JSONDecodeError, anthropic.APIError) as e:
        logger.error("Fout bij batch: %s", e)
        return []


def run(batch_grootte: int = DEFAULT_BATCH, droog: bool = False) -> None:
    """Volledige classificatierun: laad documenten, klassificeer in batches.

    Verifieert API-connectiviteit vóór het verwijderen van bestaande
    matches; bij `droog` worden geen DB-mutaties uitgevoerd.
    """
    from iso_audit.store import upsert_clause_match, verbinding

    conn = verbinding()
    docs: list[dict[str, Any]] = [
        dict(r)
        for r in conn.execute(
            "SELECT id, naam, tekst FROM documents WHERE herkomst='Drive' ORDER BY naam"
        ).fetchall()
    ]
    logger.info("%d documenten te classificeren (batch=%d)", len(docs), batch_grootte)

    client = anthropic.Anthropic()
    totaal_batches = (len(docs) + batch_grootte - 1) // batch_grootte
    totaal_matches = 0

    if not droog:
        logger.info("API-connectiviteitscheck...")
        try:
            client.messages.create(
                model=MODEL,
                max_tokens=16,
                messages=[{"role": "user", "content": "ping"}],
            )
        except anthropic.APIError as e:
            logger.error("API niet beschikbaar (%s) — stop zonder DB-wijzigingen", e)
            conn.close()
            return
        logger.info("API OK — verwijder bestaande keyword-matches voor norm=%s", NORM)
        conn.execute("DELETE FROM clause_matches WHERE norm=? AND herkomst='Drive'", (NORM,))
        conn.commit()

    for batch_nr, i in enumerate(range(0, len(docs), batch_grootte), 1):
        batch = docs[i : i + batch_grootte]
        logger.info(
            "Batch %d/%d — %s t/m %s",
            batch_nr,
            totaal_batches,
            batch[0]["naam"][:40],
            batch[-1]["naam"][:40],
        )

        resultaten = _classificeer_batch(batch, client)
        doc_map = {d["id"]: d for d in batch}

        for res in resultaten:
            doc_id = res.get("doc_id", "")
            if doc_id not in doc_map:
                logger.warning("Onbekend doc_id in response: %s", doc_id)
                continue
            matches = res.get("matches", [])
            if not matches:
                continue

            if droog:
                logger.info(
                    "  [DROOG] %s → %s",
                    doc_map[doc_id]["naam"][:50],
                    [(m["clausule"], m.get("sub_punt", "")) for m in matches],
                )
                totaal_matches += len(matches)
                continue

            for m in matches:
                cid = m.get("clausule", "")
                sp = m.get("sub_punt", "")
                if not cid:
                    continue
                upsert_clause_match(conn, doc_id, "Drive", cid, NORM, sp)
                # Zorg ook voor clausule-niveau record.
                upsert_clause_match(conn, doc_id, "Drive", cid, NORM, "")
                totaal_matches += 1

        if not droog:
            conn.commit()

    conn.close()
    logger.info(
        "Klaar: %d matches voor %d documenten (%s)",
        totaal_matches,
        len(docs),
        "DRY-RUN" if droog else "opgeslagen",
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="LLM-classifier voor ISO 9001 clausule-matching")
    parser.add_argument("--droog", action="store_true", help="Dry-run, geen DB-wijzigingen")
    parser.add_argument(
        "--batch", type=int, default=DEFAULT_BATCH, help="Batch-grootte (default: 8)"
    )
    args = parser.parse_args()
    run(batch_grootte=args.batch, droog=args.droog)
    return 0
