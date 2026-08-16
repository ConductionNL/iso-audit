"""Tests voor `iso_audit.cli` — subcommands + `--source` flag."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from iso_audit import cli

# ---------- --version / --help / geen subcommand ----------


def test_version_flag_print_versie(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "iso-audit" in out


def test_geen_subcommand_geeft_argparse_error() -> None:
    """argparse `required=True` op subparser → SystemExit(2)."""
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code == 2


# ---------- _resolve_sources ----------


def test_local_only_is_bereikbaar_vanaf_de_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bestond in de vorige repo en werkt nog via `python -m iso_audit.pipeline`, maar was
    bij de verhuizing niet doorgezet naar de `iso-audit`-CLI. De gedocumenteerde ingang
    kende de dry-run dus niet meer — een stille regressie in bereikbaarheid.

    Ook: `--source`/`--mode` zijn hier niet vereist, want dit pad leest geen enkele bron.
    """
    from iso_audit import pipeline

    gezien: dict[str, str] = {}

    def _nep(norm: str) -> str:
        gezien["norm"] = norm
        return "/pad/rapport.md"

    monkeypatch.setattr(pipeline, "run_local_only", _nep)
    assert cli.main(["pipeline", "--local-only", "--norm", "9001"]) == 0
    assert gezien["norm"] == "9001"


def test_resolve_sources_cli_eerst(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cli._SOURCE_ENV_VAR, "miro")
    out = cli._resolve_sources(["drive"])
    assert out == ["drive"]


def test_resolve_sources_env_fallback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(cli._SOURCE_ENV_VAR, "drive,miro")
    with caplog.at_level("INFO"):
        out = cli._resolve_sources(None)
    assert out == ["drive", "miro"]
    assert any("fallback naar" in r.message for r in caplog.records)


def test_resolve_sources_geen_input_exit_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(cli._SOURCE_ENV_VAR, raising=False)
    with pytest.raises(SystemExit) as exc:
        cli._resolve_sources(None)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "verplicht" in err


