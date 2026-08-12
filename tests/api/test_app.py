"""Tests voor de auditor-API (`iso_audit.api`)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iso_audit.api.app import create_app
from iso_audit.api.session import AuditSession

_EX = Path("examples/auditmemo")
_FINDINGS = [
    {
        "id": "f1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "6.5",
        "title": "Offboarding",
        "description": "Offboarding niet aantoonbaar afgesloten.",
        "triage_status": "valide",
    },
    {
        "id": "f2",
        "severity": "OFI",
        "standard": "iso-9001-2015",
        "clause": "10.2",
        "title": "Effectiviteits-evaluatie",
        "description": "Niet vastgelegd.",
    },
]


_AUDITOR = "auditor@conduction.nl"
"""Identiteit die oauth2-proxy in productie zet. Hier expliciet meegegeven zodat de
tests de bewáákte route lopen in plaats van een uitgezette gate."""


def _client(tmp_path: Path) -> TestClient:
    (tmp_path / "findings.json").write_text(json.dumps(_FINDINGS), encoding="utf-8")
    session = AuditSession(
        tmp_path,
        profile=str(_EX / "conduction.profile.yaml"),
        norms_dir="examples/norms",
        memo_input_path=str(_EX / "memo-input.yaml"),
    )
    return TestClient(create_app(session), headers={"X-Forwarded-Email": _AUDITOR})


def _client_met(tmp_path: Path, findings: list[dict[str, object]]) -> TestClient:
    (tmp_path / "findings.json").write_text(json.dumps(findings), encoding="utf-8")
    session = AuditSession(
        tmp_path,
        profile=str(_EX / "conduction.profile.yaml"),
        norms_dir="examples/norms",
        memo_input_path=str(_EX / "memo-input.yaml"),
    )
    return TestClient(create_app(session), headers={"X-Forwarded-Email": _AUDITOR})


def test_conclusion_ofi_themes(tmp_path: Path) -> None:
    """OFI's gegroepeerd per thema, aflopend; NC's tellen niet mee."""
    findings: list[dict[str, object]] = [
        {
            "id": "a",
            "severity": "OFI",
            "standard": "iso-9001-2015",
            "clause": "7.1",
            "title": "x",
            "description": "d",
            "thema": "Documentbeheer",
        },
        {
            "id": "b",
            "severity": "OFI",
            "standard": "iso-9001-2015",
            "clause": "7.5",
            "title": "y",
            "description": "d",
            "thema": "Documentbeheer",
        },
        {
            "id": "c",
            "severity": "OFI",
            "standard": "iso-9001-2015",
            "clause": "9.1",
            "title": "z",
            "description": "d",
            "thema": "Monitoring en meting",
        },
        {
            "id": "n",
            "severity": "NC",
            "standard": "iso-9001-2015",
            "clause": "10.2",
            "title": "nc",
            "description": "d",
            "triage_status": "valide",
            "thema": "Documentbeheer",
        },
    ]
    themes = _client_met(tmp_path, findings).get("/conclusion").json()["ofi_themes"]
    assert themes[0]["thema"] == "Documentbeheer"  # grootste eerst
    assert themes[0]["count"] == 2
    assert themes[0]["clauses"] == ["7.1", "7.5"]
    assert {t["thema"] for t in themes} == {"Documentbeheer", "Monitoring en meting"}  # NC niet


def _client_writable_memo(tmp_path: Path) -> TestClient:
    """Sessie met een schrijfbare kopie van memo-input (mag de repo niet muteren)."""
    import shutil

    (tmp_path / "findings.json").write_text(json.dumps(_FINDINGS), encoding="utf-8")
    mi = tmp_path / "memo-input.yaml"
    shutil.copy(_EX / "memo-input.yaml", mi)
    session = AuditSession(
        tmp_path,
        profile=str(_EX / "conduction.profile.yaml"),
        norms_dir="examples/norms",
        memo_input_path=str(mi),
    )
    return TestClient(create_app(session), headers={"X-Forwarded-Email": _AUDITOR})


def test_memo_input_edit_roundtrip(tmp_path: Path) -> None:
    """Auditor past de memo aan vóór generatie: wijziging persisteert."""
    client = _client_writable_memo(tmp_path)
    data = client.get("/memo/input").json()
    data["title"] = "Aangepaste titel"
    data["context"]["sources"] = ["Google Drive", "Jira"]
    assert client.post("/memo/input", json=data).status_code == 200
    opnieuw = client.get("/memo/input").json()
    assert opnieuw["title"] == "Aangepaste titel"
    assert opnieuw["context"]["sources"] == ["Google Drive", "Jira"]


def test_memo_input_invalid_400(tmp_path: Path) -> None:
    """Ongeldige memo-input (mist verplichte velden) faalt met 400, niet bij render."""
    client = _client_writable_memo(tmp_path)
    assert client.post("/memo/input", json={"title": "alleen titel"}).status_code == 400


def test_edit_aanbeveling_ofi(tmp_path: Path) -> None:
    """OFI-aanbeveling (suggestion) is redigeerbaar via triage; append-only gelogd."""
    client = _client(tmp_path)
    r = client.post(
        "/findings/f2", json={"suggestion": "Overweeg X vast te leggen", "reason": "redactie"}
    )
    assert r.status_code == 200
    assert client.get("/findings/f2").json()["suggestion"] == "Overweeg X vast te leggen"
    assert client.get("/findings/f2/context").json()["suggestion"] == "Overweeg X vast te leggen"


def test_memo_toont_brondocument_links(tmp_path: Path) -> None:
    """De gerenderde memo bevat klikbare links naar de brondocumenten."""
    findings: list[dict[str, object]] = [
        {
            "id": "f1",
            "severity": "NC",
            "standard": "iso-27001-2022",
            "clause": "6.5",
            "title": "x",
            "description": "d",
            "triage_status": "valide",
            "bronnen": [
                {
                    "herkomst": "Jira",
                    "doc_id": "ISO-7",
                    "doc_naam": "ISO-7",
                    "url": "https://co.atlassian.net/browse/ISO-7",
                    "beschrijving": "ticket",
                }
            ],
        }
    ]
    html = _client_met(tmp_path, findings).get("/memo/preview").text
    assert "https://co.atlassian.net/browse/ISO-7" in html


def test_get_findings(tmp_path: Path) -> None:
    r = _client(tmp_path).get("/findings")
    assert r.status_code == 200
    ids = {f["id"] for f in r.json()}
    assert ids == {"f1", "f2"}


def test_reclassify_nc_naar_ofi_append_only(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post("/findings/f1", json={"severity": "OFI", "reason": "bewijs in interview"})
    assert r.status_code == 200
    assert r.json()["severity"] == "OFI"
    # trail bevat de override (append-only) met from/to + reden.
    trail = client.get("/trail").json()
    assert len(trail) == 1
    assert trail[0]["field"] == "severity"
    assert trail[0]["from"] == "NC" and trail[0]["to"] == "OFI"
    assert trail[0]["reason"] == "bewijs in interview"


def test_triage_status_append_groeit(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/findings/f1", json={"severity": "OFI", "reason": "r1"})
    client.post("/findings/f1", json={"triage_status": "niet_valide", "reason": "r2"})
    trail = client.get("/trail").json()
    assert len(trail) == 2  # append-only: eerste blijft staan
    assert trail[1]["field"] == "triage_status"


def test_memo_gated_bij_open_kandidaat(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # zet de NC terug naar 'open' → memo moet 409'en (triage niet compleet).
    client.post("/findings/f1", json={"triage_status": "open", "reason": "heropenen"})
    assert client.get("/triage/status").json()["complete"] is False
    assert client.get("/memo/preview").status_code == 409


def test_triage_status_endpoint(tmp_path: Path) -> None:
    d = _client(tmp_path).get("/triage/status").json()
    assert d == {"total_nc": 1, "open": 0, "complete": True}


def test_finding_detail(tmp_path: Path) -> None:
    r = _client(tmp_path).get("/findings/f1")
    assert r.status_code == 200
    assert r.json()["clause"] == "6.5"


def test_finding_context_hover(tmp_path: Path) -> None:
    c = _client(tmp_path).get("/findings/f1/context").json()
    assert c["citations"]  # 6.5 resolvet in de voorbeeld-norm-DB
    assert c["citations"][0]["clause"] == "6.5"
    assert c["citations"][0]["text"]  # échte normtekst voor de hover
    assert "deviation" in c and "reasoning" in c and "verify_with" in c


def test_conclusion_saturatie(tmp_path: Path) -> None:
    # f1 is NC + valide (fixture), geen open/follow-up → verzadigd.
    c = _client(tmp_path).get("/conclusion").json()
    assert c["tally"]["valide"] == 1 and c["tally"]["open"] == 0
    assert c["saturated"] is True
    assert "saturatie" in c["advice"].lower() or "memo" in c["advice"].lower()


def test_follow_up_blokkeert_saturatie(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/findings/f1", json={"triage_status": "follow_up", "reason": "bewijs ophalen"})
    c = client.get("/conclusion").json()
    assert c["tally"]["follow_up"] == 1
    assert c["saturated"] is False
    assert "meer audits" in c["advice"].lower()


def test_tekst_redactie_append_only(tmp_path: Path) -> None:
    client = _client(tmp_path)
    r = client.post(
        "/findings/f1",
        json={
            "deviation": "Herschreven afwijking.",
            "corrective_measure": "Doe Z.",
            "reason": "redactie",
        },
    )
    assert r.status_code == 200
    assert client.get("/findings/f1").json()["deviation"] == "Herschreven afwijking."
    velden = {e["field"] for e in client.get("/trail").json()}
    assert {"deviation", "corrective_measure"} <= velden


def test_onbekende_finding_404(tmp_path: Path) -> None:
    r = _client(tmp_path).post("/findings/zzz", json={"severity": "OFI", "reason": "x"})
    assert r.status_code == 404


def test_memo_preview_rendert_html(tmp_path: Path) -> None:
    r = _client(tmp_path).get("/memo/preview")
    assert r.status_code == 200
    assert "Auditmemo" in r.text
    assert "Offboarding" in r.text


def test_findings_severity_filter(tmp_path: Path) -> None:
    r = _client(tmp_path).get("/findings", params={"severity": "NC"})
    data = r.json()
    assert [f["id"] for f in data] == ["f1"]  # alleen de NC


def test_config_options(tmp_path: Path) -> None:
    d = _client(tmp_path).get("/config/options").json()
    assert "iso-9001-2015" in d["norms"] and "iso-27001-2022" in d["norms"]
    assert "drive" in d["sources"]  # registry


def test_config_health_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Het endpoint levert per bron de `_check_source`-uitkomst terug.

    `_check_source` gestubd → deterministisch, geen netwerk. Test dat de UI per
    geregistreerde bron een `connected`-bool + naam krijgt.
    """
    import iso_audit.api.session as sess

    def _fake(naam: str) -> dict[str, object]:
        return {"connected": naam == "drive", "status": "ok", "naam": naam}

    monkeypatch.setattr(sess, "_check_source", _fake)
    h = _client(tmp_path).get("/config/health").json()
    assert {"drive", "jira", "miro", "planning"} <= set(h)
    assert h["drive"]["connected"] is True
    assert h["jira"]["connected"] is False
    for naam, status in h.items():
        assert status["naam"] == naam


