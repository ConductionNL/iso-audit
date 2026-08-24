"""Het documentenlandschap: één voorraad, los van welke audit dan ook.

## Waarom dit los staat van een audit

De opslag was al gedeeld — één `AUDIT_DB_PATH` met `documents` en `clause_matches` voor de
hele tool — maar de handeling hing als runmodus ónder een audit. Dat schuurt: het landschap
is van de organisatie, niet van audit 2026-Q3. Twee audits zouden hetzelfde werk twee keer
doen, tegen dezelfde tabel, en "welk landschap heeft déze audit gezien" is dan een vraag
zonder antwoord.

Praktisch: een Drive-lezing kostte hier tweeënhalve minuut voor 409 documenten. Dat per
audit herhalen is verspilling zonder tegenprestatie.

## Wat hier niet gebeurt

Geen classificatie. Inlezen legt vast wát er is; het oordeel komt later en per audit. Zo is
de keten naar de bronnen te verifiëren zonder API-key, en gaat een dure lezing niet verloren
als de classificatie nog niet kan draaien.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("iso_audit.audit")


def documenten(*, zoek: str = "", bron: str = "", limiet: int = 200) -> list[dict[str, Any]]:
    """De ingelezen documenten, met hun clausule-koppelingen.

    Dit is het scherm waarop een auditor controleert óf het landschap klopt: welke
    bestanden zijn gezien, waar komen ze vandaan, en aan welke clausules zijn ze gekoppeld.
    Zonder die controle is een run een black box.

    `zoek` gebruikt de bestaande full-text-index (`documents_fts`), die al door triggers
    wordt bijgehouden. Geen tweede index, geen eigen zoeklogica.
    """
    from iso_audit.store import fts_query, verbinding

    conn = verbinding()
    try:
        params: list[Any] = []
        if zoek.strip():
            # FTS-match op naam en tekst; de index bestond al maar werd nergens gebruikt.
            basis = (
                "SELECT d.id, d.naam, d.herkomst, d.mime_type, d.modified_at "
                "FROM documents d JOIN documents_fts f ON f.rowid = d.rowid "
                "WHERE documents_fts MATCH ?"
            )
            # Niet de invoer zelf: FTS5 leest `non-conformiteiten` als een kolomnaam en
            # geeft dan een 500 in plaats van nul treffers. Zie `store.fts_query`.
            params.append(fts_query(zoek))
        else:
            basis = "SELECT d.id, d.naam, d.herkomst, d.mime_type, d.modified_at FROM documents d"
        if bron:
            basis += " AND d.herkomst = ?" if "WHERE" in basis else " WHERE d.herkomst = ?"
            params.append(bron)
        basis += " ORDER BY d.naam LIMIT ?"
        params.append(max(1, min(limiet, 1000)))

        rijen = conn.execute(basis, params).fetchall()
        uit: list[dict[str, Any]] = []
        for r in rijen:
            clausules = [
                str(c[0])
                for c in conn.execute(
                    "SELECT DISTINCT clausule_id FROM clause_matches WHERE doc_id = ? "
                    "ORDER BY clausule_id",
                    (r[0],),
                ).fetchall()
            ]
            uit.append(
                {
                    "id": str(r[0]),
                    "naam": str(r[1]),
                    "herkomst": str(r[2] or ""),
                    "mime_type": str(r[3] or ""),
                    "gewijzigd": str(r[4] or ""),
                    "clausules": clausules,
                }
            )
        return uit
    except Exception as exc:
        logger.info('{"event": "landschap_zoek_leeg", "reden": %r}', str(exc))
        return []
    finally:
        conn.close()


def lees_in(bronnen: list[str], *, on_log: Any = None) -> dict[str, Any]:
    """Lees de gekozen bronnen in en leg vast wat er gelezen is.

    Hergebruikt `pipeline.run_audit(alleen_ingest=True)` in plaats van de leeslogica te
    dupliceren: één administratie van hoe een bron wordt uitgelezen, niet twee die uit de
    pas kunnen lopen. `run_audit` valideert de `gws`-omgeving niet, dus dit pad werkt ook
    in de container waar die binary ontbreekt.

    Norm `beide`: de clausule-koppeling wordt voor 9001 én 27001 vastgelegd. Het landschap
    is niet van één norm — welke clausules een audit toetst, bepaalt de audit.
    """
    from iso_audit import pipeline

    mislukt: dict[str, str] = {}
    try:
        pipeline.run_audit(
            "beide",
            sources=list(bronnen),
            alleen_ingest=True,
            no_review=True,
        )
    except pipeline.BronIngestError as exc:
        # Wat wél gelezen is, is op dit punt al vastgelegd; alleen de melding komt hier
        # nog langs. Doorgaan is juist — één kapotte bron mag het landschap niet
        # blokkeren — maar het mag niet stil.
        mislukt = dict(exc.bronnen)

    uit = staat()
    uit["mislukt"] = mislukt
    return uit


def staat() -> dict[str, Any]:
    """Hoeveel documenten er zijn, per bron, en wanneer er voor het laatst is ingelezen.

    Zonder deze twee is "hebben we alles gezien?" niet te beantwoorden — en dat is precies
    de vraag die een auditor over zijn eigen dossier moet kunnen stellen.

    Een ontbrekende of lege database is een geldige toestand ("nog niets ingelezen"), geen
    fout: het portaal moet ook bruikbaar zijn vóór de eerste ingest.
    """
    from iso_audit.store import verbinding

    leeg: dict[str, Any] = {"documenten": 0, "per_bron": {}, "laatste": None, "bronnen": []}
    try:
        conn = verbinding()
        try:
            rijen = conn.execute(
                "SELECT herkomst, COUNT(*) FROM documents GROUP BY herkomst"
            ).fetchall()
            per_bron = {str(r[0] or "onbekend"): int(r[1]) for r in rijen}
            log = conn.execute(
                "SELECT bron, bestand_count, last_run FROM ingest_log ORDER BY last_run DESC"
            ).fetchall()
        finally:
            conn.close()
    except Exception as exc:  # nog geen DB, of geen tabellen
        logger.info('{"event": "landschap_leeg", "reden": %r}', str(exc))
        return leeg

    return {
        "documenten": sum(per_bron.values()),
        "per_bron": per_bron,
        "laatste": str(log[0][2]) if log else None,
        "bronnen": [
            {"bron": str(r[0]), "aantal": int(r[1] or 0), "wanneer": str(r[2])} for r in log
        ],
    }
