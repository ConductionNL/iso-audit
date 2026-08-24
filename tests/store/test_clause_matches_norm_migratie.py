"""`clause_matches` moet twee normen op hetzelfde nummer kunnen bewaren.

De primaire sleutel was `(doc_id, herkomst, clausule_id, sub_punt)` — zonder norm. Achttien
clausulenummers bestaan in beide normen (§5.1, §6.1, §7.5, §8.4 en zo verder), dus een document
dat zowel ISO 9001 §7.5 als ISO 27001 §7.5 raakt levert twee koppelingen op die onder die sleutel
op elkaar vallen. `INSERT OR IGNORE` gooit de tweede dan stil weg: geen fout, geen melding, één
koppeling minder.

Dat is de opslagkant van hetzelfde probleem dat `laad_clause_map("beide")` aan de laadkant heeft
(zie `tests/data/test_norm_db_export.py`). Beide gaan uit van "een clausule is een nummer", en
dat klopt niet over normen heen.

Deze tests dwingen de sleutel af én de migratie voor databases die de oude sleutel al hebben —
een `CREATE TABLE IF NOT EXISTS` verandert een bestaande tabel niet, dus zonder migratie zou de
fix alleen voor nieuwe databases gelden.
"""

from __future__ import annotations

import sqlite3

from iso_audit.store import initialiseer, upsert_clause_match

_OUDE_TABEL = """
CREATE TABLE clause_matches (
    doc_id      TEXT NOT NULL,
    herkomst    TEXT NOT NULL,
    clausule_id TEXT NOT NULL,
    norm        TEXT NOT NULL,
    sub_punt    TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (doc_id, herkomst, clausule_id, sub_punt)
);
"""


def _sleutelkolommen(conn: sqlite3.Connection) -> list[str]:
    """De kolommen die samen de primaire sleutel vormen, op volgorde."""
    rijen = conn.execute("PRAGMA table_info(clause_matches)").fetchall()
    return [naam for _, naam, _, _, _, pk in sorted(rijen, key=lambda r: r[5]) if pk]


def test_norm_zit_in_de_primaire_sleutel() -> None:
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    assert "norm" in _sleutelkolommen(conn)


def test_twee_normen_op_hetzelfde_nummer_passen_naast_elkaar() -> None:
    """Het geval waar het om gaat: §7.5 bestaat in beide normen en betekent iets anders."""
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)

    upsert_clause_match(conn, "doc-1", "Drive", "7.5", "9001")
    upsert_clause_match(conn, "doc-1", "Drive", "7.5", "27001")

    normen = sorted(
        r[0] for r in conn.execute("SELECT norm FROM clause_matches WHERE clausule_id = '7.5'")
    )
    assert normen == ["27001", "9001"], "de tweede koppeling is stil weggevallen"


def test_dezelfde_koppeling_twee_keer_blijft_een_rij() -> None:
    """De dedup blijft werken; alleen de norm is als onderscheid bijgekomen."""
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)

    upsert_clause_match(conn, "doc-1", "Drive", "7.5", "9001")
    upsert_clause_match(conn, "doc-1", "Drive", "7.5", "9001")

    assert conn.execute("SELECT COUNT(*) FROM clause_matches").fetchone()[0] == 1


def test_migratie_behoudt_elke_bestaande_rij() -> None:
    """Een bestaande database met de oude sleutel wordt omgebouwd zonder verlies."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(_OUDE_TABEL)
    rijen = [
        ("doc-1", "Drive", "5.1", "beide", ""),
        ("doc-1", "Drive", "8.24", "beide", ""),
        ("doc-2", "Nextcloud", "5.1", "9001", "a"),
    ]
    conn.executemany("INSERT INTO clause_matches VALUES (?, ?, ?, ?, ?)", rijen)
    conn.commit()

    initialiseer(conn)

    assert "norm" in _sleutelkolommen(conn)
    bewaard = sorted(conn.execute("SELECT * FROM clause_matches").fetchall())
    assert bewaard == sorted(rijen), "de migratie heeft rijen verloren of veranderd"


def test_migratie_is_idempotent() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(_OUDE_TABEL)
    conn.execute("INSERT INTO clause_matches VALUES ('d', 'Drive', '5.1', 'beide', '')")
    conn.commit()

    initialiseer(conn)
    initialiseer(conn)

    assert conn.execute("SELECT COUNT(*) FROM clause_matches").fetchone()[0] == 1
    assert "norm" in _sleutelkolommen(conn)


def test_migratie_werkt_met_een_openstaande_transactie() -> None:
    """`initialiseer` wordt overal aangeroepen, ook op een verbinding die al schrijft.

    De migratie gebruikt `executescript` met een eigen `BEGIN`/`COMMIT`. Zou er al een
    transactie openstaan, dan is dat een fout — en `initialiseer` staat in vrijwel elk pad, dus
    dat zou zich pas in productie laten zien.
    """
    conn = sqlite3.connect(":memory:")
    conn.executescript(_OUDE_TABEL)
    conn.execute("INSERT INTO clause_matches VALUES ('d', 'Drive', '5.1', 'beide', '')")
    # bewust niet committen: er staat nu een transactie open
    assert conn.in_transaction

    initialiseer(conn)

    assert "norm" in _sleutelkolommen(conn)
    assert conn.execute("SELECT COUNT(*) FROM clause_matches").fetchone()[0] == 1