def test_check_source_prefers_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_check_source` gebruikt de lichte `probe()` als die bestaat, anders healthcheck."""
    import iso_audit.api.session as sess

    class _MetProbe:
        naam = "drive"
        gebruikt = ""

        def probe(self) -> dict[str, object]:
            type(self).gebruikt = "probe"
            return {"status": "ok", "naam": "drive"}

        def healthcheck(self) -> dict[str, object]:  # mag NIET aangeroepen worden
            type(self).gebruikt = "healthcheck"
            return {"status": "ok", "naam": "drive"}

    class _ZonderProbe:
        naam = "jira"

        def healthcheck(self) -> dict[str, object]:
            return {"status": "fail", "naam": "jira", "reden": "geen creds"}

    fakes = {"drive": _MetProbe, "jira": _ZonderProbe}
    monkeypatch.setattr("iso_audit.sources.get", lambda naam: fakes[naam])

    drive = sess._check_source("drive")
    assert drive["connected"] is True and _MetProbe.gebruikt == "probe"
    jira = sess._check_source("jira")
    assert jira["connected"] is False and jira["reden"] == "geen creds"


def test_check_source_miro_via_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Miro (pseudo-source) is gekoppeld zodra MIRO_API_TOKEN gezet is."""
    import iso_audit.api.session as sess

    monkeypatch.setenv("MIRO_API_TOKEN", "tok")
    assert sess._check_source("miro")["connected"] is True
    monkeypatch.delenv("MIRO_API_TOKEN", raising=False)
    assert sess._check_source("miro")["connected"] is False


def test_run_met_config(tmp_path: Path) -> None:
    d = (
        _client(tmp_path)
        .post("/run", json={"norms": ["iso-9001-2015"], "sources": ["drive"]})
        .json()
    )
    assert d["findings"] == 2
    assert d["config"]["sources"] == ["drive"]


def test_run_zonder_body(tmp_path: Path) -> None:
    d = _client(tmp_path).post("/run").json()  # body optioneel
    assert d["findings"] == 2


def test_run_progress_synchroon(tmp_path: Path) -> None:
    client = _client(tmp_path)
    start = client.post("/run/start", json={"mode": "sim", "pace": 0}).json()  # synchroon
    assert start == {"mode": "sim", "total": 2, "status": "done"}
    p = client.get("/run/progress").json()
    assert p["status"] == "done"
    assert p["done"] == 2 and p["total"] == 2
    assert "elapsed_s" in p and "eta_s" in p


def test_run_progress_idle(tmp_path: Path) -> None:
    p = _client(tmp_path).get("/run/progress").json()
    assert p["status"] == "idle"
    assert p["done"] == 0


def test_live_run_worker_draft_en_status(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Live-worker: pipeline + draft gemockt → findings vervangen + status done."""
    import iso_audit.api.run_job as rj
    from iso_audit.api.session import AuditSession, _RunState
    from iso_audit.memo.models import Finding

    monkeypatch.setattr(rj, "run_live_pipeline", lambda **kw: kw["on_log"]("Stap 7/7: klaar"))
    fake = [
        Finding(
            id="nc-8.15",
            severity="NC",
            standard="iso-27001-2022",
            clause="8.15",
            title="Logging",
            description="d",
            triage_status="open",
        )
    ]
    monkeypatch.setattr(rj, "draft_from_db", lambda **kw: fake)

    import shutil

    (tmp_path / "findings.json").write_text(json.dumps(_FINDINGS), encoding="utf-8")
    # Schrijfbare kopie: _run_live_worker werkt de memo-context bij — mag de
    # gecommitte repo-memo-input NIET muteren.
    mi = tmp_path / "memo-input.yaml"
    shutil.copy(_EX / "memo-input.yaml", mi)
    s = AuditSession(
        tmp_path,
        profile=str(_EX / "conduction.profile.yaml"),
        norms_dir="examples/norms",
        memo_input_path=str(mi),
    )
    s._run = _RunState(status="running", total=7, mode="live")
    s._run_live_worker("27001", ["drive"], "8", 3)  # synchroon (geen thread)

    assert s._run.status == "done"
    assert [f.id for f in s.findings()] == ["nc-8.15"]
    assert any("Stap 7/7" in m for m in s._run.log)


def test_index_serveert_ui(tmp_path: Path) -> None:
    r = _client(tmp_path).get("/")
    assert r.status_code == 200
    assert "auditor-flow" in r.text
    assert "Triage" in r.text
