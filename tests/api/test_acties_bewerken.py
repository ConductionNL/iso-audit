"""Eigenaren en deadlines invullen in het portaal, niet in een los .docx.

De memo levert per NC een actietabel met "wat", en de kolommen "wie", "waar" en "uiterlijk"
staan er als placeholder. Iemand moet die invullen, en de vraag was of dat in een .docx naast
het systeem mocht.

Nee: dan bewerkt iemand buiten het systeem en weet de audit-trail niet wie wat heeft toegezegd.
Een managementmemo waarvan de toezeggingen niet herleidbaar zijn, is precies het soort document
waar een externe auditor een NC op schrijft.

Dus in het portaal, via dezelfde weg als de triage: onder hetzelfde slot, append-only, met de
echte actor erbij.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .conftest import PortaalClient, maak_portaal

_AUDITOR = "auditor@conduction.nl"
_KOP = {"X-Auth-Request-Email": _AUDITOR}

_FINDINGS = [
    {
        "id": "nc1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.14",
        "title": "Continuïteit",
        "description": "Niet getest.",
        "thema": "Back-up & continuïteit",
        "triage_status": "valide",
        "actions": [{"wat": "Continuïteitstest inplannen"}, {"wat": "Uitkomst vastleggen"}],
    },
    {
        "id": "ofi1",
        "severity": "OFI",
        "standard": "iso-27001-2022",
        "clause": "8.15",
        "title": "Logging",
        "description": "Geen baseline.",
        "thema": "Logging & monitoring",
        "actions": [{"wat": "Baseline beschrijven"}],
    },
]


def _client(tmp_path: Path) -> PortaalClient:
    return maak_portaal(tmp_path, findings=_FINDINGS)


def test_de_lijst_toont_elke_actie_met_zijn_bevinding(tmp_path: Path) -> None:
    rijen = _client(tmp_path).get("/acties", headers=_KOP).json()
    assert [(r["finding_id"], r["index"]) for r in rijen] == [("nc1", 0), ("nc1", 1), ("ofi1", 0)]
    assert rijen[0]["thema"] == "Back-up & continuïteit"
    assert rijen[0]["severity"] == "NC"


def test_een_eigenaar_invullen_blijft_staan(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post(
        "/findings/nc1/acties/0",
        json={"wie": "CISO", "uiterlijk": "2026-10-01", "reason": "afgesproken in de bespreking"},
        headers=_KOP,
    )
    assert r.status_code == 200, r.text
    acties = json.loads((client.audit_dir / "findings.json").read_text())[0]["actions"]
    assert acties[0]["wie"] == "CISO"
    assert acties[0]["uiterlijk"] == "2026-10-01"
    assert acties[1]["wie"] is None, "alleen de aangewezen rij mag veranderen"


def test_de_wijziging_staat_in_de_trail_met_de_echte_actor(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post(
        "/findings/nc1/acties/0", json={"wie": "CISO", "reason": "bespreking"}, headers=_KOP
    )
    regels = [
        json.loads(r)
        for r in (client.audit_dir / "triage_log.jsonl").read_text().splitlines()
        if r.strip()
    ]
    laatste = regels[-1]
    assert laatste["actor"] == _AUDITOR
    assert laatste["finding_id"] == "nc1"
    assert "wie" in laatste["field"]
    assert laatste["to"] == "CISO"
    assert laatste["reason"] == "bespreking"


def test_de_tekst_van_de_actie_is_ook_te_corrigeren(tmp_path: Path) -> None:
    """ "Wat" komt uit het model; een auditor moet een onhandige formulering kunnen bijstellen."""
    client = _client(tmp_path)
    r = client.post(
        "/findings/nc1/acties/0",
        json={"wat": "Continuïteitstest uitvoeren", "reason": "scherper"},
        headers=_KOP,
    )
    assert r.status_code == 200
    acties = json.loads((client.audit_dir / "findings.json").read_text())[0]["actions"]
    assert acties[0]["wat"] == "Continuïteitstest uitvoeren"


def test_een_niet_bestaande_rij_is_een_nette_fout(tmp_path: Path) -> None:
    r = _client(tmp_path).post(
        "/findings/nc1/acties/9", json={"wie": "X", "reason": "y"}, headers=_KOP
    )
    assert r.status_code == 404


def test_een_niet_bestaande_bevinding_is_een_nette_fout(tmp_path: Path) -> None:
    r = _client(tmp_path).post(
        "/findings/zzz/acties/0", json={"wie": "X", "reason": "y"}, headers=_KOP
    )
    assert r.status_code == 404


def test_niets_wijzigen_schrijft_niets(tmp_path: Path) -> None:
    """Een lege wijziging hoort geen regel in een append-only trail te zetten."""
    client = _client(tmp_path)
    client.post("/findings/nc1/acties/0", json={"reason": "niets"}, headers=_KOP)
    trail = client.audit_dir / "triage_log.jsonl"
    assert not trail.exists() or not trail.read_text().strip()


@pytest.mark.parametrize("veld", ["wie", "waar", "uiterlijk"])
def test_elk_van_de_drie_kolommen_is_invulbaar(tmp_path: Path, veld: str) -> None:
    client = _client(tmp_path)
    client.post("/findings/ofi1/acties/0", json={veld: "waarde", "reason": "r"}, headers=_KOP)
    acties = json.loads((client.audit_dir / "findings.json").read_text())[1]["actions"]
    assert acties[0][veld] == "waarde"
