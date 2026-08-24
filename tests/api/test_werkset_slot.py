"""Een triage-beslissing mag niet verloren gaan als er tegelijk een run schrijft.

Gemeten in productie op 2026-08-24: de auditor zette 902 bevindingen op `valide`, en één
daarvan (`nc-5.17`, 11:49:21Z) stond daarna weer op `open`. De trail hield de beslissing wel —
die is append-only — dus trail en werkset spraken elkaar tegen. Voor een audittool is dat de
ergste soort fout: het spoor zegt dat de auditor geoordeeld heeft en de werkset zegt van niet,
en de memo-gate blokkeert op het verschil.

Twee schrijvers op `findings.json`, beide lees-alles → wijzig → schrijf-alles, zonder slot:
`runs.voeg_toe()` uit de run-thread en `session.apply_triage()` uit de verzoek-thread. De run
had de werkset gelezen vóór de triage en schreef zijn eigen snapshot terug.

Deze test draait het echte scenario met threads. Zonder slot verdwijnen er beslissingen; de
assertie is niet "het gaat meestal goed" maar "alle beslissingen staan erin".
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from iso_audit.api import runs
from iso_audit.api.session import AuditSession

_EX = Path("examples")

AANTAL = 40
"""Genoeg bevindingen om de race te raken en klein genoeg voor een snelle test."""


def _bevinding(nummer: int) -> dict[str, Any]:
    return {
        "id": f"nc-{nummer}",
        "severity": "NC",
        "clause": f"5.{nummer}",
        "title": f"Bevinding {nummer}",
        "deviation": "",
        "standard": "27001",
        "description": f"Beschrijving {nummer}",
        "source": "Drive",
        "triage_status": "open",
    }


def _sessie(audit_dir: Path) -> AuditSession:
    """Een sessie op deze map; profiel en normen doen hier niet mee."""
    memo_input = audit_dir / "memo-input.yaml"
    memo_input.write_text("title: t\nlead_summary: s\ncontext: {}\n", encoding="utf-8")
    return AuditSession(
        audit_dir,
        profile=str(_EX / "conduction.profile.yaml"),
        norms_dir=str(_EX / "norms"),
        memo_input_path=str(memo_input),
    )


def _werkset(audit_dir: Path) -> list[dict[str, Any]]:
    return json.loads((audit_dir / "findings.json").read_text(encoding="utf-8"))


def test_triage_en_run_schrijven_door_elkaar_zonder_verlies(tmp_path: Path) -> None:
    audit_dir = tmp_path
    (audit_dir / "findings.json").write_text(
        json.dumps([_bevinding(n) for n in range(AANTAL)]), encoding="utf-8"
    )
    (audit_dir / "audit.json").write_text(
        json.dumps({"id": "a", "normen": ["27001"], "periode": "2026"}), encoding="utf-8"
    )

    sessie = _sessie(audit_dir)
    fouten: list[BaseException] = []
    start = threading.Barrier(5)

    def triageer(van: int, tot: int) -> None:
        try:
            start.wait(timeout=10)
            for n in range(van, tot):
                sessie.apply_triage(
                    f"nc-{n}",
                    triage_status="valide",
                    reason="auditsessie (test)",
                    actor="auditor@test",
                )
        except BaseException as fout:
            fouten.append(fout)

    def run_voegt_toe() -> None:
        """De run-thread: leest de hele werkset en schrijft hem terug, herhaaldelijk."""
        try:
            start.wait(timeout=10)
            for n in range(AANTAL, AANTAL + 10):
                runs.voeg_toe(audit_dir, [_bevinding(n)])
        except BaseException as fout:
            fouten.append(fout)

    threads = [threading.Thread(target=triageer, args=(i * 10, (i + 1) * 10)) for i in range(4)] + [
        threading.Thread(target=run_voegt_toe)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not fouten, f"fout in een thread: {fouten[0]!r}"

    werkset = {f["id"]: f for f in _werkset(audit_dir)}
    niet_valide = sorted(
        i
        for i, f in werkset.items()
        if i.startswith("nc-") and int(i[3:]) < AANTAL
        if f["triage_status"] != "valide"
    )
    assert not niet_valide, f"triage-beslissingen verloren gegaan: {niet_valide}"
    toegevoegd = sorted(i for i in werkset if int(i[3:]) >= AANTAL)
    assert len(toegevoegd) == 10, f"kandidaten van de run verloren: {toegevoegd}"


def test_de_trail_en_de_werkset_lopen_niet_uiteen(tmp_path: Path) -> None:
    """De trail is het bewijs; de werkset is wat de auditor ziet. Die twee moeten kloppen.

    Dit is de controle die het probleem in productie aan het licht bracht, en daarom hoort hij
    in de suite: elke `to`-waarde in `triage_log.jsonl` moet terug te vinden zijn in
    `findings.json`.
    """
    audit_dir = tmp_path
    (audit_dir / "findings.json").write_text(
        json.dumps([_bevinding(n) for n in range(AANTAL)]), encoding="utf-8"
    )
    (audit_dir / "audit.json").write_text(
        json.dumps({"id": "a", "normen": ["27001"], "periode": "2026"}), encoding="utf-8"
    )
    sessie = _sessie(audit_dir)

    def triageer() -> None:
        for n in range(AANTAL):
            sessie.apply_triage(
                f"nc-{n}", triage_status="valide", reason="auditsessie (test)", actor="a@test"
            )

    def voeg_toe() -> None:
        for n in range(AANTAL, AANTAL + 10):
            runs.voeg_toe(audit_dir, [_bevinding(n)])

    t1, t2 = threading.Thread(target=triageer), threading.Thread(target=voeg_toe)
    t1.start(), t2.start()
    t1.join(timeout=60), t2.join(timeout=60)

    werkset = {f["id"]: f["triage_status"] for f in _werkset(audit_dir)}
    trail_pad = audit_dir / "triage_log.jsonl"
    laatste: dict[str, str] = {}
    for regel in trail_pad.read_text(encoding="utf-8").splitlines():
        if not regel.strip():
            continue
        rij = json.loads(regel)
        if rij["field"] == "triage_status":
            laatste[rij["finding_id"]] = rij["to"]

    afwijkend = {i: (t, werkset.get(i)) for i, t in laatste.items() if werkset.get(i) != t}
    assert not afwijkend, f"trail en werkset lopen uiteen: {afwijkend}"
