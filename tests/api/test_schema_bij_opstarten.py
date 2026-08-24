"""Het schema wordt bij het opstarten klaargezet, niet bij het eerste gebruik.

`initialiseer()` voert ook schema-migraties uit — sinds 2026-08-24 bouwt hij `clause_matches`
opnieuw op om `norm` in de primaire sleutel te krijgen. Die functie werd alleen aangeroepen
vanuit de assistent-route en vanuit de pipeline, dus een verse uitrol bleef op het oude schema
staan tot iemand toevallig een vraag stelde of een run startte.

Voor een migratie is dat de verkeerde plek: een tabel die halverwege een run wordt herbouwd, is
een verrassing tijdens werk dat twintig minuten duurt. Bij het opstarten is het zichtbaar, één
keer, en vóórdat er iemand mee werkt.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


def test_opstarten_migreert_het_schema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "audit.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE clause_matches (
            doc_id      TEXT NOT NULL,
            herkomst    TEXT NOT NULL,
            clausule_id TEXT NOT NULL,
            norm        TEXT NOT NULL,
            sub_punt    TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (doc_id, herkomst, clausule_id, sub_punt)
        );
        """
    )
    conn.execute("INSERT INTO clause_matches VALUES ('d', 'Drive', '5.1', 'beide', '')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("AUDIT_DB_PATH", str(db))

    from .conftest import maak_portaal

    maak_portaal(tmp_path)

    conn = sqlite3.connect(db)
    kolommen = conn.execute("PRAGMA table_info(clause_matches)").fetchall()
    sleutel = {naam for _, naam, _, _, _, pk in kolommen if pk}
    assert "norm" in sleutel, "het schema is niet gemigreerd bij het opstarten"
    assert conn.execute("SELECT COUNT(*) FROM clause_matches").fetchone()[0] == 1
