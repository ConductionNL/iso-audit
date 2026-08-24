"""`levert_opvolgpunten` moet werken zonder dat iemand anders eerst de adapters laadde.

De functie vraagt het aan de Source-registry en valt bij een `KeyError` terug op `False`. Is de
registry leeg — een los proces, of een test die als eerste draait — dan betekent dat "Jira levert
geen opvolgpunten", en wordt Jira stilletjes als documentbron ingelezen. Elk ticket wordt dan
tegen elke clausule geclassificeerd: ruis plus modelkosten per ticket, en precies de rolwissel
die de docstring van die functie uitsluit.

Dit brak op 2026-08-24 toen de bootstrap uit `ingest.beschikbare_bronnen()` naar
`sources.laad_adapters()` verhuisde. In de volledige testsuite viel het niet op omdat een andere
test de adapters al had geïmporteerd — de test faalde alleen wanneer `tests/test_pipeline.py`
los draaide. Een test die van zijn buren afhangt, toetst niet wat hij zegt te toetsen.
"""

from __future__ import annotations

import iso_audit.sources
from iso_audit.sources.opvolgpunten import levert_opvolgpunten


def test_werkt_met_een_lege_registry() -> None:
    iso_audit.sources._reset_for_tests()
    assert levert_opvolgpunten("jira") is True


def test_een_documentbron_levert_geen_opvolgpunten() -> None:
    iso_audit.sources._reset_for_tests()
    assert levert_opvolgpunten("drive") is False


def test_onbekende_bron_levert_false() -> None:
    iso_audit.sources._reset_for_tests()
    assert levert_opvolgpunten("bestaat-niet") is False
