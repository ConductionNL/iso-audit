"""Tests voor `iso_audit.pipeline` — orchestrator-CLI + helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from iso_audit import pipeline

# ---------- _is_ruis / _filter_ruis ----------


@pytest.mark.parametrize(
    "naam, verwacht",
    [
        ("Werkinstructie.docx", False),
        ("VERWIJDEREN_oude_doc.docx", True),
        ("TEMPLATE KOPIE MAKEN", True),
        ("OUD: notes", True),
        ("OUD policy", True),
        ("Oud: schemaatje", True),
        ("", False),
    ],
)
def test_is_ruis(naam: str, verwacht: bool) -> None:
    assert pipeline._is_ruis(naam) is verwacht


def test_filter_ruis_telt_skip() -> None:
    bev = [
        {"document_naam": "Goed.docx"},
        {"document_naam": "VERWIJDEREN_x"},
        {"document_naam": "OUD: y"},
    ]
    schoon, n = pipeline._filter_ruis(bev)
    assert n == 2
    assert len(schoon) == 1
    assert schoon[0]["document_naam"] == "Goed.docx"


def test_filter_ruis_leeg() -> None:
    schoon, n = pipeline._filter_ruis([])
    assert schoon == []
    assert n == 0


# ---------- _valideer_env ----------


def test_valideer_env_zonder_gws(monkeypatch: pytest.MonkeyPatch) -> None:
    """gws ontbreekt in PATH → sys.exit(1)."""
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: None)
    with pytest.raises(SystemExit) as exc:
        pipeline._valideer_env()
    assert exc.value.code == 1


def test_valideer_env_met_gws_geldig_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """gws aanwezig en token-geldig → geen exit, geen waarschuwing."""
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: "/usr/bin/gws")

    class _Result:
        stdout = '{"token_valid": true}'

    monkeypatch.setattr(
        pipeline.subprocess,
        "run",
        lambda *_args, **_kw: _Result(),
    )
    pipeline._valideer_env()  # Geen exception.


def test_valideer_env_token_invalid_geeft_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: "/usr/bin/gws")

    class _Result:
        stdout = '{"token_valid": false, "token_error": "expired"}'

    monkeypatch.setattr(pipeline.subprocess, "run", lambda *_a, **_kw: _Result())
    with caplog.at_level("WARNING"):
        pipeline._valideer_env()
    assert any("token niet geldig" in r.message for r in caplog.records)


def test_valideer_env_subprocess_falen_is_best_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Een subprocess-exception bij `gws auth status` is niet kritiek."""
    monkeypatch.setattr(pipeline.shutil, "which", lambda _: "/usr/bin/gws")

    def _raise(*_a: Any, **_kw: Any) -> Any:
        raise OSError("boom")

    monkeypatch.setattr(pipeline.subprocess, "run", _raise)
    pipeline._valideer_env()  # Geen exception.


# ---------- run_local_only ----------


def test_run_local_only_aanroept_lokale_rapport(tmp_path: Any) -> None:
    """Smoke test: lokale flow roept schrijf_rapport + csv + xlsx aan."""
    with (
        patch("iso_audit.reporting.local_report.schrijf_rapport") as mock_md,
        patch("iso_audit.reporting.tabular_report.schrijf_csv") as mock_csv,
        patch("iso_audit.reporting.tabular_report.schrijf_excel") as mock_xlsx,
    ):
        mock_md.return_value = str(tmp_path / "rapport.md")
        mock_csv.return_value = str(tmp_path / "rapport.csv")
        mock_xlsx.return_value = str(tmp_path / "rapport.xlsx")
        out = pipeline.run_local_only("9001")
    assert out == str(tmp_path / "rapport.md")
    mock_md.assert_called_once()
    mock_csv.assert_called_once()
    mock_xlsx.assert_called_once()


# ---------- main (dispatch) ----------


def test_main_local_only_route() -> None:
    with patch.object(pipeline, "run_local_only") as mock_local:
        pipeline.main(["--local-only", "--norm", "9001"])
    mock_local.assert_called_once_with("9001")


def test_main_setup_template_route() -> None:
    with (
        patch.object(pipeline, "_valideer_env") as mock_env,
        patch.object(pipeline, "run_setup_template") as mock_setup,
    ):
        pipeline.main(["--setup-template"])
    mock_env.assert_called_once()
    mock_setup.assert_called_once()


def test_main_report_only_route() -> None:
    with (
        patch.object(pipeline, "run_report_only") as mock_rep,
    ):
        pipeline.main(["--report-only", "--norm", "27001", "--scherpte", "0.5"])
    mock_rep.assert_called_once()
    _, kwargs = mock_rep.call_args
    assert kwargs["scherpte"] == 0.5


