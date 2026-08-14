"""Elke kiesbare model MOET een prijsregel hebben.

Zonder deze test kan iemand een model aan de keuzelijst toevoegen en gaat een run
draaien met een kostenpost van nul. Dat ziet in een auditrapport compleet uit en is het
niet — erger dan helemaal geen kostenregel.
"""

from __future__ import annotations

import re

from iso_audit.classification.findings import (
    KIESBARE_MODELLEN,
    PRIJZEN,
    PRIJZEN_PEILDATUM,
)
from iso_audit.config.settings import VELDEN

TARIEF_SLEUTELS = {"input", "output", "cache_write_5m", "cache_read"}


def test_elk_kiesbaar_model_heeft_een_prijsregel() -> None:
    zonder = [m for m in KIESBARE_MODELLEN if m not in PRIJZEN]
    assert not zonder, f"kiesbaar zonder prijsregel: {zonder}"


def test_elke_prijsregel_is_compleet() -> None:
    for model, tarieven in PRIJZEN.items():
        assert set(tarieven) == TARIEF_SLEUTELS, f"{model} mist of heeft extra tarieven"
        assert all(v > 0 for v in tarieven.values()), f"{model} heeft een tarief <= 0"


def test_output_is_duurder_dan_input() -> None:
    """Sanity-check op een omgewisselde regel — dat is de fout die je niet ziet."""
    for model, t in PRIJZEN.items():
        assert t["output"] > t["input"], f"{model}: output goedkoper dan input?"


def test_cache_tarieven_volgen_de_standaardstructuur() -> None:
    """cache-write = 1.25x input, cache-read = 0.1x input."""
    for model, t in PRIJZEN.items():
        assert t["cache_write_5m"] == round(t["input"] * 1.25, 4), model
        assert t["cache_read"] == round(t["input"] * 0.10, 4), model


def test_haiku_prijs_is_de_gecorrigeerde() -> None:
    """Regressie op de fout die kostenregels ~25% te laag maakte."""
    assert PRIJZEN["claude-haiku-4-5"]["input"] == 1.00
    assert PRIJZEN["claude-haiku-4-5"]["output"] == 5.00


def test_alias_en_gedateerde_haiku_zijn_gelijk() -> None:
    """Historische runs staan op de gedateerde ID; die mag niet anders geprijsd zijn."""
    assert PRIJZEN["claude-haiku-4-5"] == PRIJZEN["claude-haiku-4-5-20251001"]


def test_peildatum_is_een_datum() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", PRIJZEN_PEILDATUM)


def test_default_model_uit_settings_is_kiesbaar() -> None:
    """De default mag niet buiten de keuzelijst vallen; dan kan de UI hem niet tonen."""
    default = next(v.default for v in VELDEN if v.sleutel == "anthropic.model")
    assert default in KIESBARE_MODELLEN
    assert default in PRIJZEN


# --- via de API -----------------------------------------------------------


def test_herkomst_endpoint(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Een auditor moet zonder cluster kunnen zien waar zijn configuratie vandaan komt."""
    from fastapi.testclient import TestClient

    from iso_audit.api.app import create_app
    from iso_audit.api.registry import AuditRegistry
    from tests.api.conftest import AUDITOR, EXAMPLES, NORMS

    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("JIRA_BASE_URL", "https://uit-env.example")
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    registry = AuditRegistry(tmp_path / "audits")
    registry.root.mkdir(parents=True)
    app = create_app(registry, profile=str(EXAMPLES / "conduction.profile.yaml"), norms_dir=NORMS)
    client = TestClient(app, headers={"X-Forwarded-Email": AUDITOR})

    client.post("/config/bronnen/jira", json={"velden": {"JIRA_API_TOKEN": "topsecret"}})
    body = client.get("/config/herkomst")
    assert body.status_code == 200
    velden = {r["veld"]: r for r in body.json()["velden"]}

    assert velden["jira.base_url"]["bron"] == "env", "env moet de UI verslaan"
    assert velden["jira.api_token"]["ingesteld"] is True
    assert velden["jira.api_token"]["waarde"].endswith("cret")
    assert "topsecret" not in body.text, "het volledige geheim mag er niet uit"
    assert body.json()["config_version"] >= 1
