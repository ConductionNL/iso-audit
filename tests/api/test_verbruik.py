"""Wat de audits tot nu toe hebben gekost, zichtbaar bij de sleutel.

De auditor vroeg om het credit-saldo bij de API-key. Dat kan niet: `cost_report` en
`usage_report` geven met een gewone key een 401 — *"The Admin API requires an Admin API key"* —
en die kan alleen een org-owner maken. Een saldo-endpoint bestaat sowieso niet in de publieke
API; `cost_report` geeft uitgaven, niet wat er nog op staat.

Wat wél kan met wat er al is: het portaal legt per run de werkelijke kosten vast (model,
aanroepen, bedrag, peildatum). Die stonden alleen in het run-record en nergens bij elkaar. De
vraag achter "hoeveel credit heb ik nog" is in de praktijk "wat verbruikt dit ding", en dat kan
wél beantwoord worden — met gemeten eigen cijfers in plaats van een geschat saldo.

Nadrukkelijk het bedrag dat dít portaal heeft uitgegeven, niet het accountsaldo. Een getal dat
suggereert dat het het saldo is, is erger dan geen getal.
"""

from __future__ import annotations

import json
from pathlib import Path

from .conftest import maak_portaal

_AUDITOR = "auditor@conduction.nl"
_KOP = {"X-Auth-Request-Email": _AUDITOR}


def _run(usd: float, calls: int, model: str = "claude-haiku-4-5") -> str:
    return json.dumps(
        {
            "run_id": "run-0001",
            "soort": "afsluiting",
            "status": "klaar",
            "kosten": {
                "usd": usd,
                "calls": calls,
                "model": model,
                "peildatum": "2026-08-20",
                "grondslag": "werkelijk tarief",
            },
        }
    )


def test_zonder_runs_is_het_verbruik_nul(tmp_path: Path) -> None:
    client = maak_portaal(tmp_path)
    d = client.raw.get("/instellingen/anthropic", headers=_KOP).json()
    assert d["verbruik"]["usd"] == 0.0
    assert d["verbruik"]["runs"] == 0


def test_het_verbruik_telt_alle_runs_op(tmp_path: Path) -> None:
    client = maak_portaal(tmp_path)
    (client.audit_dir / "runs.jsonl").write_text(
        _run(0.79, 129) + "\n" + _run(0.21, 40) + "\n", encoding="utf-8"
    )
    d = client.raw.get("/instellingen/anthropic", headers=_KOP).json()
    assert d["verbruik"]["usd"] == 1.0
    assert d["verbruik"]["calls"] == 169
    assert d["verbruik"]["runs"] == 2


def test_een_run_zonder_kosten_telt_niet_mee(tmp_path: Path) -> None:
    """Een sim-run of een afgebroken run heeft geen bedrag; die als 0 meetellen zou het
    gemiddelde vertekenen en suggereren dat er gratis gedraaid is."""
    client = maak_portaal(tmp_path)
    (client.audit_dir / "runs.jsonl").write_text(
        _run(0.79, 129) + "\n" + json.dumps({"run_id": "run-0002", "status": "klaar"}) + "\n",
        encoding="utf-8",
    )
    d = client.raw.get("/instellingen/anthropic", headers=_KOP).json()
    assert d["verbruik"]["runs"] == 1


def test_het_verbruik_zegt_dat_het_niet_het_saldo_is(tmp_path: Path) -> None:
    """Een getal dat als accountsaldo leest, is erger dan geen getal.

    Het saldo is met een gewone API-key niet op te vragen; dit is wat dit portaal heeft
    uitgegeven, gemeten uit de eigen run-records.
    """
    client = maak_portaal(tmp_path)
    d = client.raw.get("/instellingen/anthropic", headers=_KOP).json()
    toelichting = str(d["verbruik"]["toelichting"]).lower()
    assert "saldo" in toelichting
    assert "portaal" in toelichting or "dit tool" in toelichting


def test_kapotte_regels_laten_het_scherm_niet_breken(tmp_path: Path) -> None:
    """Een configuratiescherm dat omvalt op één rare regel, is niet te repareren."""
    client = maak_portaal(tmp_path)
    (client.audit_dir / "runs.jsonl").write_text(
        "geen json\n" + _run(0.5, 10) + "\n", encoding="utf-8"
    )
    d = client.raw.get("/instellingen/anthropic", headers=_KOP).json()
    assert d["verbruik"]["usd"] == 0.5
