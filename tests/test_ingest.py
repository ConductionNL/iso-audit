"""Tests voor `iso_audit.ingest` — Drive + Miro DB-write paths."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from iso_audit import ingest

# ---------- beschikbare_bronnen ----------


def test_beschikbare_bronnen_bevat_drive() -> None:
    """`drive` is in de Source-registry → moet verschijnen."""
    bronnen = ingest.beschikbare_bronnen()
    assert "drive" in bronnen


def test_beschikbare_bronnen_bevat_miro() -> None:
    """Miro is pseudo-bron, moet altijd verschijnen."""
    bronnen = ingest.beschikbare_bronnen()
    assert "miro" in bronnen


def test_beschikbare_bronnen_gesorteerd() -> None:
    bronnen = ingest.beschikbare_bronnen()
    assert bronnen == sorted(bronnen)


# ---------- ingest_drive ----------


def _doc(idx: int, clausules: list[str], norm: str = "9001") -> dict[str, Any]:
    """Een gekoppeld document zoals `koppel_documenten` het teruggeeft.

    `clausule_normen` hoort erbij sinds 2026-08-24: een koppeling draagt de norm waaruit hij
    komt, want achttien clausulenummers bestaan in beide normen. Een helper die alleen
    `clausules` zet, laat een test slagen op een vorm die de echte functie niet produceert.
    """
    return {
        "id": f"d{idx}",
        "naam": f"Doc {idx}",
        "tekst": "tekst",
        "herkomst": "Drive",
        "mime_type": "text/plain",
        "clausule_normen": [(c, norm) for c in clausules],
        "clausules": clausules,
        "sub_punt_matches": [],
    }


@pytest.fixture()
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pad = tmp_path / "audit.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(pad))
    return pad


def test_ingest_drive_schrijft_documenten(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive-ingest schrijft documenten + clause_matches naar SQLite."""
    documenten = [_doc(1, ["4.1"]), _doc(2, [])]
    handmatige_review: list[dict[str, Any]] = []

    fake_clause_map = {
        "norm": "9001",
        "clausules": {"4.1": {"titel": "Context"}},
    }

    with (
        patch("iso_audit.sources.drive.haal_documenten_op") as mock_haal,
        patch(
            "iso_audit.classification.clause_mapping.laad_clause_map",
            return_value=fake_clause_map,
        ),
        patch(
            "iso_audit.classification.clause_mapping.koppel_documenten",
            return_value=([documenten[0]], [documenten[1]]),
        ),
    ):
        mock_haal.return_value = (documenten, handmatige_review)
        ingest.ingest_drive("9001")

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id FROM documents ORDER BY id").fetchall()
    assert [r[0] for r in rows] == ["d1", "d2"]
    matches = conn.execute(
        "SELECT doc_id, clausule_id FROM clause_matches WHERE herkomst = 'Drive'"
    ).fetchall()
    assert ("d1", "4.1") in matches
    conn.close()


def test_ingest_drive_met_handmatige_review(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Handmatige review-items worden als placeholder-document opgeslagen."""
    handmatige: list[dict[str, Any]] = [
        {"id": "h1", "naam": "Onleesbaar.pdf", "reden": "scan-only"}
    ]
    with (
        patch(
            "iso_audit.sources.drive.haal_documenten_op",
            return_value=([], handmatige),
        ),
        patch(
            "iso_audit.classification.clause_mapping.laad_clause_map",
            return_value={"norm": "9001", "clausules": {}},
        ),
        patch(
            "iso_audit.classification.clause_mapping.koppel_documenten",
            return_value=([], []),
        ),
    ):
        ingest.ingest_drive("9001")

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT tekst FROM documents WHERE id = 'h1'").fetchone()
    assert row is not None
    assert "Handmatige review vereist" in row[0]
    conn.close()


# ---------- ingest_miro ----------


def test_ingest_miro_zonder_board_id_skipt(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Zonder `MIRO_BOARD_ID` wordt Miro overgeslagen zonder error."""
    monkeypatch.delenv("MIRO_BOARD_ID", raising=False)
    ingest.ingest_miro("9001")
    # Geen DB-write — DB-bestand mag bestaan maar leeg zijn of niet bestaan.
    if db_path.is_file():
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        # Geen miro_notes-tabel aangemaakt.
        tabel_namen = [r[0] for r in rows]
        assert "miro_notes" not in tabel_namen
        conn.close()


def test_ingest_miro_schrijft_notities(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIRO_BOARD_ID", "B-123")
    notities = [
        {
            "miro_item_id": "n1",
            "tekst": "Notitie",
            "kleur": "green",
            "clausule": "4.1",
        }
    ]
    with (
        patch("iso_audit.miro.ingest.haal_notities_op", return_value=notities),
        patch("iso_audit.miro.ingest.koppel_aan_clausules", return_value=notities),
        patch(
            "iso_audit.classification.clause_mapping.laad_clause_map",
            return_value={"norm": "9001", "clausules": {}},
        ),
    ):
        ingest.ingest_miro("9001")

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id FROM miro_notes").fetchall()
    assert [r[0] for r in rows] == ["n1"]
    matches = conn.execute("SELECT doc_id FROM clause_matches WHERE herkomst = 'Miro'").fetchall()
    assert ("n1",) in matches
    conn.close()


# ---------- main ----------


def test_main_only_drive_skipt_miro(monkeypatch: pytest.MonkeyPatch) -> None:
    with (
        patch.object(ingest, "ingest_drive") as mock_drive,
        patch.object(ingest, "ingest_miro") as mock_miro,
    ):
        ingest.main(["--only", "drive", "--norm", "9001"])
    mock_drive.assert_called_once_with("9001")
    mock_miro.assert_not_called()


def test_main_only_miro_skipt_drive() -> None:
    with (
        patch.object(ingest, "ingest_drive") as mock_drive,
        patch.object(ingest, "ingest_miro") as mock_miro,
    ):
        ingest.main(["--only", "miro", "--norm", "27001"])
    mock_drive.assert_not_called()
    mock_miro.assert_called_once_with("27001")


def test_main_default_draait_beide() -> None:
    with (
        patch.object(ingest, "ingest_drive") as mock_drive,
        patch.object(ingest, "ingest_miro") as mock_miro,
    ):
        ingest.main(["--norm", "beide"])
    mock_drive.assert_called_once()
    mock_miro.assert_called_once()


def test_main_miro_exception_niet_kritiek() -> None:
    """Miro-falen mag de pipeline niet afbreken."""
    with (
        patch.object(ingest, "ingest_drive"),
        patch.object(ingest, "ingest_miro", side_effect=RuntimeError("api 500")),
    ):
        ingest.main([])  # Geen exception verwacht.


def test_main_only_kiest_valid_choice() -> None:
    """`--only` valideert tegen `beschikbare_bronnen()`."""
    with pytest.raises(SystemExit):
        ingest.main(["--only", "onbestaand"])
