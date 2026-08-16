"""Tests voor `iso_audit.sources.planning` — PlanningSource + parsing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from iso_audit import store
from iso_audit.sources import planning
from iso_audit.sources.base import Document


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(planning.PLANNING_SHEETS_ID_ENV, raising=False)


# ---------- _norm_uit_tabnaam ----------


@pytest.mark.parametrize(
    "tab, norm",
    [
        ("9001:2015 2025", "9001"),
        ("ISO 27001 2026", "27001"),
        ("Auditplanning 2025", "beide"),
    ],
)
def test_norm_uit_tabnaam(tab: str, norm: str) -> None:
    assert planning._norm_uit_tabnaam(tab) == norm


# ---------- _jaar_uit_tabnaam ----------


def test_jaar_uit_tabnaam_laatste_match() -> None:
    """Bij meerdere jaren wint de laatste — '9001:2015 2025' → 2025."""
    assert planning._jaar_uit_tabnaam("9001:2015 2025") == 2025


def test_jaar_uit_tabnaam_zonder_jaar() -> None:
    assert planning._jaar_uit_tabnaam("Auditplanning") is None


# ---------- _normaliseer_clausule ----------


@pytest.mark.parametrize(
    "raw, verwacht",
    [
        ("4.4.1", "4.4"),
        ("5.1.2", "5.1"),
        ("4.1 Organisatiecontext", "4.1"),
        ("nope", None),
        ("", None),
    ],
)
def test_normaliseer_clausule(raw: str, verwacht: str | None) -> None:
    assert planning._normaliseer_clausule(raw) == verwacht


# ---------- _detecteer_maandkolommen ----------


def test_detecteer_maandkolommen() -> None:
    rijen = [
        ["Header A", "Header B"],
        ["", "Clausule", "januari", "februari", "maart"],
        ["", "4.1", "x", "", ""],
    ]
    idx, cols = planning._detecteer_maandkolommen(rijen)
    assert idx == 1
    assert cols == {2: "januari", 3: "februari", 4: "maart"}


def test_detecteer_maandkolommen_geen_match() -> None:
    rijen = [["Geen", "maand", "namen", "hier"]]
    idx, cols = planning._detecteer_maandkolommen(rijen)
    assert idx == -1
    assert cols == {}


# ---------- _parse_tab ----------


def test_parse_tab_basis() -> None:
    rijen = [
        ["", "", "", "", ""],
        ["", "Clausule", "januari", "februari", "Notitie"],
        ["", "4.1", "x", "", "Context analyse"],
        ["", "5.1", "", "x", "Leiderschap"],
    ]
    rows = planning._parse_tab("9001:2015 2025", rijen)
    assert len(rows) == 2
    assert rows[0].clausule_id == "4.1"
    assert rows[0].norm == "9001"
    assert rows[0].jaar == 2025
    assert rows[0].gepland_maanden == ["januari"]
    assert rows[0].status == "gepland"
    assert rows[0].kwartaal == "januari"


def test_parse_tab_zonder_planning_x() -> None:
    """Clausule zonder x-markering → status = 'open'."""
    rijen = [
        ["", "Clausule", "januari"],
        ["", "10.2", ""],
    ]
    rows = planning._parse_tab("27001 2026", rijen)
    assert rows[0].status == "open"
    assert rows[0].gepland_maanden == []


def test_parse_tab_leeg() -> None:
    assert planning._parse_tab("Tab", []) == []
    assert planning._parse_tab("Tab", [["alleen header"]]) == []


def test_parse_tab_zonder_maandkolom() -> None:
    rijen = [
        ["", "Clausule", "geen-maand-hier"],
        ["", "4.1", "x"],
    ]
    assert planning._parse_tab("Tab", rijen) == []


def test_parse_tab_skipt_ongeldige_clausule() -> None:
    rijen = [
        ["", "Clausule", "januari"],
        ["", "geen nummer", "x"],
        ["", "4.1", "x"],
    ]
    rows = planning._parse_tab("9001 2025", rijen)
    assert [r.clausule_id for r in rows] == ["4.1"]


# ---------- PlanningSource ----------


def test_planningsource_zonder_configuratie_is_leeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Geen terugval op een ingebakken spreadsheet-ID.

    Tot 2026-08-16 stond het ID van Conduction hier als default. Gemeten in het cluster:
    zonder configuratie meldde planning zich **groen met 7 tabs** op andermans sheet,
    terwijl Drive zich terecht als niet-gekoppeld meldde. Bij een derde partij wijst het
    portaal dan groen naar data van Conduction.
    """
    monkeypatch.delenv(planning.PLANNING_SHEETS_ID_ENV, raising=False)
    src = planning.PlanningSource()
    assert src.spreadsheet_id == ""


