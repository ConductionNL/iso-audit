"""Impersonation is optioneel en mag de bestaande map-sharing niet stil vervangen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from iso_audit import auth


class _Creds:
    """Minimale dubbel: onthoudt of en namens wie er geïmpersoneerd is."""

    def __init__(self) -> None:
        self.subject: str | None = None

    def with_subject(self, subject: str) -> _Creds:
        nieuw = _Creds()
        nieuw.subject = subject
        return nieuw


@pytest.fixture
def _keyfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pad = tmp_path / "sa.json"
    pad.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(auth.CREDS_ENV_VAR, str(pad))

    def _fake(_file: str, scopes: list[str]) -> _Creds:
        return _Creds()

    monkeypatch.setattr(auth.service_account.Credentials, "from_service_account_file", _fake)
    return pad


def test_zonder_impersonate_geen_subject(_keyfile: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Leeg = map-sharing zoals het was; de bestaande opzet mag niet wijzigen."""
    monkeypatch.delenv(auth.IMPERSONATE_ENV_VAR, raising=False)
    creds: Any = auth._get_credentials(auth._READ_SCOPES)
    assert creds.subject is None


def test_met_impersonate_wel_subject(_keyfile: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auth.IMPERSONATE_ENV_VAR, "auditor@conduction.nl")
    creds: Any = auth._get_credentials(auth._READ_SCOPES)
    assert creds.subject == "auditor@conduction.nl"


def test_witruimte_telt_als_leeg(_keyfile: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Een veld dat per ongeluk een spatie bevat mag geen impersonation aanzetten."""
    monkeypatch.setenv(auth.IMPERSONATE_ENV_VAR, "   ")
    creds: Any = auth._get_credentials(auth._READ_SCOPES)
    assert creds.subject is None


def test_ontbrekend_keyfile_meldt_de_env_naam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(auth.CREDS_ENV_VAR, raising=False)
    with pytest.raises(OSError, match=auth.CREDS_ENV_VAR):
        auth._get_credentials(auth._READ_SCOPES)
