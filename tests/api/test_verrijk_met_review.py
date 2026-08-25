"""De export haalt kernzin en acties uit het review-advies.

De review oordeelt per clausule; de werkset bestaat uit bevindingen. Zonder deze koppeling
blijft de kernzin in de database staan en komt hij nooit in de memo — dan is de hele review
alleen een logregel.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from iso_audit.api.run_job import verrijk_met_review
from iso_audit.memo.models import Finding
from iso_audit.store import bewaar_review_advies, initialiseer


def _finding(clausule: str, standard: str = "iso-27001-2022") -> Finding:
    return Finding(
        id=f"nc-{clausule}",
        severity="NC",
        standard=standard,
        clause=clausule,
        title=f"§{clausule}",
        description="x",
    )


def _conn_met_advies(**kw: Any) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    bewaar_review_advies(
        conn,
        norm=kw.get("norm", "27001"),
        clausule=kw.get("clausule", "8.14"),
        advies="bevestigen",
        kern=kw.get("kern", "Geen getest continuïteitsplan."),
        reden="Volgens Plan.docx.",
        acties=kw.get("acties", [{"wat": "BCM-plan opstellen", "wie": "IT-lead"}]),
    )
    return conn


def test_de_kernzin_landt_op_de_bevinding() -> None:
    conn = _conn_met_advies()
    verrijkt = verrijk_met_review([_finding("8.14")], conn)
    assert verrijkt[0].kern == "Geen getest continuïteitsplan."


def test_de_acties_landen_op_de_bevinding() -> None:
    conn = _conn_met_advies()
    verrijkt = verrijk_met_review([_finding("8.14")], conn)
    assert verrijkt[0].actions[0].wat == "BCM-plan opstellen"
    assert verrijkt[0].actions[0].wie == "IT-lead"


def test_zonder_advies_blijft_de_bevinding_ongemoeid() -> None:
    """Een run zonder review moet gewoon een memo kunnen opleveren."""
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    verrijkt = verrijk_met_review([_finding("8.14")], conn)
    assert verrijkt[0].kern == ""
    assert verrijkt[0].actions == []


def test_de_norm_moet_kloppen() -> None:
    """Een advies over 9001 §7.5 hoort niet op een bevinding over 27001 §7.5.

    Achttien clausulenummers bestaan in beide normen; zonder deze controle zou de kernzin over
    "Gedocumenteerde informatie" onder "Bescherming tegen fysieke bedreigingen" belanden.
    """
    conn = _conn_met_advies(norm="9001", clausule="7.5", kern="Over documentbeheer.")
    verrijkt = verrijk_met_review([_finding("7.5", standard="iso-27001-2022")], conn)
    assert verrijkt[0].kern == ""


def test_bestaande_acties_worden_niet_overschreven() -> None:
    """Wat de auditor zelf invulde wint van een voorstel."""
    from iso_audit.memo.models import ActionRow

    conn = _conn_met_advies()
    f = _finding("8.14")
    f.actions = [ActionRow(wat="Door de auditor ingevuld", wie="MT")]
    verrijkt = verrijk_met_review([f], conn)
    assert verrijkt[0].actions[0].wat == "Door de auditor ingevuld"


def test_de_titel_volgt_de_norm_van_de_bevinding() -> None:
    """§7.5 heet in 9001 iets anders dan in 27001; de auditor ziet de titel in de werkset.

    Zonder deze koppeling toont een 9001-bevinding de 27001-titel, want dat is degene die de
    samengevoegde map bovenaan zet. Dan staat er "Bescherming tegen fysieke en
    omgevingsbedreigingen" boven een bevinding over documentbeheer.
    """
    from iso_audit.classification.clause_mapping import titel_voor

    assert titel_voor("7.5", "9001") != titel_voor("7.5", "27001")
    assert "informatie" in titel_voor("7.5", "9001").lower()