def test_planningsource_zonder_configuratie_meldt_niet_gekoppeld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Niet-gekoppeld is een eigen status, geen leveranciersfout en geen groen."""
    monkeypatch.delenv(planning.PLANNING_SHEETS_ID_ENV, raising=False)
    src = planning.PlanningSource()
    for hc in (src.probe(), src.healthcheck()):
        assert hc["status"] == "fail"
        assert hc["soort"] == "niet_geconfigureerd"
        assert "spreadsheet-ID" in str(hc["reden"])


def test_planningsource_zonder_configuratie_weigert_te_lezen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lezen zonder configuratie faalt zichtbaar in plaats van iets anders te lezen."""
    monkeypatch.delenv(planning.PLANNING_SHEETS_ID_ENV, raising=False)
    src = planning.PlanningSource()
    with pytest.raises(OSError, match=planning.PLANNING_SHEETS_ID_ENV):
        list(src.list_documents())


def test_planningsource_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(planning.PLANNING_SHEETS_ID_ENV, "env-sid")
    src = planning.PlanningSource()
    assert src.spreadsheet_id == "env-sid"


def test_planningsource_expliciete_id_wint() -> None:
    src = planning.PlanningSource(spreadsheet_id="custom-sid")
    assert src.spreadsheet_id == "custom-sid"


def test_planningsource_geregistreerd() -> None:
    from iso_audit.sources import available, get

    assert "planning" in available()
    assert get("planning") is planning.PlanningSource


def test_planningsource_list_documents() -> None:
    tabs = {
        "9001 2025": [
            ["", "Clausule", "januari", "februari", "Notitie"],
            ["", "4.1", "x", "", "Ctxt"],
        ]
    }
    src = planning.PlanningSource(spreadsheet_id="x")
    with patch.object(planning, "sheets_lees_alle_tabs", return_value=tabs):
        docs = list(src.list_documents())
    assert len(docs) == 1
    d = docs[0]
    assert d.bron == "planning"
    assert d.type == "audit-planning"
    assert d.id == "9001:4.1:2025"
    assert "4.1" in d.titel


def test_planningsource_fetch_content() -> None:
    tabs = {
        "9001 2025": [
            ["", "Clausule", "januari", "februari", "Notitie"],
            ["", "4.1", "x", "", "Context analyse"],
        ]
    }
    src = planning.PlanningSource(spreadsheet_id="x")
    doc = Document(
        id="9001:4.1:2025",
        titel="t",
        bron="planning",
        type="audit-planning",
        laatst_gewijzigd="",
        inhoud_uri="9001 2025",
    )
    with patch.object(planning, "sheets_lees_alle_tabs", return_value=tabs):
        content = src.fetch_content(doc)
    assert "Status: gepland" in content
    assert "januari" in content
    assert "Context analyse" in content


def test_planningsource_fetch_content_andere_bron() -> None:
    src = planning.PlanningSource(spreadsheet_id="x")
    doc = Document(
        id="x:y:z",
        titel="t",
        bron="drive",
        type="audit-planning",
        laatst_gewijzigd="",
        inhoud_uri="",
    )
    with pytest.raises(ValueError, match="PlanningSource"):
        src.fetch_content(doc)


def test_planningsource_fetch_content_ongeldige_id() -> None:
    src = planning.PlanningSource(spreadsheet_id="x")
    doc = Document(
        id="kapotte-id",
        titel="t",
        bron="planning",
        type="audit-planning",
        laatst_gewijzigd="",
        inhoud_uri="",
    )
    with pytest.raises(ValueError, match="Invalide PlanningSource"):
        src.fetch_content(doc)


def test_planningsource_list_findings_leeg() -> None:
    src = planning.PlanningSource(spreadsheet_id="x")
    assert list(src.list_findings("sessie-1")) == []


def test_planningsource_healthcheck_ok() -> None:
    src = planning.PlanningSource(spreadsheet_id="x")
    with patch.object(planning, "sheets_lees_alle_tabs", return_value={"t1": []}):
        h = src.healthcheck()
    assert h["status"] == "ok"
    assert h["aantal_tabs"] == 1


