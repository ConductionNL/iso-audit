"""Elke kiesbare model MOET een prijsregel hebben.

Zonder deze test kan iemand een model aan de keuzelijst toevoegen en gaat een run
draaien met een kostenpost van nul. Dat ziet in een auditrapport compleet uit en is het
niet — erger dan helemaal geen kostenregel.
"""

from __future__ import annotations

import re

from iso_audit import modellen
from iso_audit.classification.findings import (
    KIESBARE_MODELLEN,
    PRIJZEN,
    PRIJZEN_GRONDSLAG,
    PRIJZEN_PEILDATUM,
    TIJDELIJK_TARIEF_TOT,
    prijs_voor,
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


def test_gedateerd_model_uit_de_trail_blijft_geprijsd() -> None:
    """Historische runs staan op de gedateerde ID en die records worden nooit herschreven.

    Tot 2026-08-20 stond dezelfde prijs twee keer in de tabel, één keer per spelling — twee
    regels die uit elkaar kunnen lopen. Nu herleidt `prijs_voor()` de gedateerde vorm naar
    zijn alias.
    """
    assert prijs_voor("claude-haiku-4-5-20251001") == PRIJZEN[modellen.HAIKU_4_5]


def test_onbekend_model_levert_geen_stille_nul() -> None:
    """`None` en niet een tarief van nul: de caller moet het verschil kunnen zien."""
    assert prijs_voor("claude-verzonnen-9") is None


def test_grondslag_is_een_van_de_twee_bekende_waarden() -> None:
    assert PRIJZEN_GRONDSLAG in {"lijstprijs", "werkelijk tarief"}


def test_werkelijk_tarief_volgt_de_sonnet_actie() -> None:
    """Op verzoek van de opdrachtgever (2026-08-20) rapporteert de tabel werkelijke tarieven.

    Sonnet 5 heeft t/m 2026-08-31 een introtarief van 2.00/10.00 in plaats van 3.00/15.00.
    """
    if PRIJZEN_GRONDSLAG != "werkelijk tarief":
        return
    assert PRIJZEN[modellen.SONNET_5]["input"] == 2.00
    assert PRIJZEN[modellen.SONNET_5]["output"] == 10.00
    assert TIJDELIJK_TARIEF_TOT[modellen.SONNET_5] == "2026-08-31"


def test_elk_tijdelijk_tarief_heeft_een_prijsregel_en_een_datum() -> None:
    for model, tot in TIJDELIJK_TARIEF_TOT.items():
        assert model in PRIJZEN, f"{model} heeft geen prijsregel"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", tot), f"{model}: {tot} is geen datum"


def test_verlopen_actietarief_wordt_gemeld(caplog: object, monkeypatch: object) -> None:
    """Een verlopen actietarief maakt elk bedrag te laag, en dat ziet compleet uit.

    Zonder deze melding vervalt de keuze voor werkelijke tarieven stil op 1 september.
    """
    import logging

    from iso_audit.classification import findings as f

    monkeypatch.setattr(f, "TIJDELIJK_TARIEF_TOT", {modellen.SONNET_5: "2020-01-01"})  # type: ignore[attr-defined]
    monkeypatch.setattr(f, "_TARIEF_GEWAARSCHUWD", set())  # type: ignore[attr-defined]
    with caplog.at_level(logging.WARNING, logger="iso_audit.classification.findings"):  # type: ignore[attr-defined]
        f.prijs_voor(modellen.SONNET_5)
    assert "verlopen" in "\n".join(caplog.messages)  # type: ignore[attr-defined]


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

    client.post("/instellingen/bronnen/jira", json={"velden": {"JIRA_API_TOKEN": "topsecret"}})
    body = client.get("/instellingen/herkomst")
    assert body.status_code == 200
    velden = {r["veld"]: r for r in body.json()["velden"]}

    assert velden["jira.base_url"]["bron"] == "env", "env moet de UI verslaan"
    assert velden["jira.api_token"]["ingesteld"] is True
    assert velden["jira.api_token"]["waarde"].endswith("cret")
    assert "topsecret" not in body.text, "het volledige geheim mag er niet uit"
    assert body.json()["config_version"] >= 1


# --- één plek voor de namen ------------------------------------------------


def test_geen_modelnaam_als_letterlijke_string_buiten_modellen_py() -> None:
    """Modelnamen staan in `iso_audit.modellen` en nergens anders als literal.

    Op 2026-08-20 stond dezelfde naam in vijf spellingen in `src/`: vier constanten op
    `claude-haiku-4-5-20251001` en één fallback op `claude-haiku-4-5`. Vijf plekken die uit
    elkaar kunnen lopen zonder dat iets faalt — een model bumpen was vijf greps, en één
    vergeten regel geeft geen foutmelding maar een run die stil op een ander model draait
    dan het rapport zegt. Deze test is de gate daarop.

    Alleen letterlijke strings; een modelnaam in een comment of docstring mag.
    """
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src" / "iso_audit"
    literal = re.compile(r"""["']claude-[a-z0-9.\-]+["']""")
    overtredingen: list[str] = []
    for pad in sorted(src.rglob("*.py")):
        if pad.name == "modellen.py":
            continue
        for nr, regel in enumerate(pad.read_text(encoding="utf-8").splitlines(), start=1):
            if literal.search(regel):
                overtredingen.append(f"{pad.relative_to(src)}:{nr}: {regel.strip()}")
    assert not overtredingen, "modelnaam hardcoded buiten iso_audit.modellen:\n" + "\n".join(
        overtredingen
    )


def test_standaard_en_kiesbaar_hangen_samen() -> None:
    """Het standaardmodel moet kiesbaar zijn, anders kan de UI zijn eigen default niet tonen."""
    assert modellen.STANDAARD in modellen.KIESBAAR
    assert modellen.STANDAARD in PRIJZEN


def test_gedateerde_vormen_wijzen_naar_een_kiesbaar_model() -> None:
    for gedateerd, alias in modellen.GEDATEERDE_VORM.items():
        assert alias in modellen.KIESBAAR, f"{gedateerd} -> {alias} is niet kiesbaar"
        assert modellen.normaliseer(gedateerd) == alias


def test_uit_omgeving_valt_terug_op_de_standaard(monkeypatch: object) -> None:
    monkeypatch.delenv(modellen.ENV_VAR, raising=False)  # type: ignore[attr-defined]
    assert modellen.uit_omgeving() == modellen.STANDAARD
    monkeypatch.setenv(modellen.ENV_VAR, modellen.OPUS_5)  # type: ignore[attr-defined]
    assert modellen.uit_omgeving() == modellen.OPUS_5
