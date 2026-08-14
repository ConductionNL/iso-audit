"""Precedence, herkomst en de niet-onderhandelbare eigenschap dat geheimen niet lekken.

De matrix is het punt van deze test: per bron-combinatie moet niet alleen de *waarde*
kloppen maar ook de *herkomst*. Een loader die de juiste waarde teruggeeft met de verkeerde
bron is voor een audit even onbruikbaar als een verkeerde waarde.
"""

from __future__ import annotations

import itertools
import json
import logging
from pathlib import Path

import pytest

from iso_audit.config import herkomst as h
from iso_audit.config.settings import (
    API_KEY_ENV,
    SCHEMA_VERSIE,
    VELDEN,
    Waarde,
    load_config,
)

ALLE_ENV = tuple(v.env for v in VELDEN)


@pytest.fixture(autouse=True)
def _schone_omgeving(monkeypatch: pytest.MonkeyPatch) -> None:
    """Geen enkele env-var uit de echte omgeving mag deze tests beïnvloeden."""
    for naam in ALLE_ENV:
        monkeypatch.delenv(naam, raising=False)
    monkeypatch.delenv("ISO_AUDIT_CONFIG", raising=False)


def _schrijf_yaml(root: Path, inhoud: str) -> None:
    (root / "config.yaml").write_text(inhoud, encoding="utf-8")


# --- de matrix ------------------------------------------------------------


@pytest.mark.parametrize(
    ("in_env", "in_yaml", "in_ui"), list(itertools.product([False, True], repeat=3))
)
def test_precedence_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, in_env: bool, in_yaml: bool, in_ui: bool
) -> None:
    """Alle acht combinaties voor één niet-geheim veld, op waarde én herkomst."""
    if in_env:
        monkeypatch.setenv("JIRA_BASE_URL", "https://uit-env.example")
    if in_yaml:
        _schrijf_yaml(tmp_path, "jira:\n  base_url: https://uit-yaml.example\n")
    ui = {"JIRA_BASE_URL": "https://uit-ui.example"} if in_ui else {}

    w = load_config(root=tmp_path, ui_waarden=ui)["jira.base_url"]

    if in_env:
        assert (w.waarde, w.bron) == ("https://uit-env.example", "env")
    elif in_yaml:
        assert (w.waarde, w.bron) == ("https://uit-yaml.example", "yaml")
    elif in_ui:
        assert (w.waarde, w.bron) == ("https://uit-ui.example", "ui")
    else:
        assert (w.waarde, w.bron) == ("", "leeg")


def test_default_wint_alleen_als_niets_anders_er_is(tmp_path: Path) -> None:
    w = load_config(root=tmp_path)["anthropic.model"]
    assert (w.waarde, w.bron) == ("claude-haiku-4-5", "default")


def test_ui_verslaat_default(tmp_path: Path) -> None:
    """Anders kan een auditor het model niet wijzigen zonder het manifest aan te raken."""
    w = load_config(root=tmp_path, ui_waarden={"AUDIT_CLASSIFICATION_MODEL": "claude-opus-5"})[
        "anthropic.model"
    ]
    assert (w.waarde, w.bron) == ("claude-opus-5", "ui")


