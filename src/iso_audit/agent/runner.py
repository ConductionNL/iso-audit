"""De agentische lus, met afdwingbare grenzen en een volledige trail.

## Wat deze laag toevoegt

De vaste pipeline (`pipeline.py`) leest alle bronnen, classificeert, en stopt. Wat hij
niet kan: doorvragen. Een auditor die ziet dat een beleidsdocument naar een procedure
verwijst die niet in de auditmap staat, gaat die procedure zoeken. Dat is
patroondetectie — capability 2 uit `docs/explanation/missie.md`.

## Waarom max_iterations en niet task_budget

`task_budget` is **adviserend**: het model ziet een aftelling maar wordt niet gestopt.
`max_iterations` is afdwingbaar, en het kostenplafond hieronder ook. Voor een auditor is
"de lus stopte gegarandeerd na N rondes, en dat staat in de trail" bruikbaar; "het model
wist van een budget" niet. Daarom hier twee harde grenzen en geen adviserende.

## Waarom de join deterministisch blijft

De agent stelt bevindingen voor; `api/runs.py:dedup_sleutel` en `voeg_toe` bepalen wat
één bevinding is. Geen agent besluit dat twee bevindingen dezelfde zijn — dat moet een
auditor kunnen uitleggen.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from iso_audit.agent import tools as agent_tools
from iso_audit.classification.findings import PRIJZEN, PRIJZEN_PEILDATUM

_log = logging.getLogger("iso_audit.audit")

MAX_RONDES = 12
"""Harde bovengrens op de lus. Bewust laag: een audit die twaalf rondes niet genoeg
vindt, vraagt een mens, niet meer rondes."""

MAX_KOSTEN_USD = 2.00
"""Kostenplafond per run. Afdwingbaar: bij overschrijding stopt de lus en staat de reden
in de trail. Geen adviserend budget."""

PROMPT_VERSIE = "agent-v1"
"""Versie van de systeemprompt. Zonder dit is een oude run niet te reproduceren."""

SYSTEEMPROMPT = """Je bent een auditassistent. Je leest bronnen en stelt bevindingen voor.

Werkwijze:
1. Kijk eerst welke bronnen gekoppeld zijn.
2. Lees gericht. Een ontbrekende bron of een niet-vindbaar document is zelf een
   observatie voor de auditor — werk er niet omheen.
3. Volg verwijzingen. Verwijst een document naar een procedure die je niet aantreft, dan
   is dat het soort patroon waar je naar zoekt.

Regels:
- Elke bevinding verwijst naar een document- of ticket-id. Kun je dat niet, dan is het
  een vraag en geen bevinding; benoem hem dan als vraag in je eindantwoord.
- Je slaat niets op. Je stelt voor; een mens beslist.
- Verzin geen clausulenummers. Weet je de clausule niet, benoem dat.

Sluit af met een korte samenvatting: wat je hebt gelezen, wat je voorstelt, en waar je
twijfelt."""


@dataclass(slots=True)
class RunResultaat:
    """Wat een run oplevert. Bewust data, geen zijeffect."""

    kandidaten: list[dict[str, Any]] = field(default_factory=list)
    aanroepen: list[dict[str, Any]] = field(default_factory=list)
    rondes: int = 0
    kosten_usd: float = 0.0
    gestopt_door: str = "klaar"
    samenvatting: str = ""


def _kosten(model: str, in_tok: int, uit_tok: int) -> float:
    tarief = PRIJZEN.get(model)
    if tarief is None:
        # Geen prijsregel = we weten het niet. Nul teruggeven zou een run laten lijken
        # alsof hij gratis was; daarom loggen we het expliciet.
        _log.warning('{"event": "agent_model_zonder_prijs", "model": "%s"}', model)
        return 0.0
    return (in_tok / 1_000_000) * tarief["input"] + (uit_tok / 1_000_000) * tarief["output"]


def draai(
    *,
    audit_id: str,
    opdracht: str,
    model: str | None = None,
    max_rondes: int = MAX_RONDES,
    max_kosten_usd: float = MAX_KOSTEN_USD,
    client: Any | None = None,
) -> RunResultaat:
    """Draai één agentische ronde-reeks en geef het resultaat terug.

    Schrijft niets. De aanroeper voegt de kandidaten toe via de deterministische join en
    legt de trail vast — zo blijft deze functie testbaar zonder audit-directory.
    """
    import anthropic

    model = model or os.environ.get("AUDIT_CLASSIFICATION_MODEL") or "claude-haiku-4-5"
    ctx = agent_tools.RunContext(audit_id=audit_id)
    agent_tools.zet_context(ctx)
    resultaat = RunResultaat()

    try:
        runner = (client or anthropic.Anthropic()).beta.messages.tool_runner(
            model=model,
            max_tokens=8000,
            max_iterations=max_rondes,
            system=SYSTEEMPROMPT,
            tools=list(agent_tools.ALLE_TOOLS),
            messages=[{"role": "user", "content": opdracht}],
        )
        for bericht in runner:
            resultaat.rondes += 1
            gebruik = getattr(bericht, "usage", None)
            if gebruik is not None:
                resultaat.kosten_usd += _kosten(
                    model,
                    getattr(gebruik, "input_tokens", 0) or 0,
                    getattr(gebruik, "output_tokens", 0) or 0,
                )
            resultaat.samenvatting = _tekst(bericht) or resultaat.samenvatting

            if resultaat.kosten_usd > max_kosten_usd:
                resultaat.gestopt_door = "kostenplafond"
                break
            if resultaat.rondes >= max_rondes:
                resultaat.gestopt_door = "rondelimiet"
                break
    finally:
        resultaat.kandidaten = list(ctx.kandidaten)
        resultaat.aanroepen = list(ctx.aanroepen)
        agent_tools.zet_context(None)

    _log.info(
        json.dumps(
            {
                "event": "agent_run",
                "audit": audit_id,
                "model": model,
                "prompt_versie": PROMPT_VERSIE,
                "rondes": resultaat.rondes,
                "kandidaten": len(resultaat.kandidaten),
                "kosten_usd": round(resultaat.kosten_usd, 4),
                "prijzen_peildatum": PRIJZEN_PEILDATUM,
                "gestopt_door": resultaat.gestopt_door,
            },
            ensure_ascii=False,
        )
    )
    return resultaat


def _tekst(bericht: Any) -> str:
    blokken = getattr(bericht, "content", None) or []
    return "\n".join(
        getattr(b, "text", "") for b in blokken if getattr(b, "type", "") == "text"
    ).strip()


def trail_regels(resultaat: RunResultaat, *, model: str, audit_id: str) -> list[dict[str, Any]]:
    """Eén trail-regel per tool-aanroep, met model en prompt-versie.

    Dit is het punt waarop een agentische run auditbaar wordt in plaats van een zwarte
    doos: zonder deze regels kun je niet nagaan wélke bronnen zijn geraadpleegd om tot een
    bevinding te komen.
    """
    return [
        {
            **aanroep,
            "audit": audit_id,
            "agent": "auditassistent",
            "model": model,
            "prompt_versie": PROMPT_VERSIE,
        }
        for aanroep in resultaat.aanroepen
    ]


def voeg_toe_via_join(resultaat: RunResultaat, audit_dir: Path) -> tuple[int, int]:
    """Laat de deterministische join bepalen wat één bevinding is.

    Bewust een aparte functie: de agent stelt voor, deze stap beslist, en die scheiding
    moet in de code te zien zijn en niet alleen in een docstring.
    """
    from iso_audit.api.runs import voeg_toe

    return voeg_toe(audit_dir, resultaat.kandidaten)
