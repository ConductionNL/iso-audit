"""Elke Claude-modelnaam in dit project, op één plek.

## Waarom deze module bestaat

Op 2026-08-20 stond dezelfde modelnaam in vijf verschillende spellingen in `src/`:
`classification/llm.py`, `classification/thema.py`, `memo/draft.py` en
`reporting/report_generation.py` hadden elk hun eigen constante op
`claude-haiku-4-5-20251001`, en `agent/runner.py` viel terug op `claude-haiku-4-5` —
dezelfde model, andere string. Vijf plekken die uit elkaar kunnen lopen zonder dat
iets faalt: een model bumpen betekende vijf greps, en één vergeten regel geeft geen
foutmelding maar een run die stil op een ander model draait dan het rapport zegt.

Eén tabel met namen, en elders alleen verwijzingen. Dat is het hele idee.

## Alias versus gedateerde vorm

De API accepteert beide vormen: `claude-haiku-4-5` (alias, wijst altijd naar de
nieuwste versie van dat model) en `claude-haiku-4-5-20251001` (vastgezet op één
versie). In de audit-trail staan historische runs op de gedateerde vorm; die records
worden nooit herschreven, dus de gedateerde namen moeten opzoekbaar blijven. Vandaar
`GEDATEERDE_VORM`: nieuwe runs gebruiken de alias, oude records blijven leesbaar.

Voor een auditwerktuig is de alias niet vanzelfsprekend de juiste keuze — hij beweegt
onder je handen als Anthropic het model bijwerkt. Dat is bewust geaccepteerd: het
`model_versie`-veld in `classifications` legt per classificatie vast welke string is
gebruikt, en de `usage_json` erbij maakt het bedrag navertelbaar. Wil je een run
reproduceerbaar vastzetten, kies dan expliciet een gedateerde vorm via
`AUDIT_CLASSIFICATION_MODEL`.
"""

from __future__ import annotations

import os

HAIKU_4_5 = "claude-haiku-4-5"
SONNET_5 = "claude-sonnet-5"
OPUS_5 = "claude-opus-5"

STANDAARD = HAIKU_4_5
"""Het model voor alles wat de auditor niet zelf kiest: memo-tekst, thema-bepaling en
de rapportgeneratie. Bewust het goedkoopste: die drie paden schrijven tekst op basis
van al-geclassificeerde bevindingen en vellen geen oordeel over bewijs."""

KIESBAAR: tuple[str, ...] = (HAIKU_4_5, SONNET_5, OPUS_5)
"""Wat een auditor in de UI kan kiezen voor de **classificatie**, van goedkoop naar
duur. Elk model hier MOET een prijsregel hebben in `classification/findings.py`;
`tests/config/test_modelkeuze.py` faalt anders. Zonder die test kan een nieuw model
stil zonder kostenrapportage gaan lopen."""

GEDATEERDE_VORM: dict[str, str] = {
    "claude-haiku-4-5-20251001": HAIKU_4_5,
}
"""Gedateerde model-ID's die in historische records staan, met hun alias erbij. Alleen
voor opzoeken — nieuwe runs gebruiken de alias."""

ENV_VAR = "AUDIT_CLASSIFICATION_MODEL"
"""De env-var waarmee de classificatie-modelkeuze wordt doorgegeven. Raakt **alleen**
de classificatie; zie `STANDAARD` voor de rest."""


def normaliseer(model: str) -> str:
    """Geef de alias voor `model`, of `model` zelf als het er geen gedateerde vorm van is.

    Bedoeld voor opzoeken (prijzen), niet voor het aanroepen van de API: wat er is
    aangeroepen hoort onveranderd in de trail te staan.
    """
    return GEDATEERDE_VORM.get(model, model)


def uit_omgeving() -> str:
    """Het gekozen classificatie-model, of `STANDAARD` als er niets is gezet."""
    return os.environ.get(ENV_VAR) or STANDAARD
