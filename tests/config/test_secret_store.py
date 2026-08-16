"""De Secret-backend, en vooral: dat hij terugvalt in plaats van te breken.

Zonder terugval is het tool niet meer buiten dit cluster te draaien — en dat was juist de
reden om configuratie uit het cluster te halen.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from iso_audit.api.bron_config import BronConfig
from iso_audit.config import secret_store as ss


@pytest.fixture(autouse=True)
def _geen_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ss.SECRET_NAAM_ENV, raising=False)


def _nep_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doe alsof er een serviceaccount-token in de pod ligt."""
    token = tmp_path / "token"
    token.write_text("nep-token", encoding="utf-8")
    monkeypatch.setattr(ss, "_TOKEN", token)
    monkeypatch.setattr(ss, "_CA", tmp_path / "ca.crt")
    ns = tmp_path / "namespace"
    ns.write_text("iso-platform", encoding="utf-8")
    monkeypatch.setattr(ss, "_NS", ns)


# --- beschikbaarheid ------------------------------------------------------


def test_niet_beschikbaar_zonder_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _nep_token(tmp_path, monkeypatch)
    assert ss.beschikbaar() is False


def test_niet_beschikbaar_zonder_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lokaal draaien: env gezet maar geen pod eromheen."""
    monkeypatch.setenv(ss.SECRET_NAAM_ENV, "iso-audit-portal-config")
    monkeypatch.setattr(ss, "_TOKEN", Path("/bestaat/niet"))
    assert ss.beschikbaar() is False


def test_beschikbaar_met_beide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _nep_token(tmp_path, monkeypatch)
    monkeypatch.setenv(ss.SECRET_NAAM_ENV, "iso-audit-portal-config")
    assert ss.beschikbaar() is True


# --- lezen en schrijven ---------------------------------------------------


def test_lees_ontcijfert_de_sleutel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _nep_token(tmp_path, monkeypatch)
    monkeypatch.setenv(ss.SECRET_NAAM_ENV, "s")
    inhoud = json.dumps({"jira": {"JIRA_API_TOKEN": "t0k3n"}})
    monkeypatch.setattr(
        ss,
        "_api",
        lambda *_a, **_k: {
            "data": {ss._SLEUTEL: base64.b64encode(inhoud.encode()).decode("ascii")}
        },
    )
    assert ss.lees() == {"jira": {"JIRA_API_TOKEN": "t0k3n"}}


def test_leeg_secret_geeft_leeg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _nep_token(tmp_path, monkeypatch)
    monkeypatch.setenv(ss.SECRET_NAAM_ENV, "s")
    monkeypatch.setattr(ss, "_api", lambda *_a, **_k: {})
    assert ss.lees() == {}


def test_onleesbare_inhoud_geeft_leeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    _nep_token(tmp_path, monkeypatch)
    monkeypatch.setenv(ss.SECRET_NAAM_ENV, "s")
    monkeypatch.setattr(ss, "_api", lambda *_a, **_k: {"data": {ss._SLEUTEL: "geen-base64!!"}})
    with caplog.at_level(logging.WARNING, logger="iso_audit.audit"):
        assert ss.lees() == {}
    assert "secret_store_onleesbaar" in caplog.text


def test_schrijf_gebruikt_een_merge_patch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Merge-patch met één sleutel: andere sleutels van een beheerder blijven staan."""
    _nep_token(tmp_path, monkeypatch)
    monkeypatch.setenv(ss.SECRET_NAAM_ENV, "s")
    gezien: dict[str, object] = {}

    def _api(pad: str, *, methode: str = "GET", body: bytes | None = None) -> dict[str, object]:
        gezien.update({"pad": pad, "methode": methode, "body": body})
        return {}

    monkeypatch.setattr(ss, "_api", _api)
    ss.schrijf({"miro": {"MIRO_API_TOKEN": "x"}})

    assert gezien["methode"] == "PATCH"
    assert gezien["pad"] == "/api/v1/namespaces/iso-platform/secrets/s"
    patch = json.loads(str(gezien["body"], "utf-8"))  # type: ignore[arg-type]
    assert list(patch["data"]) == [ss._SLEUTEL], "alleen onze eigen sleutel aanraken"


# --- terugval -------------------------------------------------------------


def test_bron_config_valt_terug_op_de_pvc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Zonder werkende kube-API moet configureren blijven werken, met een waarschuwing."""
    import logging

    _nep_token(tmp_path, monkeypatch)
    monkeypatch.setenv(ss.SECRET_NAAM_ENV, "s")

    def _kapot(*_a: object, **_k: object) -> dict[str, object]:
        raise ss.SecretStoreError("kube-API niet bereikbaar.")

    monkeypatch.setattr(ss, "_api", _kapot)

    c = BronConfig(tmp_path)
    with caplog.at_level(logging.WARNING, logger="iso_audit.audit"):
        c.zet("miro", {"MIRO_API_TOKEN": "t0k3n"}, door="a@c.nl")

    assert "secret_store_terugval" in caplog.text
    assert c.pad.is_file(), "de PVC-terugval moet echt geschreven zijn"
    assert oct(c.pad.stat().st_mode)[-3:] == "600"
    assert c.ui_waarden()["MIRO_API_TOKEN"] == "t0k3n"


def test_zonder_secret_backend_gedraagt_alles_zich_als_voorheen(tmp_path: Path) -> None:
    """De bestaande PVC-route blijft de default; niets verandert lokaal.

    `omgeving={}` zegt expliciet dat er geen beheerderswaarden zijn. Zonder dat legt de
    store bij constructie `os.environ` vast — inclusief wat een eerdere test daar zette —
    en dan lijkt dit veld door een beheerder gezet.
    """
    c = BronConfig(tmp_path, omgeving={})
    c.zet("miro", {"MIRO_API_TOKEN": "t0k3n"}, door="a@c.nl")
    assert c.pad.is_file()
    assert BronConfig(tmp_path, omgeving={}).ui_waarden()["MIRO_API_TOKEN"] == "t0k3n"


def test_foutmelding_bevat_geen_responsbody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Een kube-API-fout kan het token in de body echoën; die mag niet doorgegeven worden."""
    _nep_token(tmp_path, monkeypatch)
    monkeypatch.setenv(ss.SECRET_NAAM_ENV, "s")

    class _Antwoord:
        status = 403

        def read(self) -> bytes:
            return b"Forbidden: nep-token geweigerd"

    class _Verbinding:
        def __init__(self, *_a: object, **_k: object) -> None: ...
        def request(self, *_a: object, **_k: object) -> None: ...
        def getresponse(self) -> _Antwoord:
            return _Antwoord()

        def close(self) -> None: ...

    monkeypatch.setattr(ss.http.client, "HTTPSConnection", _Verbinding)
    with pytest.raises(ss.SecretStoreError) as fout:
        ss.lees()
    assert "nep-token" not in str(fout.value)
    assert "403" in str(fout.value)


def test_verbinding_is_altijd_https() -> None:
    """Structureel, niet met een controle die iemand kan vergeten.

    Op de aanroep controleren en niet op de tekst: de docstring van `_api` legt juist uit
    waarom `urlopen` hier niet gebruikt wordt, en die uitleg mag de test niet omzeggen.
    """
    import inspect

    bron = inspect.getsource(ss._api)
    code = bron.split('"""', 2)[-1]  # docstring eraf
    assert "HTTPSConnection(" in code
    assert "urlopen(" not in code, "urlopen laat een string het schema bepalen"
    assert "http.client.HTTPConnection" not in code, "geen onversleutelde variant"
