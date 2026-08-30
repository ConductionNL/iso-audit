"""Lokale SQLite opslag voor audit-landschap.

Schema:
  documents       — Drive-bestanden met volledige tekst
  miro_notes      — Miro sticky notes / tekstvakken
  clause_matches  — welke documenten matchen welke clausules
  ingest_log      — wanneer is welke bron voor het laatst gesynchroniseerd
  bevindingen     — geclassificeerde audit-bevindingen (NC/OFI/positief)
  interviews      — handmatige bevindingen per clausule
  classifications — traceability-laag (§2.6.3): elke LLM-call wordt vóór
                    consumptie gepersisteerd inclusief prompt/model-versie,
                    input-hash, raw output, usage en duur. Dedup-key:
                    (audit_id, finding_id, prompt_versie, model_versie).
  decisions       — audit-trail (§3.1.3): elk hoog-risico beslismoment
                    (autonoom selectief; integer altijd voor hoog) plus
                    de uiteindelijke auditor-actie. Append-only.
  assistent_vragen — wat de auditor het tool vroeg, met het antwoord, de bronnen
                    die aan het model meegingen, welke daarvan terugkwamen, en de
                    kosten met peildatum en grondslag. Append-only.

FTS5 full-text search op documents.naam + documents.tekst voor lokaal
zoeken zonder API-kosten.

Schema-stabiliteit: het schema is ongewijzigd t.o.v. `Ops_to_Biz/audit/store.py`
op de bestaande tabellen. Nieuwe tabellen (`classifications`) zijn additief
en idempotent (`CREATE TABLE IF NOT EXISTS`); oude `audit.db`-bestanden
blijven werken.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# src/iso_audit/store.py → parent (iso_audit) → parent (src) → parent (repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = str(_REPO_ROOT / "output" / "audit.db")


_fallback_gemeld = False


def db_pad() -> str:
    """Lokatie van de SQLite-database; override via `AUDIT_DB_PATH`-env.

    Zonder die env-var valt de functie terug op een pad **binnen de repo**. Dat is
    prima voor een lokale CLI-run, maar in het portaal is het fout: het image draait
    met `readOnlyRootFilesystem` en een append-only audit-trail op een vluchtig
    filesystem is geen audit-trail. Conform de repo-conventie ("env-var-fallbacks
    bestaan, maar loggen expliciet dat er fallback wordt gebruikt") wordt het
    gebruik van de fallback één keer per proces gemeld in plaats van stil te
    gebeuren.
    """
    global _fallback_gemeld
    expliciet = os.environ.get("AUDIT_DB_PATH")
    if expliciet:
        return expliciet
    if not _fallback_gemeld:
        logger.warning(
            "AUDIT_DB_PATH niet gezet — fallback naar %s (binnen de repo/het image). "
            "In het portaal MOET dit op persistente opslag staan; zie change "
            "iso-portal, capability portal-deployment.",
            DEFAULT_DB_PATH,
        )
        _fallback_gemeld = True
    return DEFAULT_DB_PATH


def verbinding(pad: str | None = None) -> sqlite3.Connection:
    """Open SQLite-verbinding met WAL + foreign keys aan."""
    pad = pad or db_pad()
    parent = os.path.dirname(pad)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(pad)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migreer_clause_matches_norm(conn: sqlite3.Connection) -> None:
    """Zet `norm` in de primaire sleutel van een bestaande `clause_matches`.

    `CREATE TABLE IF NOT EXISTS` raakt een bestaande tabel niet aan, dus zonder deze migratie
    zou de sleutelwijziging alleen voor nieuwe databases gelden en zou elke bestaande
    installatie de tweede koppeling op een botsend clausulenummer blijven weggooien.

    SQLite kan een primaire sleutel niet wijzigen; de tabel wordt daarom opnieuw opgebouwd,
    binnen één transactie — een half gemigreerde tabel is erger dan een oude.
    """
    kolommen = conn.execute("PRAGMA table_info(clause_matches)").fetchall()
    if not kolommen:
        return  # tabel bestaat nog niet; `initialiseer` maakt hem hieronder meteen goed aan
    if any(naam == "norm" and pk for _, naam, _, _, _, pk in kolommen):
        return
    conn.executescript(
        """
        BEGIN;
        CREATE TABLE clause_matches_migratie (
            doc_id      TEXT NOT NULL,
            herkomst    TEXT NOT NULL,
            clausule_id TEXT NOT NULL,
            norm        TEXT NOT NULL,
            sub_punt    TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (doc_id, herkomst, clausule_id, norm, sub_punt)
        );
        INSERT OR IGNORE INTO clause_matches_migratie
            SELECT doc_id, herkomst, clausule_id, norm, sub_punt FROM clause_matches;
        DROP TABLE clause_matches;
        ALTER TABLE clause_matches_migratie RENAME TO clause_matches;
        COMMIT;
        """
    )
    logger.info("clause_matches gemigreerd: norm toegevoegd aan de primaire sleutel")


def _migreer_bevindingen_kolommen(conn: sqlite3.Connection) -> None:
    """Voeg `audit_id`, `ernst` en `onbruikbaar` toe aan een bestaande `bevindingen`.

    `CREATE TABLE IF NOT EXISTS` raakt een bestaande tabel niet aan, dus zonder deze migratie
    zouden de nieuwe velden alleen in een verse database bestaan — en dan is de prompt wel
    aangepast maar valt het resultaat bij het opslaan weg.

    `ALTER TABLE ... ADD COLUMN` volstaat hier: er verandert niets aan de sleutel, en bestaande
    rijen krijgen `NULL` respectievelijk `0`. Dat is precies wat ze zijn — van vóór dit
    onderscheid.
    """
    kolommen = {r[1] for r in conn.execute("PRAGMA table_info(bevindingen)")}
    if not kolommen:
        return
    if "audit_id" not in kolommen:
        conn.execute("ALTER TABLE bevindingen ADD COLUMN audit_id TEXT")
    if "ernst" not in kolommen:
        conn.execute("ALTER TABLE bevindingen ADD COLUMN ernst TEXT")
        logger.info("bevindingen gemigreerd: kolom ernst toegevoegd")
    if "onbruikbaar" not in kolommen:
        conn.execute("ALTER TABLE bevindingen ADD COLUMN onbruikbaar INTEGER NOT NULL DEFAULT 0")
        logger.info("bevindingen gemigreerd: kolom onbruikbaar toegevoegd")


def initialiseer(conn: sqlite3.Connection) -> None:
    """Maak alle tabellen aan als ze nog niet bestaan, en voer schema-migraties uit."""
    _migreer_clause_matches_norm(conn)
    _migreer_bevindingen_kolommen(conn)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id          TEXT PRIMARY KEY,
            naam        TEXT NOT NULL,
            tekst       TEXT NOT NULL DEFAULT '',
            herkomst    TEXT NOT NULL DEFAULT 'Drive',
            mime_type   TEXT,
            modified_at TEXT,           -- Drive modifiedTime (ISO 8601), NULL als onbekend
            ingested_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS miro_notes (
            id                TEXT PRIMARY KEY,
            tekst             TEXT NOT NULL,
            kleur             TEXT,
            pre_classificatie TEXT,
            board_id          TEXT,
            ingested_at       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS clause_matches (
            doc_id      TEXT NOT NULL,
            herkomst    TEXT NOT NULL,   -- 'Drive' | 'Miro'
            clausule_id TEXT NOT NULL,
            norm        TEXT NOT NULL,
            sub_punt    TEXT NOT NULL DEFAULT '',  -- '' = clausule-niveau, 'a'/'b'/... = sub-punt
            -- `norm` hoort in de sleutel: achttien clausulenummers bestaan in beide normen
            -- (§5.1, §6.1, §7.5, §8.4 …) en betekenen daar iets anders. Zonder norm in de
            -- sleutel gooide `INSERT OR IGNORE` de tweede koppeling stil weg.
            PRIMARY KEY (doc_id, herkomst, clausule_id, norm, sub_punt)
        );

        CREATE TABLE IF NOT EXISTS ingest_log (
            bron        TEXT PRIMARY KEY,  -- 'drive' | 'miro'
            folder_id   TEXT,
            bestand_count INTEGER,
            last_run    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bevindingen (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id           TEXT NOT NULL,
            herkomst         TEXT NOT NULL,
            clausule_id      TEXT NOT NULL,
            norm             TEXT NOT NULL,
            classificatie    TEXT NOT NULL,
            -- 'major' | 'minor' | NULL. Alleen bij een NC: major betekent dat het proces als
            -- geheel afwezig of gebroken is en certificering in gevaar komt.
            ernst            TEXT,
            beschrijving     TEXT,
            onderbouwing     TEXT,
            -- Oordeel zonder beschrijving én zonder onderbouwing. Niet weggegooid — dát het
            -- model het zo teruggaf is een gegeven — maar telt niet mee als bevinding.
            onbruikbaar      INTEGER NOT NULL DEFAULT 0,
            pre_classificatie TEXT,
            document_naam    TEXT,
            classified_at    TEXT NOT NULL,
            -- Welke audit deze bevinding heeft opgeleverd. Zonder deze kolom exporteerde élke
            -- audit alles wat er ooit in de tabel was beland: op 2026-08-30 toonde een schone
            -- audit 247 bevindingen terwijl de run er zes had opgeleverd. Archiveren van de
            -- vorige audit hielp niet — de bevindingen zitten hier, niet in de auditmap.
            audit_id         TEXT,
            UNIQUE(doc_id, herkomst, clausule_id, norm)
        );

        -- Eén rij per (norm, clausule): de autonome review oordeelt over een clausule als
        -- geheel, niet per bevinding. De memo-bouwer leest hier de kernzin en de voorgestelde
        -- actietabel; het ruwe antwoord met tijdstempel blijft in `assistent_vragen`.
        CREATE TABLE IF NOT EXISTS review_adviezen (
            norm                TEXT NOT NULL,
            clausule_id         TEXT NOT NULL,
            advies              TEXT NOT NULL,
            voorgestelde_klasse TEXT,
            ernst               TEXT,
            kern                TEXT NOT NULL DEFAULT '',
            reden               TEXT NOT NULL DEFAULT '',
            acties_json         TEXT NOT NULL DEFAULT '[]',
            beoordeeld_op       TEXT NOT NULL,
            PRIMARY KEY (norm, clausule_id)
        );

        CREATE TABLE IF NOT EXISTS interviews (
            clausule_id    TEXT NOT NULL,
            norm           TEXT NOT NULL,
            bevinding      TEXT NOT NULL,  -- 'NC' | 'OFI' | 'positief' | 'overgeslagen'
            antwoord       TEXT,           -- korte ja/nee/deels samenvatting
            notitie        TEXT,           -- vrije toelichting van de auditor
            interviewed_at TEXT NOT NULL,
            PRIMARY KEY (clausule_id, norm)
        );

        CREATE TABLE IF NOT EXISTS classifications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id        TEXT NOT NULL,    -- run-id voor groepering
            finding_id      TEXT NOT NULL,    -- 'drive:<doc>:<clausule>' of 'miro:<batch>'
            input_hash      TEXT NOT NULL,    -- sha256(system + user)
            prompt_versie   TEXT NOT NULL,    -- sha256(system) — prompt-logic-versie
            model_versie    TEXT NOT NULL,    -- bv. claude-haiku-4-5-20251001
            raw_output      TEXT,             -- response.content[0].text
            usage_json      TEXT,             -- {input_tokens, output_tokens, cache_*}
            elapsed_s       REAL,
            created_at      TEXT NOT NULL,
            UNIQUE(audit_id, finding_id, prompt_versie, model_versie)
        );

        CREATE INDEX IF NOT EXISTS idx_classifications_audit
            ON classifications(audit_id);
        CREATE INDEX IF NOT EXISTS idx_classifications_finding
            ON classifications(finding_id);

        CREATE TABLE IF NOT EXISTS decisions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id         TEXT NOT NULL,
            punt             TEXT NOT NULL,    -- e.g. 'classify_finding', 'send_report'
            context_json     TEXT NOT NULL,
            voorstel_json    TEXT NOT NULL,
            status           TEXT NOT NULL,    -- 'pending' | 'resolved' | 'cancelled'
            besluit_json     TEXT,             -- definitief besluit; NULL als status=pending
            risico           TEXT NOT NULL,    -- 'laag' | 'midden' | 'hoog'
            classificatie_id INTEGER,          -- optionele link naar classifications.id
            -- notifier_naam: NULL voor autonoom; 'slack'/'email'/... voor integer
            notifier_naam    TEXT,
            created_at       TEXT NOT NULL,
            resolved_at      TEXT,
            FOREIGN KEY (classificatie_id) REFERENCES classifications(id)
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_audit_status
            ON decisions(audit_id, status);
        CREATE INDEX IF NOT EXISTS idx_decisions_punt_resolved
            ON decisions(punt, resolved_at);

        -- Vraagassistent: append-only, nooit overschreven.
        --
        -- `meegegeven_json` is het punt waarop een antwoord later na te trekken is: een
        -- antwoord dat achteraf verkeerd blijkt is alleen te begrijpen als je weet wat de
        -- assistent op dat moment kon zien. `gebruikt_json` zegt welke daarvan in het
        -- antwoord terugkwamen — dat verschil is zelf informatie.
        --
        -- Kosten met peildatum én grondslag, om dezelfde reden als in `runs.jsonl`: een
        -- bedrag zonder grondslag is niet te lezen, want lijstprijs is niet hetzelfde als
        -- wat er gefactureerd wordt.
        CREATE TABLE IF NOT EXISTS assistent_vragen (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            agent            TEXT NOT NULL,    -- 'bronbevrager' | 'normuitlegger' | ...
            vraag            TEXT NOT NULL,
            antwoord         TEXT NOT NULL,
            meegegeven_json  TEXT NOT NULL,    -- bron-records die aan het model meegingen
            gebruikt_json    TEXT NOT NULL,    -- bron-ID's die in het antwoord terugkomen
            model            TEXT NOT NULL,
            usd              REAL NOT NULL DEFAULT 0,
            prijzen_peildatum TEXT NOT NULL,
            prijzen_grondslag TEXT NOT NULL,
            storing          TEXT,             -- reden als het antwoord niet geldig was
            gesteld_door     TEXT NOT NULL DEFAULT '',
            gesteld_op       TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_assistent_gesteld_op
            ON assistent_vragen(gesteld_op);

        -- FTS5 full-text search over naam + tekst
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
            USING fts5(naam, tekst, content=documents, content_rowid=rowid);

        -- FTS triggers to keep index in sync
        CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, naam, tekst)
            VALUES (new.rowid, new.naam, new.tekst);
        END;

        CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, naam, tekst)
            VALUES ('delete', old.rowid, old.naam, old.tekst);
        END;

        CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, naam, tekst)
            VALUES ('delete', old.rowid, old.naam, old.tekst);
            INSERT INTO documents_fts(rowid, naam, tekst)
            VALUES (new.rowid, new.naam, new.tekst);
        END;
    """)
    conn.commit()