def test_planningsource_healthcheck_fail_lekt_de_ruwe_melding_niet() -> None:
    """Zoals bij DriveSource: de leveranciersmelding hoort in het serverlog.

    Deze test asserteerde eerder dat "auth fail" in `reden` stond. De echte melding hier
    was een volledige subprocess-dump met de commandoregel erin.
    """
    src = planning.PlanningSource(spreadsheet_id="x")
    with patch.object(planning, "sheets_lees_alle_tabs", side_effect=RuntimeError("auth fail")):
        h = src.healthcheck()
    assert h["status"] == "fail"
    assert h["soort"]
    assert "auth fail" not in str(h["reden"])


def test_planningsource_probe_leest_niet_alle_tabs() -> None:
    """De probe vraagt alleen de tabtitels; `healthcheck()` leest de inhoud."""
    src = planning.PlanningSource(spreadsheet_id="x")
    with (
        patch.object(planning, "sheets_tabnamen", return_value=["Tab1", "Tab2"]) as namen,
        patch.object(planning, "sheets_lees_alle_tabs") as alles,
    ):
        h = src.probe()
    assert h["status"] == "ok"
    assert h["aantal_tabs"] == 2
    assert namen.called
    assert not alles.called


# ---------- run (legacy CLI) ----------


@pytest.fixture
def db_pad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    pad = tmp_path / "audit.db"
    monkeypatch.setenv("AUDIT_DB_PATH", str(pad))
    return str(pad)


def test_run_droog_doet_geen_db_mutatie(db_pad: str, capsys: pytest.CaptureFixture[str]) -> None:
    tabs = {
        "9001 2025": [
            ["", "Clausule", "januari", "februari", "Notitie"],
            ["", "4.1", "x", "", "Ctxt"],
        ]
    }
    with patch.object(planning, "sheets_lees_alle_tabs", return_value=tabs):
        planning.run(droog=True, spreadsheet_id="x")
    out = capsys.readouterr().out
    assert "4.1" in out

    # DB is leeg.
    conn = store.verbinding(db_pad)
    try:
        rows = conn.execute("SELECT * FROM audit_planning").fetchall()
    except Exception:  # tabel mogelijk niet aangemaakt in dry-run? — controleer
        rows = []
    finally:
        conn.close()
    # In dry-run wordt _initialiseer_planning_tabel WEL aangeroepen (commit
    # gebeurt al daar), maar er worden geen rijen toegevoegd.
    assert rows == []


def test_run_persisteert_planning(db_pad: str) -> None:
    tabs = {
        "9001 2025": [
            ["", "Clausule", "januari", "februari", "Notitie"],
            ["", "4.1", "x", "", "Ctxt"],
            ["", "5.1", "", "x", "Leider"],
        ]
    }
    with patch.object(planning, "sheets_lees_alle_tabs", return_value=tabs):
        planning.run(droog=False, spreadsheet_id="x")

    conn = store.verbinding(db_pad)
    rows = conn.execute(
        "SELECT clausule_id, norm, jaar, kwartaal, status FROM audit_planning ORDER BY clausule_id"
    ).fetchall()
    conn.close()
    assert len(rows) == 2
    assert rows[0]["clausule_id"] == "4.1"
    assert rows[0]["norm"] == "9001"
    assert rows[0]["jaar"] == 2025
    assert rows[0]["kwartaal"] == "januari"
    assert rows[0]["status"] == "gepland"


# ---------- sheet-id validatie (config-grens) ----------

# Vorm van een echt Sheets-ID (44 tekens uit [A-Za-z0-9_-]), maar van niemand.
_SCHOON_SHEET_ID = "1AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVv"


def test_valideer_sheet_id_clean_geen_warning(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.WARNING):
        out = planning._valideer_sheet_id(_SCHOON_SHEET_ID)
    assert out == _SCHOON_SHEET_ID
    assert "misvormd" not in caplog.text


def test_valideer_sheet_id_waarschuwt_bij_misvorming(caplog: pytest.LogCaptureFixture) -> None:
    """Een .env-regel zonder newline plakt de volgende toewijzing aan de ID."""
    import logging

    kapot = "1BV2abcGOOGLE_SERVICE_ACCOUNT_FILE=audit/config/service_account.json"
    with caplog.at_level(logging.WARNING):
        out = planning._valideer_sheet_id(kapot)
    # Waarde wordt NIET aangepast (geen stille verkeerde-sheet-bug), wel gewaarschuwd.
    assert out == kapot
    assert "misvormd" in caplog.text