def test_main_default_route_naar_run_audit() -> None:
    with (
        patch.object(pipeline, "_valideer_env"),
        patch.object(pipeline, "run_audit") as mock_audit,
    ):
        pipeline.main(["--norm", "9001", "--no-review"])
    mock_audit.assert_called_once()
    args = mock_audit.call_args.kwargs
    assert args["no_review"] is True


def test_main_dry_run_cost_via_run_audit() -> None:
    """--dry-run-cost passeert via run_audit-pad."""
    with (
        patch.object(pipeline, "_valideer_env"),
        patch.object(pipeline, "run_audit") as mock_audit,
    ):
        pipeline.main(["--dry-run-cost", "--norm", "9001"])
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["dry_run_cost"] is True


# ---------- _converteer_md_naar_html_docx_pdf ----------


def test_converteer_md_html_falen_stopt_keten(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HTML-conversie faalt → DOCX/PDF worden niet geprobeerd."""
    with (
        patch("iso_audit.reporting.md_to_html.converteer", side_effect=OSError("nope")),
        patch("iso_audit.reporting.html_to_docx.converteer") as mock_docx,
        patch("iso_audit.reporting.html_to_pdf.converteer") as mock_pdf,
        caplog.at_level("WARNING"),
    ):
        pipeline._converteer_md_naar_html_docx_pdf("/tmp/x.md")
    mock_docx.assert_not_called()
    mock_pdf.assert_not_called()
    assert any("HTML-conversie mislukt" in r.message for r in caplog.records)


def test_converteer_md_html_ok_dan_docx_pdf() -> None:
    """HTML lukt → DOCX en PDF worden allebei geprobeerd."""
    with (
        patch("iso_audit.reporting.md_to_html.converteer", return_value="/tmp/x.html"),
        patch("iso_audit.reporting.html_to_docx.converteer", return_value="/tmp/x.docx"),
        patch("iso_audit.reporting.html_to_pdf.converteer", return_value="/tmp/x.pdf"),
    ):
        pipeline._converteer_md_naar_html_docx_pdf("/tmp/x.md")


# ---------- run_audit honoreert de geselecteerde bronnen ----------


def _jira_doc() -> dict[str, Any]:
    return {
        "naam": "AUD-1",
        "id": "AUD-1",
        "tekst": "backup beleid en directie review",
        "herkomst": "Jira",
        "mime_type": "issue",
        "modified_at": "2026-05-01T10:00:00Z",
    }


def test_run_audit_jira_levert_opvolgpunten_geen_documenten() -> None:
    """Jira gaat niet door de documentingest.

    Deze test verwachtte eerder `ingest_documenten("jira")`. Dat pad classificeerde elk
    ticket tegen elke clausule en leverde bevindingen als "dit ticket bewijst §4.1 niet" —
    ruis plus LLM-kosten per ticket. Een Jira-issue met een ISO-label is een openstaande
    verbeteractie, geen bewijsmateriaal; die gaat nu buiten de classificatie om.
    """
    from unittest.mock import MagicMock

    drive = MagicMock(return_value=([], []))
    docs = MagicMock(return_value=[_jira_doc()])
    punten = MagicMock(return_value=[])
    with (
        patch("iso_audit.sources.drive.haal_documenten_op", drive),
        patch("iso_audit.sources.protocol_ingest.ingest_documenten", docs),
        patch("iso_audit.sources.opvolgpunten.haal_op", punten),
        patch("iso_audit.miro.ingest.haal_notities_op") as miro,
        patch("iso_audit.classification.findings.schat_kosten", return_value={}),
    ):
        pipeline.run_audit("9001", dry_run_cost=True, sources=["jira"])
    drive.assert_not_called()
    miro.assert_not_called()
    docs.assert_not_called(), "Jira hoort niet als documentbron te worden ingelezen"
    assert punten.call_count == 1
    assert punten.call_args.args[0] == "jira"


def test_run_audit_default_bronnen_drive_en_miro() -> None:
    """sources=None → default Drive + Miro; geen protocol-ingest."""
    from unittest.mock import MagicMock

    drive = MagicMock(return_value=([], []))
    protocol = MagicMock(return_value=[])
    with (
        patch("iso_audit.sources.drive.haal_documenten_op", drive),
        patch("iso_audit.sources.protocol_ingest.ingest_documenten", protocol),
        patch("iso_audit.miro.ingest.haal_notities_op", return_value=[]) as miro,
        patch("iso_audit.classification.findings.schat_kosten", return_value={}),
    ):
        pipeline.run_audit("9001", dry_run_cost=True, sources=None)
    drive.assert_called_once()
    miro.assert_called_once()
    protocol.assert_not_called()  # drive+miro hebben eigen pad