def test_resolve_sources_onbekend_exit_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(cli._SOURCE_ENV_VAR, raising=False)
    with pytest.raises(SystemExit) as exc:
        cli._resolve_sources(["bogus"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "onbekend" in err.lower()


def test_resolve_sources_multi_dedup_sort(monkeypatch: pytest.MonkeyPatch) -> None:
    out = cli._resolve_sources(["miro", "drive", "drive"])
    assert out == ["drive", "miro"]


# ---------- pipeline subcommand ----------


def test_pipeline_zonder_source_faalt(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(cli._SOURCE_ENV_VAR, raising=False)
    monkeypatch.delenv(cli._MODE_ENV_VAR, raising=False)
    with pytest.raises(SystemExit) as exc:
        cli.main(["pipeline", "--mode", "autonoom", "--norm", "9001"])
    assert exc.value.code == 2


def test_pipeline_report_only_zonder_source_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--report-only regenereert uit DB; --source/--mode niet vereist, run_audit niet aangeroepen."""
    monkeypatch.delenv(cli._SOURCE_ENV_VAR, raising=False)
    monkeypatch.delenv(cli._MODE_ENV_VAR, raising=False)
    with (
        patch("iso_audit.pipeline.run_report_only") as mock_report,
        patch("iso_audit.pipeline.run_audit") as mock_audit,
    ):
        rc = cli.main(["pipeline", "--report-only", "--norm", "9001"])
    assert rc == 0
    mock_report.assert_called_once()
    mock_audit.assert_not_called()


def test_pipeline_met_source_roept_run_audit_aan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(cli._SOURCE_ENV_VAR, raising=False)
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    with patch("iso_audit.pipeline.run_audit") as mock_audit:
        rc = cli.main(
            [
                "pipeline",
                "--source",
                "drive",
                "--norm",
                "9001",
                "--mode",
                "autonoom",
            ]
        )
    assert rc == 0
    mock_audit.assert_called_once()


def test_pipeline_env_source_fallback_werkt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(cli._SOURCE_ENV_VAR, "drive")
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    with patch("iso_audit.pipeline.run_audit") as mock_audit:
        cli.main(["pipeline", "--norm", "27001", "--mode", "autonoom"])
    mock_audit.assert_called_once()


def test_pipeline_no_review_flag_door_gegeven(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    with patch("iso_audit.pipeline.run_audit") as mock_audit:
        cli.main(
            [
                "pipeline",
                "--source",
                "drive",
                "--mode",
                "autonoom",
                "--no-review",
                "--rehash",
            ]
        )
    kw = mock_audit.call_args.kwargs
    assert kw["no_review"] is True
    assert kw["rehash"] is True


# ---------- doctor subcommand ----------


def test_doctor_zonder_gws_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    rc = cli.main(["doctor"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "[fail]" in out


def test_doctor_met_gws_en_creds_exit_0(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """gws aanwezig + alle notifier-creds gezet → exit 0."""
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/gws")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    monkeypatch.setenv("AUDIT_NOTIFIER_EMAIL", "a@b")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("SMTP_FROM", "f@b")
    rc = cli.main(["doctor"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[ok]" in out
    assert "Geregistreerde sources" in out
    assert "Geregistreerde notifiers" in out


def test_doctor_zonder_notifier_creds_exit_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """gws aanwezig maar geen notifier-creds → exit 1 (notifier healthcheck faalt)."""
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/gws")
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("AUDIT_NOTIFIER_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    rc = cli.main(["doctor"])
    assert rc == 1


# ---------- setup-template subcommand ----------


def test_setup_template_roept_pipeline_helpers_aan() -> None:
    with (
        patch("iso_audit.pipeline._valideer_env") as mock_env,
        patch("iso_audit.pipeline.run_setup_template") as mock_setup,
    ):
        rc = cli.main(["setup-template"])
    assert rc == 0
    mock_env.assert_called_once()
    mock_setup.assert_called_once()


# ---------- --mode / --notifier ----------


def test_resolve_mode_cli_eerst(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cli._MODE_ENV_VAR, "integer")
    assert cli._resolve_mode("autonoom") == "autonoom"


def test_resolve_mode_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cli._MODE_ENV_VAR, "integer")
    assert cli._resolve_mode(None) == "integer"


def test_resolve_mode_geen_input_exit_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(cli._MODE_ENV_VAR, raising=False)
    with pytest.raises(SystemExit) as exc:
        cli._resolve_mode(None)
    assert exc.value.code == 2


def test_resolve_mode_onbekende_env_exit_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(cli._MODE_ENV_VAR, "exotic")
    with pytest.raises(SystemExit) as exc:
        cli._resolve_mode(None)
    assert exc.value.code == 2


def test_resolve_notifier_autonoom_negeert(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """`--mode autonoom` met `--notifier slack` → warning, retourneert None."""
    with caplog.at_level("WARNING"):
        out = cli._resolve_notifier("slack", "autonoom")
    assert out is None
    assert any("ignored in autonoom" in r.message for r in caplog.records)


def test_resolve_notifier_integer_zonder_notifier_exit_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(cli._NOTIFIER_ENV_VAR, raising=False)
    with pytest.raises(SystemExit) as exc:
        cli._resolve_notifier(None, "integer")
    assert exc.value.code == 2


def test_resolve_notifier_integer_env_fallback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(cli._NOTIFIER_ENV_VAR, "slack")
    with caplog.at_level("INFO"):
        out = cli._resolve_notifier(None, "integer")
    assert out == "slack"


def test_resolve_notifier_onbekende_notifier_exit_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli._resolve_notifier("teams", "integer")
    assert exc.value.code == 2


def test_pipeline_zonder_mode_exit_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.delenv(cli._MODE_ENV_VAR, raising=False)
    with pytest.raises(SystemExit) as exc:
        cli.main(["pipeline", "--source", "drive", "--norm", "9001"])
    assert exc.value.code == 2


def test_pipeline_integer_zonder_notifier_exit_2(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.delenv(cli._NOTIFIER_ENV_VAR, raising=False)
    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "pipeline",
                "--source",
                "drive",
                "--norm",
                "9001",
                "--mode",
                "integer",
            ]
        )
    assert exc.value.code == 2


def test_pipeline_integer_met_notifier_construeert_mode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`--mode integer --notifier slack` bouwt IntegerMode met SlackNotifier."""
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    with patch("iso_audit.pipeline.run_audit") as mock_audit:
        cli.main(
            [
                "pipeline",
                "--source",
                "drive",
                "--norm",
                "9001",
                "--mode",
                "integer",
                "--notifier",
                "slack",
            ]
        )
    mock_audit.assert_called_once()
    mode_arg = mock_audit.call_args.kwargs["mode"]
    from iso_audit.modes.integer import IntegerMode

    assert isinstance(mode_arg, IntegerMode)


# ---------- __main__ delegatie ----------


def test_main_module_delegeert(monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m iso_audit` importeert __main__ en roept cli.main aan."""
    from iso_audit import __main__ as iso_main

    assert iso_main.main is cli.main
