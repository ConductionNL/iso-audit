"""Tests voor `iso_audit.reporting.full_report` — DB-driven via fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from iso_audit import store
from iso_audit.reporting import full_report


@pytest.fixture
def db_pad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    pad = tmp_path / "audit.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(pad))
    conn = store.verbinding(str(pad))
    store.initialiseer(conn)
    conn.close()
    return str(pad)


# ---------- _drive_link ----------


def test_drive_link_doc() -> None:
    assert full_report._drive_link("x", "application/vnd.google-apps.document") == (
        "https://docs.google.com/document/d/x"
    )


def test_drive_link_sheet() -> None:
    assert full_report._drive_link("y", "application/vnd.google-apps.spreadsheet") == (
        "https://docs.google.com/spreadsheets/d/y"
    )


def test_drive_link_overig() -> None:
    assert full_report._drive_link("z", "application/pdf") == ("https://drive.google.com/file/d/z")
    assert full_report._drive_link("q", None) == "https://drive.google.com/file/d/q"


# ---------- _sorteersleutel ----------


def test_sorteersleutel_numeriek() -> None:
    """5.9 vóór 5.12 (in tegenstelling tot lexicografisch)."""
    items = ["A.5.12", "5.2", "A.5.9", "A.5.10"]
    items.sort(key=full_report._sorteersleutel)
    assert items == ["5.2", "A.5.9", "A.5.10", "A.5.12"]


def test_sorteersleutel_invalid_terugval() -> None:
    """Niet-numeriek part → tuple (0,)."""
    assert full_report._sorteersleutel("abc") == (0,)


# ---------- _laad_normteksten ----------


def test_laad_normteksten_9001() -> None:
    nt = full_report._laad_normteksten("9001")
    assert "4.1" in nt
    assert "normtekst" in nt["4.1"]


def test_laad_normteksten_27001() -> None:
    nt = full_report._laad_normteksten("27001")
    assert "A.6.5" in nt


def test_laad_normteksten_beide() -> None:
    nt = full_report._laad_normteksten("beide")
    assert "4.1" in nt  # 9001
    assert "A.6.5" in nt  # 27001


# ---------- _fetch_planning ----------


def test_fetch_planning_ontbrekende_tabel(db_pad: str) -> None:
    """`audit_planning`-tabel bestaat niet → lege dict, geen crash."""
    conn = store.verbinding(db_pad)
    planning = full_report._fetch_planning(conn, "9001")
    conn.close()
    assert planning == {}


# ---------- _fetch_bewijzen (scope-fallback) ----------


def test_fetch_bewijzen_zonder_scope_kolom(db_pad: str) -> None:
    """M-B store-schema heeft geen `documents.scope` → fallback-query."""
    conn = store.verbinding(db_pad)
    store.upsert_document(conn, {"id": "d1", "naam": "Beleid", "tekst": ""})
    store.upsert_clause_match(conn, "d1", "Drive", "10.2", "9001", "")
    conn.commit()
    rows = full_report._fetch_bewijzen(conn, "9001")
    conn.close()
    assert len(rows) == 1
    assert rows[0]["clausule_id"] == "10.2"


# ---------- genereer_rapport ----------


def test_genereer_rapport_basis(db_pad: str) -> None:
    md = full_report.genereer_rapport("9001")
    assert md.startswith("# Volledig Auditrapport")
    # Heeft een dekking-line.
    assert "Clausule-dekking" in md
    # Bevat ten minste één §-koptekst van 9001.
    assert "## 4.1 — " in md


def test_genereer_rapport_met_bewijs_en_link(db_pad: str) -> None:
    conn = store.verbinding(db_pad)
    store.upsert_document(
        conn,
        {
            "id": "doc-abc",
            "naam": "Beleidsdocument",
            "tekst": "",
            "mime_type": "application/vnd.google-apps.document",
        },
    )
    store.upsert_clause_match(conn, "doc-abc", "Drive", "10.2", "9001", "")
    conn.commit()
    conn.close()
    md = full_report.genereer_rapport("9001")
    assert "Beleidsdocument" in md
    assert "https://docs.google.com/document/d/doc-abc" in md


def test_genereer_rapport_zonder_bewijs(db_pad: str) -> None:
    md = full_report.genereer_rapport("9001")
    # Default = elk clausule "Gevonden bewijs: (geen)".
    assert "**Gevonden bewijs**: _(geen)_" in md


def test_genereer_rapport_met_interview(db_pad: str) -> None:
    conn = store.verbinding(db_pad)
    store.upsert_interview(conn, "10.2", "9001", "NC", "nee", "ontbreekt")
    conn.commit()
    conn.close()
    md = full_report.genereer_rapport("9001")
    assert "🔴 Non-conformiteit" in md
    assert "> ontbreekt" in md


# ---------- schrijf_rapport ----------


def test_schrijf_rapport_naar_eigen_dir(db_pad: str, tmp_path: Path) -> None:
    out = tmp_path / "rapporten"
    pad = full_report.schrijf_rapport("9001", output_dir=out)
    p = Path(pad)
    assert p.is_file()
    assert p.parent == out
    assert p.name.startswith("Auditrapport_volledig_9001")
    assert p.suffix == ".md"
