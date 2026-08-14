"""De grenzen van de agentische lus, en dat de join deterministisch blijft.

Wat hier bewaakt wordt is niet of het model iets zinnigs zegt — dat is niet testbaar —
maar dat de lus **gegarandeerd stopt**, dat geen tool schrijft, en dat de agent niet zelf
bepaalt wat één bevinding is.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from iso_audit.agent import runner, tools


def _functie(tool: Any) -> Any:
    """De onderliggende functie van een `@beta_tool`.

    De decorator levert een `BetaFunctionTool` met de functie op `.func`; die willen we
    voor bronanalyse en om een tool los aan te roepen zonder de SDK-laag ertussen.
    """
    return getattr(tool, "func", tool)


class _Bericht:
    """Minimaal bericht zoals de tool-runner het teruggeeft."""

    def __init__(self, tekst: str = "klaar", in_tok: int = 1000, uit_tok: int = 100) -> None:
        self.content = [type("B", (), {"type": "text", "text": tekst})()]
        self.usage = type("U", (), {"input_tokens": in_tok, "output_tokens": uit_tok})()


class _Runner:
    """Doet alsof het model eindeloos doorgaat, zodat de grenzen getest worden."""

    def __init__(self, aantal: int = 1000, in_tok: int = 1000) -> None:
        self._aantal = aantal
        self._in_tok = in_tok

    def __iter__(self) -> Any:
        for _ in range(self._aantal):
            yield _Bericht(in_tok=self._in_tok)


class _Client:
    def __init__(self, runner_obj: _Runner) -> None:
        self._r = runner_obj

    @property
    def beta(self) -> Any:
        buiten = self

        class _M:
            def tool_runner(self, **_kw: Any) -> Any:
                return buiten._r

        return type("B", (), {"messages": _M()})()


# --- de lus stopt ---------------------------------------------------------


def test_rondelimiet_stopt_de_lus() -> None:
    """Een model dat blijft doorgaan mag geen oneindige run opleveren."""
    uit = runner.draai(
        audit_id="9001-2026-Q3",
        opdracht="lees alles",
        model="claude-haiku-4-5",
        max_rondes=3,
        client=_Client(_Runner(aantal=1000)),
    )
    assert uit.rondes == 3
    assert uit.gestopt_door == "rondelimiet"


def test_kostenplafond_stopt_de_lus() -> None:
    """Afdwingbaar, niet adviserend: bij overschrijding stopt hij echt."""
    uit = runner.draai(
        audit_id="9001-2026-Q3",
        opdracht="lees alles",
        model="claude-haiku-4-5",
        max_rondes=100,
        max_kosten_usd=0.002,  # ~2 rondes à 1000 input-tokens
        client=_Client(_Runner(aantal=100, in_tok=1_000_000)),
    )
    assert uit.gestopt_door == "kostenplafond"
    assert uit.rondes < 100


def test_reden_van_stoppen_staat_in_de_log(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.INFO, logger="iso_audit.audit"):
        runner.draai(
            audit_id="a-1",
            opdracht="x",
            model="claude-haiku-4-5",
            max_rondes=2,
            client=_Client(_Runner(aantal=50)),
        )
    regel = next(r.getMessage() for r in caplog.records if "agent_run" in r.getMessage())
    data = json.loads(regel)
    assert data["gestopt_door"] == "rondelimiet"
    assert data["prompt_versie"] == runner.PROMPT_VERSIE
    assert data["model"] == "claude-haiku-4-5"
    assert data["prijzen_peildatum"]


def test_model_zonder_prijs_wordt_gemeld(caplog: pytest.LogCaptureFixture) -> None:
    """Stil nul kosten rapporteren zou een run gratis laten lijken."""
    import logging

    with caplog.at_level(logging.WARNING, logger="iso_audit.audit"):
        uit = runner.draai(
            audit_id="a-1",
            opdracht="x",
            model="verzonnen-model",
            max_rondes=1,
            client=_Client(_Runner(aantal=5)),
        )
    assert uit.kosten_usd == 0.0
    assert "agent_model_zonder_prijs" in caplog.text


def test_context_wordt_altijd_opgeruimd() -> None:
    """Ook als de lus klapt, mag er geen context blijven hangen voor de volgende run."""

    class _Klapt:
        def __iter__(self) -> Any:
            raise RuntimeError("stuk")
            yield  # pragma: no cover

    with pytest.raises(RuntimeError, match="stuk"):
        runner.draai(
            audit_id="a-1", opdracht="x", model="claude-haiku-4-5", client=_Client(_Klapt())
        )
    assert tools._context is None


# --- geen tool schrijft --------------------------------------------------


def test_geen_tool_raakt_de_trail_of_de_database() -> None:
    """De trail is van de coordinator. Een tool die hem schrijft, ondermijnt de join."""
    verboden = ("findings.json", "runs.jsonl", "triage_log", "sqlite", "store", "voeg_toe")
    for tool in tools.ALLE_TOOLS:
        bron = inspect.getsource(_functie(tool))
        for term in verboden:
            assert term not in bron, f"{tool} raakt {term}"


def test_geen_tool_opent_een_bestand_voor_schrijven() -> None:
    for tool in tools.ALLE_TOOLS:
        bron = inspect.getsource(_functie(tool))
        for term in ("open(", "write_text", "mkdir", '"w"', "'w'"):
            assert term not in bron, f"{tool} schrijft ({term})"


def test_bevinding_zonder_bewijs_wordt_geweigerd() -> None:
    """Geen claim zonder bron — dat is de auditor-spiegel, geen stijlvoorkeur."""
    ctx = tools.RunContext(audit_id="a-1")
    tools.zet_context(ctx)
    try:
        func = _functie(tools.stel_bevinding_voor)
        uit = func(
            standard="iso-9001-2015",
            clause="10.2",
            titel="x",
            onderbouwing="y",
            bron="drive",
            bewijs_id="   ",
        )
        assert "Geweigerd" in uit
        assert ctx.kandidaten == []
    finally:
        tools.zet_context(None)


def test_bevinding_met_bewijs_wordt_voorgesteld_maar_niet_opgeslagen() -> None:
    ctx = tools.RunContext(audit_id="a-1")
    tools.zet_context(ctx)
    try:
        func = _functie(tools.stel_bevinding_voor)
        uit = func(
            standard="iso-9001-2015",
            clause="10.2",
            titel="Procedure ontbreekt",
            onderbouwing="Beleid verwijst naar P-12, niet aangetroffen.",
            bron="drive",
            bewijs_id="doc-42",
        )
        assert "Niet opgeslagen" in uit
        assert len(ctx.kandidaten) == 1
        assert ctx.kandidaten[0]["bewijs_id"] == "doc-42"
    finally:
        tools.zet_context(None)


def test_tool_zonder_context_faalt_luid() -> None:
    """Stil doorgaan zonder context zou kandidaten laten verdwijnen."""
    tools.zet_context(None)
    func = _functie(tools.lijst_bronnen)
    with pytest.raises(RuntimeError, match="run-context"):
        func()


# --- de join blijft deterministisch --------------------------------------


def test_join_bepaalt_wat_een_bevinding_is(tmp_path: Path) -> None:
    """De agent stelt twee bijna-identieke bevindingen voor; de join maakt er één van."""
    uit = runner.RunResultaat(
        kandidaten=[
            {
                "standard": "iso-9001-2015",
                "clause": "10.2",
                "source": "drive",
                "title": "Procedure ontbreekt",
                "description": "a",
            },
            {
                "standard": "iso-9001-2015",
                "clause": "10.2",
                "source": "drive",
                "title": "procedure   ONTBREEKT",
                "description": "b",
            },
        ]
    )
    (tmp_path / "findings.json").write_text("[]", encoding="utf-8")
    toegevoegd, overgeslagen = runner.voeg_toe_via_join(uit, tmp_path)

    assert (toegevoegd, overgeslagen) == (1, 1), "de deterministische dedup moet dit samenvoegen"


def test_trail_regels_zijn_compleet() -> None:
    """Zonder agent, model en prompt-versie is een run niet te reproduceren."""
    uit = runner.RunResultaat(
        aanroepen=[{"tool": "lijst_documenten", "bron": "drive", "aantal": 3}]
    )
    (regel,) = runner.trail_regels(uit, model="claude-haiku-4-5", audit_id="9001-2026-Q3")
    for veld in ("tool", "audit", "agent", "model", "prompt_versie"):
        assert regel.get(veld), f"{veld} ontbreekt of is leeg"