def upsert_document(conn: sqlite3.Connection, doc: dict[str, Any]) -> None:
    """Idempotente insert/update van een document-rij."""
    conn.execute(
        """
        INSERT INTO documents (id, naam, tekst, herkomst, mime_type, modified_at, ingested_at)
        VALUES (:id, :naam, :tekst, :herkomst, :mime_type, :modified_at, :ingested_at)
        ON CONFLICT(id) DO UPDATE SET
            naam        = excluded.naam,
            tekst       = excluded.tekst,
            herkomst    = excluded.herkomst,
            mime_type   = excluded.mime_type,
            modified_at = COALESCE(excluded.modified_at, modified_at),
            ingested_at = excluded.ingested_at
        """,
        {
            "id": doc["id"],
            "naam": doc["naam"],
            "tekst": doc.get("tekst", ""),
            "herkomst": doc.get("herkomst", "Drive"),
            "mime_type": doc.get("mime_type"),
            "modified_at": doc.get("modified_at"),
            "ingested_at": now(),
        },
    )


def upsert_miro_note(conn: sqlite3.Connection, note: dict[str, Any]) -> None:
    """Idempotente insert/update van een Miro-note."""
    conn.execute(
        """
        INSERT INTO miro_notes (id, tekst, kleur, pre_classificatie, board_id, ingested_at)
        VALUES (:id, :tekst, :kleur, :pre_classificatie, :board_id, :ingested_at)
        ON CONFLICT(id) DO UPDATE SET
            tekst             = excluded.tekst,
            kleur             = excluded.kleur,
            pre_classificatie = excluded.pre_classificatie,
            ingested_at       = excluded.ingested_at
        """,
        {
            "id": note["miro_item_id"],
            "tekst": note["tekst"],
            "kleur": note.get("kleur"),
            "pre_classificatie": note.get("pre_classificatie"),
            "board_id": note.get("board_id"),
            "ingested_at": now(),
        },
    )


