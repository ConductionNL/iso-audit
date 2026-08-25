"""De memo past op één tot drie A4, en meldt het als dat niet lukt.

De klant stelt dat als harde eis. Een memo die stil op vier pagina's uitkomt breekt die eis
zonder dat iemand het merkt — hetzelfde patroon als de PDF die maandenlang ontbrak omdat de
melding een `logger.warning` was, en als de MIME-types die zonder melding werden overgeslagen.

Daarom wordt er geteld en gemeld, en wordt de memo **wel** geschreven: een auditor die hem te
lang vindt kan comprimeren, maar een memo die weigert helpt niemand. Het verschil met de
norm-DB-weigering is dat daar inhoud ontbrak; hier is de inhoud er en is alleen de vorm te ruim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from iso_audit.memo.renderer.pdf import MAX_PAGINAS, PaginaBudget, schrijf_pdf

_KORT = "<html><body><h1>Auditmemo</h1><p>Eén NC.</p></body></html>"


def _lang(paginas: int) -> str:
    blokken = "".join(
        f'<div style="page-break-after: always">Blok {i}</div>' for i in range(paginas)
    )
    return f"<html><body>{blokken}</body></html>"


def test_een_korte_memo_past(tmp_path: Path) -> None:
    budget = schrijf_pdf(_KORT, tmp_path / "memo.pdf")
    assert budget.paginas == 1
    assert budget.past is True
    assert budget.melding == ""


def test_de_grens_ligt_op_drie_paginas() -> None:
    """De klanteis is 1 tot 3 A4; die staat in de code, niet in een aanname."""
    assert MAX_PAGINAS == 3


def test_een_te_lange_memo_wordt_wel_geschreven(tmp_path: Path) -> None:
    """Schrijven én melden. Weigeren zou de auditor met lege handen laten."""
    pad = tmp_path / "memo.pdf"

    budget = schrijf_pdf(_lang(6), pad)

    assert pad.is_file()
    assert budget.past is False
    assert budget.paginas > MAX_PAGINAS


def test_de_melding_noemt_het_aantal_paginas(tmp_path: Path) -> None:
    """ "Te lang" zonder getal laat de auditor raden hoeveel eruit moet."""
    budget = schrijf_pdf(_lang(6), tmp_path / "memo.pdf")
    assert str(budget.paginas) in budget.melding
    assert str(MAX_PAGINAS) in budget.melding


def test_het_budget_is_af_te_lezen_zonder_de_pdf_te_openen(tmp_path: Path) -> None:
    """De aanroeper moet erop kunnen sturen: loggen, in de run-samenvatting, in het portaal."""
    budget = schrijf_pdf(_KORT, tmp_path / "memo.pdf")
    assert isinstance(budget, PaginaBudget)
    assert budget.pad.name == "memo.pdf"


@pytest.mark.parametrize("paginas", [1, 2, 3])
def test_een_tot_drie_paginas_past(paginas: int, tmp_path: Path) -> None:
    budget = schrijf_pdf(_lang(paginas), tmp_path / "memo.pdf")
    assert budget.past is True, f"{budget.paginas} pagina's zou moeten passen"
