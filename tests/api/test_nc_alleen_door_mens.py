"""Een NC wordt alleen door een mens-account getrieerd — afgedwongen, niet afgesproken.

De regel stond in de docstring van `classification/auto_triage.py` en werd daar netjes gevolgd,
maar alleen bij het *voorstellen*. Op de schrijfweg lag niets. En de schrijfweg is precies wat
een externe auditor leest: de trail zegt wie wat besloot. Staat daar bij een bevestigde NC een
machine-actor, dan is de bevestiging niet te verantwoorden — ongeacht hoe zorgvuldig de agent
was die het voorstel deed.

Beide richtingen zijn geblokkeerd, niet alleen bevestigen. Een NC afserveren als `niet_valide`
is even zwaar een auditoordeel als hem bevestigen: in het ene geval draagt de organisatie een
correctie, in het andere verdwijnt een geconstateerd gebrek uit het dossier.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from iso_audit.api.session import MACHINE_ACTOREN, AuditSession, SessionError
from iso_audit.classification.auto_triage import AUTO_ACTOR

_FINDINGS = [
    {
        "id": "nc1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.14",
        "title": "Continuïteit",
        "description": "Niet getest.",
        "triage_status": "open",
    },
    {
        "id": "pos1",
        "severity": "POSITIVE",
        "standard": "iso-27001-2022",
        "clause": "5.1",
        "title": "Beleid vastgesteld",
        "description": "Aantoonbaar.",
        "triage_status": "open",
    },
]


_EX = Path("examples/auditmemo")


def _sessie(tmp_path: Path) -> AuditSession:
    (tmp_path / "findings.json").write_text(json.dumps(_FINDINGS), encoding="utf-8")
    return AuditSession(
        tmp_path,
        profile=str(_EX / "conduction.profile.yaml"),
        norms_dir="examples/norms",
        memo_input_path=str(_EX / "memo-input.yaml"),
    )


def test_auto_triage_staat_in_de_lijst_met_machine_actoren() -> None:
    """Anders is de blokkade een dode letter."""
    assert AUTO_ACTOR in MACHINE_ACTOREN


def test_een_machine_mag_een_nc_niet_bevestigen(tmp_path: Path) -> None:
    sessie = _sessie(tmp_path)
    with pytest.raises(SessionError, match="mens-account"):
        sessie.apply_triage(
            "nc1", triage_status="valide", reason="review zei bevestigen", actor=AUTO_ACTOR
        )


def test_een_machine_mag_een_nc_ook_niet_afserveren(tmp_path: Path) -> None:
    sessie = _sessie(tmp_path)
    with pytest.raises(SessionError, match="mens-account"):
        sessie.apply_triage(
            "nc1", triage_status="niet_valide", reason="lijkt onterecht", actor=AUTO_ACTOR
        )


def test_de_geweigerde_triage_laat_niets_achter(tmp_path: Path) -> None:
    """Half doorgevoerd is erger dan geweigerd: dan staat er een wijziging zonder besluit."""
    sessie = _sessie(tmp_path)
    with pytest.raises(SessionError):
        sessie.apply_triage("nc1", triage_status="valide", reason="x", actor=AUTO_ACTOR)
    assert next(f for f in sessie.findings() if f.id == "nc1").triage_status == "open"
    assert (
        not (tmp_path / "triage_log.jsonl").exists()
        or not (tmp_path / "triage_log.jsonl").read_text(encoding="utf-8").strip()
    )


def test_een_machine_mag_wel_een_positieve_bevinding_afdoen(tmp_path: Path) -> None:
    """Dat is het onbetwiste voorwerk waar auto-triage voor bestaat."""
    sessie = _sessie(tmp_path)
    f = sessie.apply_triage(
        "pos1", triage_status="valide", reason="review bevestigde", actor=AUTO_ACTOR
    )
    assert f.triage_status == "valide"


def test_een_mens_mag_de_nc_gewoon_bevestigen(tmp_path: Path) -> None:
    sessie = _sessie(tmp_path)
    f = sessie.apply_triage(
        "nc1", triage_status="valide", reason="auditsessie 26-8", actor="auditor@conduction.nl"
    )
    assert f.triage_status == "valide"


def test_een_machine_kan_de_regel_niet_omzeilen_via_de_classificatie(tmp_path: Path) -> None:
    """Iets in dezelfde aanroep tot NC promoveren en meteen bevestigen, telt ook als NC."""
    sessie = _sessie(tmp_path)
    with pytest.raises(SessionError, match="mens-account"):
        sessie.apply_triage(
            "pos1", severity="NC", triage_status="valide", reason="x", actor=AUTO_ACTOR
        )