def upsert_clause_match(
    conn: sqlite3.Connection,
    doc_id: str,
    herkomst: str,
    clausule_id: str,
    norm: str,
    sub_punt: str = "",
) -> None:
    """Markeer dat een document een clausule raakt; sub_punt optioneel."""
    conn.execute(
        """
        INSERT OR IGNORE INTO clause_matches (doc_id, herkomst, clausule_id, norm, sub_punt)
        VALUES (?, ?, ?, ?, ?)
        """,
        (doc_id, herkomst, clausule_id, norm, sub_punt or ""),
    )


def log_ingest(conn: sqlite3.Connection, bron: str, folder_id: str | None, count: int) -> None:
    """Leg vast wanneer een bron voor het laatst is gesynchroniseerd."""
    conn.execute(
        """
        INSERT INTO ingest_log (bron, folder_id, bestand_count, last_run)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(bron) DO UPDATE SET
            folder_id     = excluded.folder_id,
            bestand_count = excluded.bestand_count,
            last_run      = excluded.last_run
        """,
        (bron, folder_id, count, now()),
    )
    conn.commit()


def bewaar_assistentvraag(
    conn: sqlite3.Connection,
    *,
    agent: str,
    record: dict[str, Any],
    storing: str | None = None,
    gesteld_door: str = "",
) -> int:
    """Leg één vraag met haar antwoord vast. Append-only; geeft het rij-id terug.

    Ook een storing wordt vastgelegd, met de reden en zonder antwoord. Weglaten maakt het
    overzicht schoner en het dossier onvolledig — een vraag die op een onverifieerbare
    verwijzing strandde is precies wat je later wil terugzien, en het is het enige spoor dat
    de controle heeft gewerkt.
    """
    cur = conn.execute(
        """
        INSERT INTO assistent_vragen (
            agent, vraag, antwoord, meegegeven_json, gebruikt_json, model, usd,
            prijzen_peildatum, prijzen_grondslag, storing, gesteld_door, gesteld_op
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            agent,
            str(record.get("vraag", "")),
            str(record.get("antwoord", "")),
            json.dumps(record.get("meegegeven", []), ensure_ascii=False),
            json.dumps(record.get("gebruikt", []), ensure_ascii=False),
            str(record.get("model", "")),
            float(record.get("usd", 0.0) or 0.0),
            str(record.get("peildatum", "")),
            str(record.get("grondslag", "")),
            storing,
            gesteld_door,
            now(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def fts_query(vraag: str) -> str:
    """Bouw een veilige FTS5-query uit vrije tekst: elk woord als geciteerde term.

    Eén implementatie voor alle drie de MATCH-plekken (`assistent/ophalen.py`,
    `api/landschap.py`, `zoek()` hieronder). Tot 2026-08-24 had elke plek zijn eigen aanpak
    en twee ervan waren stuk: de zoekbalk gaf de invoer onbewerkt door, en de assistent
    filterde tekens weg maar liet koppeltekens staan. `non-conformiteiten` gaf daardoor
    `sqlite3.OperationalError: no such column: conformiteiten` — een 500 op het kernwoord van
    een ISO-auditor.

    Aanhalingstekens maken van elk woord een letterlijke term, dus geen enkel FTS5-teken
    heeft nog betekenis. Dat dekt ook het stillere geval: `AND` of `NEAR` in een mensenvraag
    is een woord en geen operator, en ongeciteerd zoekt de query iets anders dan er staat.

    Woorden van minder dan drie tekens en losse cijferreeksen vallen weg; een lege uitkomst
    betekent "hier valt niet op te zoeken" en niet "geen resultaten".
    """
    woorden = [w for w in re.findall(r"[\w-]{3,}", vraag.lower()) if not w.isdigit()]
    # Een aanhalingsteken binnen een term verdubbelen is in FTS5 de ontsnapping — dezelfde
    # regel als in SQL-strings.
    return " OR ".join(f'"{w.replace(chr(34), chr(34) * 2)}"' for w in woorden)


def zoek(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    """Full-text search over document-namen en inhoud (FTS5)."""
    result: list[sqlite3.Row] = conn.execute(
        """
        SELECT d.id, d.naam, d.herkomst, d.mime_type,
               snippet(documents_fts, 1, '[', ']', '...', 20) AS fragment
        FROM documents_fts f
        JOIN documents d ON d.rowid = f.rowid
        WHERE documents_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()
    return result


def upsert_interview(
    conn: sqlite3.Connection,
    clausule_id: str,
    norm: str,
    bevinding: str,
    antwoord: str | None = None,
    notitie: str | None = None,
) -> None:
    """Idempotente insert/update van een handmatige interview-bevinding."""
    conn.execute(
        """
        INSERT INTO interviews (clausule_id, norm, bevinding, antwoord, notitie, interviewed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(clausule_id, norm) DO UPDATE SET
            bevinding      = excluded.bevinding,
            antwoord       = excluded.antwoord,
            notitie        = excluded.notitie,
            interviewed_at = excluded.interviewed_at
        """,
        (clausule_id, norm, bevinding, antwoord, notitie, now()),
    )


def laad_interviews(conn: sqlite3.Connection, norm: str | None = None) -> list[sqlite3.Row]:
    """Laad alle interviews, optioneel gefilterd op norm (`9001`/`27001`)."""
    if norm:
        result: list[sqlite3.Row] = conn.execute(
            "SELECT * FROM interviews WHERE norm = ? ORDER BY clausule_id",
            (norm,),
        ).fetchall()
        return result
    return conn.execute("SELECT * FROM interviews ORDER BY clausule_id").fetchall()


def now() -> str:
    """UTC-tijdstempel als ISO 8601-string (voor `*_at`-kolommen)."""
    return datetime.now(UTC).isoformat()


def _sha256(tekst: str) -> str:
    """Hex-digest van sha256 over `tekst`."""
    return hashlib.sha256(tekst.encode("utf-8")).hexdigest()


def log_classification(
    conn: sqlite3.Connection,
    audit_id: str,
    finding_id: str,
    system_prompt: str,
    user_prompt: str,
    model: str,
    raw_output: str | None,
    usage: dict[str, Any] | None = None,
    elapsed_s: float | None = None,
) -> None:
    """Persisteer een LLM-call vóór consumptie van de output (§2.6.4).

    Dedup-key: `(audit_id, finding_id, prompt_versie, model_versie)`.
    Reruns met dezelfde prompt-versie + model overschrijven niet — de
    classificatie blijft een append-only trace.

    De `system_prompt` bepaalt `prompt_versie` (sha256); de combinatie
    van `system_prompt + user_prompt` bepaalt `input_hash`.
    """
    prompt_versie = _sha256(system_prompt)
    input_hash = _sha256(system_prompt + "\n---\n" + user_prompt)
    conn.execute(
        """
        INSERT OR IGNORE INTO classifications
            (audit_id, finding_id, input_hash, prompt_versie, model_versie,
             raw_output, usage_json, elapsed_s, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            finding_id,
            input_hash,
            prompt_versie,
            model,
            raw_output,
            json.dumps(usage) if usage is not None else None,
            elapsed_s,
            now(),
        ),
    )


def laad_classifications(
    conn: sqlite3.Connection,
    audit_id: str | None = None,
    finding_id: str | None = None,
) -> list[sqlite3.Row]:
    """Laad classifications-rijen, optioneel gefilterd op audit/finding."""
    if audit_id and finding_id:
        return conn.execute(
            "SELECT * FROM classifications WHERE audit_id=? AND finding_id=? ORDER BY created_at",
            (audit_id, finding_id),
        ).fetchall()
    if audit_id:
        return conn.execute(
            "SELECT * FROM classifications WHERE audit_id=? ORDER BY created_at",
            (audit_id,),
        ).fetchall()
    if finding_id:
        return conn.execute(
            "SELECT * FROM classifications WHERE finding_id=? ORDER BY created_at",
            (finding_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM classifications ORDER BY created_at").fetchall()


# ---------------------------------------------------------------------------
# Decisions (§3.1.3) — append-only audit-trail van Mode-beslissingen
# ---------------------------------------------------------------------------


def schrijf_decision(
    conn: sqlite3.Connection,
    audit_id: str,
    punt: str,
    context: dict[str, Any],
    voorstel: dict[str, Any],
    risico: str,
    status: str,
    besluit: dict[str, Any] | None = None,
    notifier_naam: str | None = None,
    classificatie_id: int | None = None,
) -> int:
    """Schrijf een nieuwe rij naar `decisions` en retourneer de toegekende id.

    Status MOET `pending`, `resolved` of `cancelled` zijn. Bij `resolved`
    is `resolved_at` automatisch gevuld met `now()`.
    """
    if status not in ("pending", "resolved", "cancelled"):
        raise ValueError(
            f"decisions.status moet 'pending', 'resolved' of 'cancelled' zijn — kreeg {status!r}"
        )
    resolved_at = now() if status in ("resolved", "cancelled") else None
    cur = conn.execute(
        """
        INSERT INTO decisions
            (audit_id, punt, context_json, voorstel_json, status, besluit_json,
             risico, classificatie_id, notifier_naam, created_at, resolved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id,
            punt,
            json.dumps(context),
            json.dumps(voorstel),
            status,
            json.dumps(besluit) if besluit is not None else None,
            risico,
            classificatie_id,
            notifier_naam,
            now(),
            resolved_at,
        ),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def resolve_decision(
    conn: sqlite3.Connection,
    decision_id: int,
    besluit: dict[str, Any],
    status: str = "resolved",
) -> None:
    """Update een `pending` decision-rij met definitief besluit en `resolved_at`.

    Append-only-discipline: rijen met `status != "pending"` worden NOOIT
    overschreven; de update doet niets als de rij al resolved/cancelled is.
    """
    if status not in ("resolved", "cancelled"):
        raise ValueError(
            f"resolve_decision: status moet 'resolved' of 'cancelled' zijn — kreeg {status!r}"
        )
    conn.execute(
        """
        UPDATE decisions
        SET besluit_json = ?, status = ?, resolved_at = ?
        WHERE id = ? AND status = 'pending'
        """,
        (json.dumps(besluit), status, now(), decision_id),
    )
    conn.commit()


def laad_decision(conn: sqlite3.Connection, decision_id: int) -> sqlite3.Row | None:
    """Geef één decision-rij terug op id, of `None` als niet bestaat."""
    row: sqlite3.Row | None = conn.execute(
        "SELECT * FROM decisions WHERE id = ?", (decision_id,)
    ).fetchone()
    return row


def laad_pending_decisions(conn: sqlite3.Connection, audit_id: str) -> list[sqlite3.Row]:
    """Alle `status='pending'` rijen voor een audit-run (voor crash-recovery)."""
    return conn.execute(
        "SELECT * FROM decisions WHERE audit_id = ? AND status = 'pending' ORDER BY created_at",
        (audit_id,),
    ).fetchall()


def bewaar_review_advies(
    conn: sqlite3.Connection,
    *,
    norm: str,
    clausule: str,
    advies: str,
    kern: str,
    reden: str,
    voorgestelde_klasse: str | None = None,
    ernst: str | None = None,
    acties: list[dict[str, Any]] | None = None,
) -> None:
    """Leg het review-advies voor één clausule vast; een tweede run overschrijft.

    Overschrijven is hier geen verlies: het ruwe antwoord met tijdstempel, model en kosten staat
    in `assistent_vragen` en die is append-only. Deze tabel is de laatste stand waar de
    memo-bouwer op werkt.
    """
    conn.execute(
        """
        INSERT INTO review_adviezen
            (norm, clausule_id, advies, voorgestelde_klasse, ernst, kern, reden, acties_json,
             beoordeeld_op)
        VALUES (?,?,?,?,?,?,?,?,datetime('now'))
        ON CONFLICT(norm, clausule_id) DO UPDATE SET
            advies              = excluded.advies,
            voorgestelde_klasse = excluded.voorgestelde_klasse,
            ernst               = excluded.ernst,
            kern                = excluded.kern,
            reden               = excluded.reden,
            acties_json         = excluded.acties_json,
            beoordeeld_op       = excluded.beoordeeld_op
        """,
        (
            norm,
            clausule,
            advies,
            voorgestelde_klasse,
            ernst,
            kern,
            reden,
            json.dumps(acties or [], ensure_ascii=False),
        ),
    )
    conn.commit()


def review_adviezen(conn: sqlite3.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    """Alle review-adviezen, op (norm, clausule)."""
    # Expliciete kolommen en geen `SELECT *`: deze functie wordt ook aangeroepen op een
    # verbinding zonder `row_factory`, en dan is een rij een tuple. Op naam uitpakken maakt hem
    # onafhankelijk van hoe de verbinding is opgezet.
    uit: dict[tuple[str, str], dict[str, Any]] = {}
    rijen = conn.execute(
        "SELECT norm, clausule_id, advies, voorgestelde_klasse, ernst, kern, reden,"
        " acties_json, beoordeeld_op FROM review_adviezen"
    ).fetchall()
    for norm, clausule, advies, klasse, ernst, kern, reden, acties_json, op in rijen:
        uit[(str(norm), str(clausule))] = {
            "norm": str(norm),
            "clausule_id": str(clausule),
            "advies": str(advies),
            "voorgestelde_klasse": klasse,
            "ernst": ernst,
            "kern": str(kern or ""),
            "reden": str(reden or ""),
            "acties": json.loads(acties_json or "[]"),
            "beoordeeld_op": str(op),
        }
    return uit
