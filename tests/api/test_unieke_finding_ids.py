"""Twee bevindingen mogen nooit hetzelfde `id` krijgen.

Gemeten in productie op 2026-08-24. De werkset had 903 regels en 902 unieke id's: `nc-5.17`
kwam twee keer voor, met verschillende titels ("Beheer en beveiliging van
authenticatie-informatie **ontbreekt**" en dezelfde zonder dat woord), verschillende
`deviation` en verschillende `corrective_measure`. Twee echte bevindingen dus, en de
dedup-sleutel zag dat goed — die bevat de genormaliseerde titel.

Het **id** zag het niet: dat is `nc-<clausule>`, dus elke tweede NC op dezelfde clausule
botst. Gevolg in de UI: `apply_triage` zoekt met `next(...)` en muteert alleen de eerste
match. De auditor zet de tweede op `valide`, de trail legt dat vast, en de lijst blijft `open`.
Dat is niet te repareren door harder te klikken, en het blokkeert de memo-gate voor altijd.

Waarom dit hier hard wordt afgedwongen en niet in de UI wordt opgevangen: een id is de sleutel
waarmee de append-only trail naar een bevinding verwijst. Twee regels onder één sleutel maakt
de trail dubbelzinnig — en dan is niet meer te zeggen welke bevinding een auditor beoordeelde.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from iso_audit.api import runs


def _kandidaat(clausule: str, titel: str) -> dict[str, Any]:
    return {
        "id": f"nc-{clausule}",
        "severity": "NC",
        "standard": "27001",
        "clause": clausule,
        "title": titel,
        "description": titel,
        "deviation": "",
        "source": "Drive",
        "triage_status": "open",
    }


def _werkset(audit_dir: Path) -> list[dict[str, Any]]:
    return json.loads((audit_dir / "findings.json").read_text(encoding="utf-8"))


def test_tweede_bevinding_op_dezelfde_clausule_krijgt_een_eigen_id(tmp_path: Path) -> None:
    """Beide bevindingen blijven staan — alleen het id van de tweede wijkt af.

    Niet dedupliceren: de titels verschillen, dus het zijn twee bevindingen en dat oordeel is
    aan de auditor. Alleen het id moet uniek worden, want dat is de sleutel van de trail.
    """
    runs.voeg_toe(tmp_path, [_kandidaat("5.17", "Authenticatie-informatie ontbreekt")])
    toegevoegd, overgeslagen = runs.voeg_toe(
        tmp_path, [_kandidaat("5.17", "Authenticatie-informatie onvolledig")]
    )

    assert (toegevoegd, overgeslagen) == (1, 0)
    werkset = _werkset(tmp_path)
    assert len(werkset) == 2
    ids = [f["id"] for f in werkset]
    assert len(set(ids)) == 2, f"id's niet uniek: {ids}"
    assert ids[0] == "nc-5.17", "het eerste id mag niet veranderen — de trail verwijst ernaar"


def test_identieke_kandidaat_wordt_nog_steeds_overgeslagen(tmp_path: Path) -> None:
    """De dedup blijft werken: hetzelfde geval twee keer levert één regel.

    Zonder deze test zou "maak id's uniek" van elke herhaalde run een nieuwe bevinding maken,
    en dan groeit de werkset elke run met alles wat er al stond.
    """
    kandidaat = _kandidaat("5.17", "Authenticatie-informatie ontbreekt")
    runs.voeg_toe(tmp_path, [kandidaat])
    toegevoegd, overgeslagen = runs.voeg_toe(tmp_path, [dict(kandidaat)])

    assert (toegevoegd, overgeslagen) == (0, 1)
    assert len(_werkset(tmp_path)) == 1


def test_drie_op_dezelfde_clausule_geven_drie_id_s(tmp_path: Path) -> None:
    for titel in ("ontbreekt", "onvolledig", "niet actueel"):
        runs.voeg_toe(tmp_path, [_kandidaat("5.17", f"Authenticatie {titel}")])
    ids = [f["id"] for f in _werkset(tmp_path)]
    assert len(set(ids)) == 3, f"id's niet uniek: {ids}"


def test_bestaande_dubbele_ids_worden_hersteld_met_een_spoor(tmp_path: Path) -> None:
    """Voor de werkset die al bestaat: herstellen, en de wijziging vastleggen.

    De productie-werkset had de dubbele al staan. Stil laten liggen betekent dat die bevinding
    nooit meer te triageren is; stil hernoemen betekent dat de trail naar een id verwijst dat
    niet meer bestaat. Dus hernoemen **en** de hernoeming in de trail zetten.
    """
    werkset = [
        _kandidaat("5.17", "Authenticatie ontbreekt"),
        _kandidaat("5.17", "Authenticatie onvolledig"),
        _kandidaat("8.24", "Encryptie ontbreekt"),
    ]
    (tmp_path / "findings.json").write_text(json.dumps(werkset), encoding="utf-8")

    hersteld = runs.herstel_dubbele_ids(tmp_path, door="auditor@test")

    assert hersteld == 1
    ids = [f["id"] for f in _werkset(tmp_path)]
    assert len(set(ids)) == 3, f"id's niet uniek na herstel: {ids}"
    assert ids[0] == "nc-5.17", "de eerste houdt zijn id — de trail verwijst ernaar"

    trail = [
        json.loads(r)
        for r in (tmp_path / "triage_log.jsonl").read_text(encoding="utf-8").splitlines()
        if r.strip()
    ]
    hernoemingen = [r for r in trail if r["field"] == "id"]
    assert len(hernoemingen) == 1
    assert hernoemingen[0]["from"] == "nc-5.17"
    assert hernoemingen[0]["to"] == ids[1]
    assert hernoemingen[0]["actor"] == "auditor@test"


def test_herstel_is_idempotent(tmp_path: Path) -> None:
    """Twee keer draaien mag geen tweede hernoeming opleveren."""
    werkset = [_kandidaat("5.17", "a"), _kandidaat("5.17", "b")]
    (tmp_path / "findings.json").write_text(json.dumps(werkset), encoding="utf-8")

    assert runs.herstel_dubbele_ids(tmp_path, door="a@test") == 1
    assert runs.herstel_dubbele_ids(tmp_path, door="a@test") == 0
