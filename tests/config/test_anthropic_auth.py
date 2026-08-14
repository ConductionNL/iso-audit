"""Tests voor de Anthropic-auth-wrapper, tegen een stub-CLI.

Er wordt hier bewust **geen** echte CLI aangeroepen: een testsuite die een OAuth-flow
tegen iemands account start en zijn profiel overschrijft is onacceptabel. De stub
imiteert het contract dat de wrapper aanneemt — een URL op stdout, dan een code op stdin —
zodat de wrapper te testen is zonder credentials.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from iso_audit.config import anthropic_auth as aa

STUB_OK = """#!/bin/sh
# Imiteert `ant`. Argumenten bepalen het gedrag.
case "$1 $2" in
  "auth status")
    if [ -n "$STUB_ACTIEF" ]; then echo "logged in"; exit 0; else echo "not logged in"; exit 1; fi ;;
  "auth login")
    echo "Open deze URL: https://console.example/authorize?code_challenge=xyz"
    read -r code
    [ "$code" = "goede-code" ] && exit 0 || exit 1 ;;
  "auth logout")
    [ -n "$STUB_LOGOUT_FAALT" ] && exit 1 || exit 0 ;;
esac
exit 2
"""

STUB_ZONDER_URL = """#!/bin/sh
echo "iets anders zonder url"
exit 0
"""


def _stub(tmp_path: Path, inhoud: str) -> str:
    pad = tmp_path / "ant-stub"
    pad.write_text(inhoud, encoding="utf-8")
    pad.chmod(pad.stat().st_mode | stat.S_IXUSR)
    return str(pad)


@pytest.fixture(autouse=True)
def _schoon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUB_ACTIEF", raising=False)
    monkeypatch.delenv("STUB_LOGOUT_FAALT", raising=False)
    aa._lopend.clear()


# --- status ---------------------------------------------------------------


def test_status_zonder_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Geen CLI = geen sso, met een leesbare reden die naar api_key wijst."""
    monkeypatch.setenv(aa.ANT_BIN_ENV, "/bestaat/niet/ant")
    uit = aa.status()
    assert uit["actief"] is False
    assert "API-key" in str(uit["reden"])


def test_status_niet_ingelogd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    assert aa.status() == {"actief": False, "reden": "Geen actieve Anthropic-sessie."}


def test_status_ingelogd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    monkeypatch.setenv("STUB_ACTIEF", "1")
    assert aa.status()["actief"] is True


# --- login ----------------------------------------------------------------


def test_login_geeft_een_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    sessie, url = aa.start_login()
    assert url.startswith("https://console.example/authorize")
    assert sessie in aa._lopend
    aa.voltooi_login(sessie, "goede-code")


def test_login_zonder_url_faalt_netjes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_ZONDER_URL))
    with pytest.raises(aa.AuthError, match="authorize-URL"):
        aa.start_login()
    assert not aa._lopend, "een mislukte start mag geen sessie achterlaten"


def test_verkeerde_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    sessie, _ = aa.start_login()
    with pytest.raises(aa.AuthError, match="niet geaccepteerd"):
        aa.voltooi_login(sessie, "foute-code")


def test_lege_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    sessie, _ = aa.start_login()
    with pytest.raises(aa.AuthError, match="geen code"):
        aa.voltooi_login(sessie, "   ")


def test_onbekende_sessie(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    with pytest.raises(aa.AuthError, match="verlopen of onbekend"):
        aa.voltooi_login("bestaat-niet", "goede-code")


def test_sessie_is_eenmalig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Een sessie-id mag niet twee keer bruikbaar zijn."""
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    sessie, _ = aa.start_login()
    aa.voltooi_login(sessie, "goede-code")
    with pytest.raises(aa.AuthError, match="verlopen of onbekend"):
        aa.voltooi_login(sessie, "goede-code")


def test_verlopen_login_wordt_geweigerd_en_opgeruimd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    sessie, _ = aa.start_login()
    aa._lopend[sessie].gestart -= aa.LOGIN_TIMEOUT * 2

    with pytest.raises(aa.AuthError, match="verlopen"):
        aa.voltooi_login(sessie, "goede-code")
    assert sessie not in aa._lopend


def test_een_nieuwe_login_ruimt_verlopen_sessies_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anders blijven processen hangen tot de pod herstart."""
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    oud, _ = aa.start_login()
    aa._lopend[oud].gestart -= aa.LOGIN_TIMEOUT * 2

    nieuw, _ = aa.start_login()
    assert oud not in aa._lopend
    assert nieuw in aa._lopend
    aa.voltooi_login(nieuw, "goede-code")


# --- uitloggen ------------------------------------------------------------


def test_uitloggen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    aa.uitloggen()


def test_uitloggen_faalt_netjes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(aa.ANT_BIN_ENV, _stub(tmp_path, STUB_OK))
    monkeypatch.setenv("STUB_LOGOUT_FAALT", "1")
    with pytest.raises(aa.AuthError, match="niet gelukt"):
        aa.uitloggen()


# --- de omgeving die de CLI meekrijgt -------------------------------------


def test_api_key_wordt_uit_de_cli_omgeving_gehaald(monkeypatch: pytest.MonkeyPatch) -> None:
    """Een gezette key laat de CLI die key gebruiken in plaats van het profiel."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-iets")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "tok")
    env = aa._omgeving()
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-iets", "de echte omgeving blijft intact"


def test_lege_api_key_wordt_ook_verwijderd(monkeypatch: pytest.MonkeyPatch) -> None:
    """De val: een lege string verslaat het profiel net zo goed als een gevulde."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert "ANTHROPIC_API_KEY" not in aa._omgeving()
