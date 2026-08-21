"""Tests voor `iso_audit.api.run_job` — standaard-resolutie bij beide-runs."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from iso_audit.api.run_job import _bron_url, _resolve_standard
from iso_audit.memo.norm_lookup import laad_norm_db


def _db(tmp_path: Path):  # type: ignore[no-untyped-def]
    def _w(slug: str, clauses: list[str]) -> None:
        doc = {
            "metadata": {"standard": slug, "slug": slug},
            "clauses": {
                c: {"title_nl": c, "title_en": "", "text_nl": "t", "text_en": ""} for c in clauses
            },
        }
        (tmp_path / f"{slug}.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")

    _w("iso-9001-2015", ["6.2", "10.2"])
    _w("iso-27001-2022", ["8.16", "10.2"])  # 10.2 botst (in beide)
    return laad_norm_db(tmp_path)


def test_resolve_expliciete_norm() -> None:
    assert _resolve_standard("9001", "6.2", None) == "iso-9001-2015"
    assert _resolve_standard("27001", "8.16", None) == "iso-27001-2022"


def test_resolve_beide_alleen_27001(tmp_path: Path) -> None:
    assert _resolve_standard("beide", "8.16", _db(tmp_path)) == "iso-27001-2022"


def test_resolve_beide_alleen_9001(tmp_path: Path) -> None:
    assert _resolve_standard("beide", "6.2", _db(tmp_path)) == "iso-9001-2015"


def test_resolve_beide_botsing_default_9001(tmp_path: Path) -> None:
    # 10.2 zit in beide norm-DB's → default 9001 (bekende beperking).
    assert _resolve_standard("beide", "10.2", _db(tmp_path)) == "iso-9001-2015"


def test_resolve_beide_zonder_db_default() -> None:
    assert _resolve_standard("beide", "8.16", None) == "iso-9001-2015"


def test_has_clause(tmp_path: Path) -> None:
    db = _db(tmp_path)
    assert db.has_clause("iso-27001-2022", "8.16") is True
    assert db.has_clause("iso-9001-2015", "8.16") is False


# ---------- _bron_url: klikbare link per bron ----------


def test_bron_url_drive() -> None:
    assert _bron_url("Drive", "abc123") == "https://drive.google.com/open?id=abc123"


def test_bron_url_jira(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_BASE_URL", "https://co.atlassian.net")
    assert _bron_url("Jira", "ISO-7") == "https://co.atlassian.net/browse/ISO-7"


def test_bron_url_jira_zonder_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    # Zonder base-url geen betrouwbare link.
    assert _bron_url("Jira", "ISO-7") is None


def test_bron_url_onbekend_of_leeg() -> None:
    assert _bron_url("planning", "x") is None  # geen well-known vorm
    assert _bron_url("Drive", "") is None  # geen id → geen link


# --- de live-log is geen serverlog -----------------------------------------


def test_ruwe_leveranciersmelding_gaat_niet_naar_de_browser() -> None:
    """De live-log van een run wordt in de browser opgevraagd.

    De handler hangt aan de logger `iso_audit`, dus élke onderliggende regel kwam erin —
    inclusief de ruwe `verbinding_fout` met `detail`, en dat is precies de leveranciersrespons
    die `normaliseer` uit de client moet houden. Op 2026-08-14 is dit lekpad gesloten voor de
    bron-health en het run-record; de live-log was de derde weg en die stond nog open.
    """
    import logging

    from iso_audit.api.run_job import ALLEEN_SERVERLOG, _ProgressHandler
    from iso_audit.config.verbinding import normaliseer

    regels: list[str] = []
    handler = _ProgressHandler(regels.append)
    log = logging.getLogger("iso_audit")
    log.addHandler(handler)
    vorig = log.level
    log.setLevel(logging.INFO)
    try:
        log.info("Stap 5/7: Bevindingen classificeren")
        normaliseer(
            RuntimeError("401 from https://example.atlassian.net/rest/api/3/search?token=geheim"),
            bron="jira",
        )
    finally:
        log.removeHandler(handler)
        log.setLevel(vorig)

    assert regels == ["Stap 5/7: Bevindingen classificeren"]
    assert not any("geheim" in r for r in regels)
    assert ALLEEN_SERVERLOG == "alleen_serverlog"
