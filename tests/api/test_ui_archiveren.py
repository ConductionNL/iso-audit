"""De archiveerknop staat in het auditoverzicht.

De vraag was letterlijk "ook handig als die weggegooid kunnen worden". Wat er staat is
archiveren en niet verwijderen — een audit die gedraaid heeft is bewijs dát er geaudit is — en
de knop moet dat zeggen, anders klikt iemand hem in de veronderstelling dat het weg is.
"""

from __future__ import annotations

from pathlib import Path

UI = Path("src/iso_audit/api/ui.html")


def _html() -> str:
    return UI.read_text(encoding="utf-8")


def test_er_is_een_archiveerknop_per_audit() -> None:
    assert "archiveerAudit(" in _html()


def test_de_knop_zegt_dat_er_niets_wordt_verwijderd() -> None:
    """Anders klikt iemand hem denkend dat het dossier weg is."""
    html = _html()
    kop = html[
        html.index("archiveerAudit('${a.id}')") : html.index("archiveerAudit('${a.id}')") + 300
    ]
    assert "niets verwijderd" in kop


def test_de_ui_vraagt_een_reden() -> None:
    html = _html()
    assert "Waarom?" in html
    assert "Geef een reden op." in html


def test_de_lijst_wordt_ververst_na_archiveren() -> None:
    """Anders blijft de rij staan en denkt de auditor dat het niet werkte."""
    html = _html()
    blok = html[
        html.index("async function archiveerAudit") : html.index("async function maakAudit")
    ]
    assert "loadDashboard()" in blok
