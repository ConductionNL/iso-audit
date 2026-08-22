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


# --- één run per audit -----------------------------------------------------


def test_tweede_run_wordt_geweigerd_met_409(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Vier startknoppen binnen twintig seconden maakten vier threads in één proces.

    Die deelden één niet-thread-safe Google-client; het proces viel om met SIGSEGV. Los
    daarvan betalen vier gelijktijdige ingests viermaal de classificatie.
    """
    import json

    from iso_audit.api.session import AuditSession, RunLooptError

    (tmp_path / "findings.json").write_text(json.dumps([]), encoding="utf-8")
    sessie = AuditSession(
        tmp_path,
        profile="examples/auditmemo/conduction.profile.yaml",
        norms_dir="examples/norms",
        memo_input_path=tmp_path / "memo-input.yaml",
    )
    sessie._run.status = "running"

    with pytest.raises(RunLooptError, match="loopt al een run"):
        sessie.start_run(mode="live", norm="27001", sources=["drive"])


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


# --- opvolgpunten zijn bewijslast, geen triage-kandidaten -------------------


def test_opvolgpunten_komen_niet_in_de_triage_werklijst(tmp_path: Path) -> None:
    """Een openstaand punt uit Jira is al beoordeeld door degene die het aanmaakte.

    Wat het in een audit doet is aantonen dát er opvolging is — bewijslast, geen bevinding.
    Gemeten op 2026-08-22: van de 901 kandidaten in de eerste volledige run waren er 83 uit
    `Jira-opvolging`, elk met een triage-vraag die niemand kon beantwoorden.
    """
    from iso_audit.api.run_job import export_db_findings
    from iso_audit.store import initialiseer, now, verbinding

    conn = verbinding()
    initialiseer(conn)
    for doc_id, herkomst, klasse in (
        ("d1", "Drive", "NC"),
        ("ISO-709", "Jira-opvolging", "OFI"),
        ("ISO-710", "Miro-opvolging", "OFI"),
    ):
        conn.execute(
            """INSERT INTO bevindingen
               (doc_id, herkomst, clausule_id, norm, classificatie, beschrijving,
                document_naam, classified_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (doc_id, herkomst, "8.24", "27001", klasse, "beschrijving", doc_id, now()),
        )
    conn.commit()
    conn.close()

    uit = export_db_findings(norm="27001")

    assert [f.bronnen[0].doc_id for f in uit] == ["d1"], "alleen echt bewijs, geen opvolging"


def test_opvolgpunten_blijven_in_de_database_staan(tmp_path: Path) -> None:
    """Uitsluiten van de triage is niet hetzelfde als weggooien: ze zijn bewijslast.

    De vraagassistent leest ze als eigen soort bron, en een auditor moet kunnen aantonen dat
    er opvolging plaatsvond.
    """
    from iso_audit.store import initialiseer, now, verbinding

    conn = verbinding()
    initialiseer(conn)
    conn.execute(
        """INSERT INTO bevindingen
           (doc_id, herkomst, clausule_id, norm, classificatie, beschrijving,
            document_naam, classified_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("ISO-709", "Jira-opvolging", "8.24", "27001", "OFI", "x", "ISO-709", now()),
    )
    conn.commit()

    aantal = conn.execute(
        "SELECT COUNT(*) FROM bevindingen WHERE herkomst LIKE '%-opvolging'"
    ).fetchone()[0]
    conn.close()
    assert aantal == 1
