"""De kop-NC's krijgen ook de kernzin en de acties van de review.

De run van 2026-08-25 22:38 leverde 140 bevindingen met een kernzin op — maar geen enkele van de
47 NC's. Uitgerekend die hebben hem nodig: de memo bestaat uit NC-blokken.

Oorzaak: NC's komen uit `draft_from_db`, een ander pad dan de ruwe bevindingen. Dat pad zet een
placeholder-actie ("(actie in te vullen door auditor)") en slaat de review-verrijking over —
en omdat de actielijst dan niet leeg is, liet `verrijk_met_review` hem ook staan.

De placeholder blijft als er geen voorstel is; een leeg vakje ziet de auditor en vult hij. Maar
een voorstel dat er wél is, hoort niet achter een placeholder te verdwijnen.
"""

from __future__ import annotations

import sqlite3

from iso_audit.api.run_job import verrijk_met_review
from iso_audit.memo.models import ActionRow, Finding
from iso_audit.store import bewaar_review_advies, initialiseer

PLACEHOLDER = "(actie in te vullen door auditor)"


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    bewaar_review_advies(
        conn,
        norm="27001",
        clausule="8.16",
        advies="bevestigen",
        voorgestelde_klasse="NC",
        kern="Logging bestaat maar wordt niet beoordeeld.",
        reden="Volgens Beleid.docx.",
        acties=[{"wat": "Reviewcadans vastleggen", "wie": "IT-lead", "uiterlijk": "2026-Q4"}],
    )
    return conn


def _nc() -> Finding:
    return Finding(
        id="nc-8.16",
        severity="NC",
        standard="iso-27001-2022",
        clause="8.16",
        title="§8.16",
        description="x",
        actions=[ActionRow(wat=PLACEHOLDER)],
    )


def test_de_kop_nc_krijgt_de_kernzin() -> None:
    verrijkt = verrijk_met_review([_nc()], _conn())
    assert verrijkt[0].kern.startswith("Logging bestaat")


def test_het_voorstel_vervangt_de_placeholder() -> None:
    """Een placeholder is geen ingevulde actie; die mag een voorstel niet blokkeren."""
    verrijkt = verrijk_met_review([_nc()], _conn())
    assert verrijkt[0].actions[0].wat == "Reviewcadans vastleggen"
    assert verrijkt[0].actions[0].wie == "IT-lead"


def test_een_echte_actie_van_de_auditor_blijft_staan() -> None:
    """Wat een mens invulde wint, ook van een beter voorstel."""
    f = _nc()
    f.actions = [ActionRow(wat="Door de auditor bepaald", wie="MT")]
    verrijkt = verrijk_met_review([f], _conn())
    assert verrijkt[0].actions[0].wat == "Door de auditor bepaald"


def test_zonder_voorstel_blijft_de_placeholder() -> None:
    """Geen voorstel is geen reden om het vakje leeg te maken; de auditor vult het."""
    conn = sqlite3.connect(":memory:")
    initialiseer(conn)
    bewaar_review_advies(
        conn, norm="27001", clausule="8.16", advies="bevestigen", kern="k", reden="r"
    )
    verrijkt = verrijk_met_review([_nc()], conn)
    assert verrijkt[0].actions[0].wat == PLACEHOLDER
