"""Een opvolgpunt houdt zijn id over runs heen.

`_issue_to_finding` bouwde het id als `f"{sessie_id}:{key}"`. Het sessie-id is per run anders,
dus dezelfde Jira-issue kreeg elke run een nieuw id — en `_upsert_bevindingen` zag dat als een
nieuw punt. Gemeten op 2026-08-24 met drie runs op één database:

| ronde | classificatie-calls | opvolgpunten in `bevindingen` |
|---|---|---|
| 1 | 118 | 83 |
| 2 | 0 (alles uit cache) | 166 |

83 unieke Jira-sleutels, elk twee keer, onder twee `audit-<tijdstempel>`-prefixen. Er kwam geen
enkele modelaanroep aan te pas: het waren letterlijk dezelfde punten, opnieuw opgeslagen.

Ze staan buiten de triage (`herkomst NOT LIKE '%-opvolging'`), dus de werkset bleef schoon. Wat
wél scheefloopt is elke telling van "hoeveel opvolging is er" — en dat is precies waar deze rijen
voor bestaan: aantonen dát er opvolging plaatsvindt. Een teller die met elke run verdubbelt, toont
dat niet aan maar overdrijft het.

Het documentenpad in dezelfde module gebruikt al wél de kale key (`_issue_to_document`); alleen
het bevindingenpad week af.
"""

from __future__ import annotations

from typing import Any

from iso_audit.sources.jira import _issue_to_finding

_ISSUE: dict[str, Any] = {
    "key": "ISO-751",
    "fields": {"summary": "Logging-baseline vaststellen", "labels": ["iso27001-8.15"]},
}


def test_id_is_de_jira_sleutel_en_niet_de_sessie() -> None:
    finding = _issue_to_finding(_ISSUE, "audit-20260824T134042Z")
    assert finding.id == "ISO-751"


def test_twee_runs_geven_hetzelfde_id() -> None:
    """De kern: zonder dit dupliceert elke run alle opvolgpunten."""
    eerste = _issue_to_finding(_ISSUE, "audit-20260824T134042Z")
    tweede = _issue_to_finding(_ISSUE, "audit-20260824T141958Z")
    assert eerste.id == tweede.id


def test_bewijs_verwijst_nog_steeds_naar_de_issue() -> None:
    finding = _issue_to_finding(_ISSUE, "audit-x")
    assert finding.bewijs_uris == ["jira://ISO-751"]
    assert finding.clausule_ids == ["8.15"]
