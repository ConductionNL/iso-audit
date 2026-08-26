"""De bevindingenlijst filtert op meer dan classificatie.

Op 2026-08-26 meldde de auditor dat hij niet op triage-status kon filteren, en ook niet op bron
of clausule. Met 271 bevindingen in één audit is dat geen comfort-kwestie: "laat zien wat nog
open staat" is de eerste vraag van elke triage-sessie, en zonder dat filter is het antwoord
scrollen.

De filters combineren met AND. Een filter dat niets oplevert geeft een lege lijst en geen fout —
dat is een geldig antwoord op "is hier nog iets open?".
"""

from __future__ import annotations

from pathlib import Path

from .conftest import PortaalClient, maak_portaal

_AUDITOR = "auditor@conduction.nl"

_FINDINGS = [
    {
        "id": "f1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.14",
        "title": "Continuïteit",
        "description": "Niet getest.",
        "triage_status": "open",
        "source": "Drive/Continuiteitsplan.docx",
    },
    {
        "id": "f2",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "8.5",
        "title": "MFA",
        "description": "Niet gedefinieerd.",
        "triage_status": "valide",
        "source": "Drive/Toegangsbeleid.docx",
    },
    {
        "id": "f3",
        "severity": "OFI",
        "standard": "iso-9001-2015",
        "clause": "10.2",
        "title": "Evaluatie",
        "description": "Niet vastgelegd.",
        "triage_status": "open",
        "source": "Jira/ISO-42",
    },
]


def _client(tmp_path: Path) -> PortaalClient:
    return maak_portaal(tmp_path, findings=_FINDINGS)


def _ids(client: PortaalClient, query: str) -> list[str]:
    r = client.get(f"/findings{query}", headers={"X-Auth-Request-Email": _AUDITOR})
    assert r.status_code == 200, r.text
    return sorted(f["id"] for f in r.json())


def test_zonder_filter_komt_alles_terug(tmp_path: Path) -> None:
    assert _ids(_client(tmp_path), "") == ["f1", "f2", "f3"]


def test_filter_op_triage_status(tmp_path: Path) -> None:
    assert _ids(_client(tmp_path), "?triage_status=open") == ["f1", "f3"]


def test_filter_op_bron_is_deeltekst(tmp_path: Path) -> None:
    """De auditor typt "drive", niet het volledige pad."""
    assert _ids(_client(tmp_path), "?source=drive") == ["f1", "f2"]


def test_filter_op_clausule_pakt_het_hele_hoofdstuk(tmp_path: Path) -> None:
    """`8` betekent §8.x — anders moet je elke subclausule los weten."""
    assert _ids(_client(tmp_path), "?clause=8") == ["f1", "f2"]


def test_filter_op_clausule_kan_ook_exact(tmp_path: Path) -> None:
    assert _ids(_client(tmp_path), "?clause=8.14") == ["f1"]


def test_een_clausulefilter_matcht_geen_toevallig_prefix(tmp_path: Path) -> None:
    """`8.1` mag §8.14 niet opleveren; dat is een ander onderwerp."""
    assert _ids(_client(tmp_path), "?clause=8.1") == []


def test_filters_combineren_met_and(tmp_path: Path) -> None:
    assert _ids(_client(tmp_path), "?severity=NC&triage_status=open") == ["f1"]


def test_een_filter_zonder_treffers_geeft_een_lege_lijst(tmp_path: Path) -> None:
    assert _ids(_client(tmp_path), "?source=nextcloud") == []