def test_lege_env_var_telt_niet_als_gezet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Een lege env-var is geen configuratie; anders blokkeert hij de lagere bronnen."""
    monkeypatch.setenv("JIRA_BASE_URL", "   ")
    w = load_config(root=tmp_path, ui_waarden={"JIRA_BASE_URL": "https://ui.example"})[
        "jira.base_url"
    ]
    assert (w.waarde, w.bron) == ("https://ui.example", "ui")


# --- naar_omgeving en de sso-val -----------------------------------------


def test_naar_omgeving_vult_de_adapters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """De adapters lezen env-vars; die moeten na het laden gevuld zijn."""
    load_config(root=tmp_path, ui_waarden={"MIRO_API_TOKEN": "t0k3n"}).naar_omgeving()
    import os

    assert os.environ["MIRO_API_TOKEN"] == "t0k3n"


def test_sso_verwijdert_een_lege_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """De val: de SDK laat óók een lege key voorgaan op het CLI-profiel."""
    monkeypatch.setenv(API_KEY_ENV, "")
    _schrijf_yaml(tmp_path, "anthropic:\n  auth_mode: sso\n")

    load_config(root=tmp_path).naar_omgeving()

    import os

    assert API_KEY_ENV not in os.environ


def test_sso_verwijdert_ook_een_gevulde_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(API_KEY_ENV, "sk-iets")
    _schrijf_yaml(tmp_path, "anthropic:\n  auth_mode: sso\n")

    load_config(root=tmp_path).naar_omgeving()

    import os

    assert API_KEY_ENV not in os.environ


def test_api_key_modus_laat_de_key_staan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(API_KEY_ENV, "sk-iets")
    load_config(root=tmp_path).naar_omgeving()

    import os

    assert os.environ[API_KEY_ENV] == "sk-iets"


# --- geheimen lekken niet -------------------------------------------------


def test_repr_van_een_geheim_toont_de_waarde_niet() -> None:
    w = Waarde("supergeheim", "env", geheim=True)
    for weergave in (repr(w), str(w), f"{w}", "{}".format(w)):  # noqa: UP032
        assert "supergeheim" not in weergave
        assert "env" in weergave, "de herkomst hoort wél zichtbaar te zijn"


def test_repr_van_een_gewone_waarde_toont_hem_wel() -> None:
    """Anders kun je niet-geheime configuratie niet debuggen."""
    assert "https://x.example" in repr(Waarde("https://x.example", "yaml"))


def test_geheim_in_een_stacktrace(tmp_path: Path) -> None:
    """Het scenario waar dit voor bedoeld is: een exception die het object meeneemt."""
    s = load_config(root=tmp_path, ui_waarden={"JIRA_API_TOKEN": "topsecret"})
    with pytest.raises(ValueError, match="<geheim>") as fout:
        raise ValueError(f"kapot: {s['jira.api_token']}")
    assert "topsecret" not in str(fout.value)


def test_overzicht_maskeert_geheimen(tmp_path: Path) -> None:
    s = load_config(root=tmp_path, ui_waarden={"JIRA_API_TOKEN": "abcdefgh1234"})
    rijen = {r["veld"]: r for r in h.overzicht(s)}

    token = rijen["jira.api_token"]
    assert token["ingesteld"] is True
    assert token["waarde"] == "••••••••1234"
    assert "abcdefgh1234" not in json.dumps(h.overzicht(s))


def test_masker_verraadt_de_lengte_niet() -> None:
    kort = h.masker("abcd1234")
    lang = h.masker("a" * 200 + "1234")
    assert kort.count("•") == lang.count("•")
    assert kort.endswith("1234") and lang.endswith("1234")


def test_herkomst_log_bevat_geen_waarden(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    s = load_config(root=tmp_path, ui_waarden={"JIRA_API_TOKEN": "topsecret"})
    with caplog.at_level(logging.INFO, logger="iso_audit.audit"):
        h.log_herkomst(s)

    tekst = "\n".join(r.getMessage() for r in caplog.records)
    assert "config_herkomst" in tekst
    assert '"veld": "jira.api_token"' in tekst
    assert '"bron": "ui"' in tekst
    assert "topsecret" not in tekst


# --- yaml-eigenaardigheden ------------------------------------------------


def test_secret_in_yaml_werkt_maar_waarschuwt(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Weigeren zou een derde partij blokkeren op een bestand dat hij zelf kan fixen."""
    _schrijf_yaml(tmp_path, "jira:\n  api_token: in-yaml\n")
    with caplog.at_level(logging.WARNING, logger="iso_audit.audit"):
        w = load_config(root=tmp_path)["jira.api_token"]

    assert (w.waarde, w.bron) == ("in-yaml", "yaml")
    assert "config_yaml_secret" in caplog.text
    assert "in-yaml" not in caplog.text, "de waarschuwing mag het geheim niet bevatten"


def test_kapotte_yaml_blokkeert_het_portaal_niet(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _schrijf_yaml(tmp_path, "jira: [dit: is: geen: geldige: yaml")
    with caplog.at_level(logging.WARNING, logger="iso_audit.audit"):
        s = load_config(root=tmp_path, ui_waarden={"JIRA_BASE_URL": "https://ui.example"})

    assert s["jira.base_url"].bron == "ui"
    assert "config_yaml_onleesbaar" in caplog.text


def test_nieuwere_schemaversie_meldt_en_start_door(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _schrijf_yaml(tmp_path, f"config_version: {SCHEMA_VERSIE + 5}\njira:\n  base_url: https://x\n")
    with caplog.at_level(logging.WARNING, logger="iso_audit.audit"):
        s = load_config(root=tmp_path)

    assert s.config_version == SCHEMA_VERSIE + 5
    assert s["jira.base_url"].waarde == "https://x"
    assert "config_schema_nieuwer" in caplog.text


def test_expliciet_config_pad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    elders = tmp_path / "elders.yaml"
    elders.write_text("jira:\n  base_url: https://elders\n", encoding="utf-8")
    monkeypatch.setenv("ISO_AUDIT_CONFIG", str(elders))

    assert load_config(root=tmp_path)["jira.base_url"].waarde == "https://elders"


def test_onbekend_veld_geeft_een_lege_waarde(tmp_path: Path) -> None:
    """Een tikfout in een sleutel mag geen KeyError worden in een draaiende run."""
    assert load_config(root=tmp_path)["bestaat.niet"].bron == "leeg"
