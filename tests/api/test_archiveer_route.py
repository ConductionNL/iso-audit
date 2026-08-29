"""De archiveerknop doet wat hij belooft.

Op 2026-08-29 gaf `POST /audits/{id}/archiveer` een 422 met `loc: ["query","body"]`, en bij het
opvragen van `/openapi.json` zelfs een 500. De oorzaak: `AuditArchiveren` was *binnen*
`create_app` gedefinieerd, en met `from __future__ import annotations` is elke annotatie een
string. FastAPI kan die forward reference niet oplossen naar een lokale klasse, dus zag hij
`body` als queryparameter.

Gevolg: de knop stond er, de route stond er, en samen werkten ze niet. Precies het gat dat een
contract-test niet ziet — `tests/api/test_ui_archiveren.py` controleerde dat de UI het juiste
pad aanroept, niet dat dat pad werkt.

De reden blijft verplicht: zonder reden is later niet te zien of dit opruimen was of iets
wegwerken.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from .conftest import maak_portaal

_AUDITOR = "auditor@conduction.nl"
_KOP = {"X-Auth-Request-Email": _AUDITOR}


def test_archiveren_lukt_met_een_reden(tmp_path: Path) -> None:
    client = maak_portaal(tmp_path)
    r = client.post(
        "/archiveer", json={"reden": "proefrun, hoort niet in het overzicht"}, headers=_KOP
    )
    assert r.status_code == 200, r.text


def test_de_audit_verdwijnt_uit_het_overzicht(tmp_path: Path) -> None:
    client = maak_portaal(tmp_path)
    assert any(a["id"] == client.audit_id for a in client.raw.get("/audits", headers=_KOP).json())
    client.post("/archiveer", json={"reden": "opruimen"}, headers=_KOP)
    assert not any(
        a["id"] == client.audit_id for a in client.raw.get("/audits", headers=_KOP).json()
    )


def test_er_wordt_niets_verwijderd(tmp_path: Path) -> None:
    """De map gaat naar het archief. Dat staat ook zo op de knop, en het moet waar zijn."""
    client = maak_portaal(tmp_path)
    client.post("/archiveer", json={"reden": "opruimen"}, headers=_KOP)
    # `archief/<datum>/<audit-id>-<tijd>/`, dus twee niveaus diep.
    archief = list(tmp_path.rglob("archief/*/*/findings.json"))
    assert archief, "de audit is niet terug te vinden in het archief"


def test_zonder_reden_wordt_het_geweigerd(tmp_path: Path) -> None:
    """Zonder reden is later niet te zien of dit opruimen was of iets wegwerken."""
    client = maak_portaal(tmp_path)
    assert client.post("/archiveer", json={}, headers=_KOP).status_code == 422


def test_een_lege_reden_telt_niet(tmp_path: Path) -> None:
    client = maak_portaal(tmp_path)
    r = client.post("/archiveer", json={"reden": "   "}, headers=_KOP)
    assert r.status_code in (400, 422), r.text


def test_de_openapi_beschrijving_klopt(tmp_path: Path) -> None:
    """`/openapi.json` gaf een 500 zolang het model niet op te lossen was.

    Dat is niet alleen cosmetisch: elke gegenereerde client en elke integratie leest dit.
    """
    client = maak_portaal(tmp_path)
    spec = client.raw.get("/openapi.json", headers=_KOP)
    assert spec.status_code == 200
    route = spec.json()["paths"]["/audits/{audit_id}/archiveer"]["post"]
    assert "requestBody" in route, "de reden hoort in de body, niet in de query"
    assert not [p for p in route.get("parameters", []) if p["name"] == "body"]


def test_de_reden_komt_in_de_audittrail(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """`log_event` schrijft naar de logger, niet naar een bestand — dat is de audittrail."""
    client = maak_portaal(tmp_path)
    with caplog.at_level(logging.INFO, logger="iso_audit.audit"):
        client.post("/archiveer", json={"reden": "proefrun met verkeerde scope"}, headers=_KOP)
    regels = [json.loads(r.message) for r in caplog.records if r.message.startswith("{")]
    archief = [r for r in regels if r.get("soort") == "audit_gearchiveerd"]
    assert archief, f"geen archiveer-regel: {[r.get('soort') for r in regels]}"
    assert "verkeerde scope" in archief[-1]["reden"]
