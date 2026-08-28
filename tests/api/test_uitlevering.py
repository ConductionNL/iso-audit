"""De auditor moet bij de output kunnen.

De export meldde tot 2026-08-26 alleen een serverpad:
`PDF: /var/lib/iso-audit/audits/27001_9001-2026-Q3/Auditmemo_management.pdf`. Dat is een pad in
een pod met een read-only filesystem, achter een oauth-proxy. Niemand kan daarbij. Er was in de
hele API geen enkele download-route — ook de bewijslast-rapporten van 8 MB waren onbereikbaar.

Een tool dat bewijs produceert dat niemand kan ophalen, heeft geen bewijs geproduceerd.

Twee omvangen, want dat is wat een auditor vraagt: alleen de memo (om te bespreken), of het hele
pakket (om te archiveren en te overleggen). Wat erin zit staat in een manifest — de selectie van
de bewijslast berust op een regel, en die regel hoort leesbaar in de zip te staan.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from .conftest import PortaalClient, maak_portaal

_AUDITOR = "auditor@conduction.nl"
_FINDINGS = [
    {
        "id": "nc1",
        "severity": "NC",
        "standard": "iso-27001-2022",
        "clause": "A.8.14",
        "title": "Continuïteit",
        "description": "Niet getest.",
        "triage_status": "valide",
    }
]


def _client(tmp_path: Path) -> PortaalClient:
    return maak_portaal(tmp_path, findings=_FINDINGS)


def _zip(client: PortaalClient, scope: str) -> zipfile.ZipFile:
    r = client.get(f"/download?scope={scope}", headers={"X-Auth-Request-Email": _AUDITOR})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers["content-disposition"]
    return zipfile.ZipFile(io.BytesIO(r.content))


def test_de_zip_heet_naar_de_audit(tmp_path: Path) -> None:
    """Drie zips in een downloadmap moeten uit elkaar te houden zijn."""
    client = _client(tmp_path)
    r = client.get("/download?scope=memo", headers={"X-Auth-Request-Email": _AUDITOR})
    assert client.audit_id in r.headers["content-disposition"]
    assert "memo" in r.headers["content-disposition"]


def test_scope_memo_bevat_de_memo_en_het_manifest(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post("/memo/export", headers={"X-Auth-Request-Email": _AUDITOR})
    namen = _zip(client, "memo").namelist()
    assert any(n.endswith("Auditmemo_management.pdf") for n in namen), namen
    assert "INHOUD.md" in namen


def test_scope_bewijslast_bevat_ook_de_werkset_en_de_trail(tmp_path: Path) -> None:
    client = _client(tmp_path)
    (client.audit_dir / "runs.jsonl").write_text('{"run_id": "run-0001"}\n', encoding="utf-8")
    (client.audit_dir / "triage_log.jsonl").write_text('{"actor": "x"}\n', encoding="utf-8")
    namen = _zip(client, "bewijslast").namelist()
    assert any(n.endswith("findings.json") for n in namen), namen
    assert any(n.endswith("runs.jsonl") for n in namen), namen
    assert any(n.endswith("triage_log.jsonl") for n in namen), namen


def test_het_manifest_noemt_elk_bestand_en_de_selectieregel(tmp_path: Path) -> None:
    """Zonder die regel weet een externe auditor niet waarom dít erin zit en dat niet."""
    zf = _zip(_client(tmp_path), "bewijslast")
    manifest = zf.read("INHOUD.md").decode("utf-8")
    for naam in zf.namelist():
        if naam != "INHOUD.md":
            assert Path(naam).name in manifest, f"niet in manifest: {naam}"
    assert "selectie" in manifest.lower()


def test_een_onbekende_scope_wordt_geweigerd(tmp_path: Path) -> None:
    r = _client(tmp_path).get(
        "/download?scope=alles-en-nog-wat", headers={"X-Auth-Request-Email": _AUDITOR}
    )
    assert r.status_code == 422


def test_zonder_memo_pdf_is_de_memo_zip_geen_fout_maar_een_lege_lijst(tmp_path: Path) -> None:
    """Nog niet geëxporteerd is een toestand, geen storing — maar het manifest zegt het wel."""
    zf = _zip(_client(tmp_path), "memo")
    manifest = zf.read("INHOUD.md").decode("utf-8")
    assert "nog niet" in manifest.lower()


def test_de_download_is_afgeschermd(tmp_path: Path) -> None:
    """Dezelfde poort als de rest: een bewijslastpakket is geen open bestand.

    `headers={}` betekent in deze fixture bewust géén identity-header, in tegenstelling tot
    `None` — dat valt terug op de auditor-default en zou hier niets bewijzen.
    """
    client = maak_portaal(tmp_path, findings=_FINDINGS, headers={})
    assert client.get("/download?scope=memo").status_code == 403


def test_de_zip_bevat_geen_paden_buiten_de_audit(tmp_path: Path) -> None:
    """Geen absolute paden, geen `..` — een zip die buiten zijn map uitpakt is een lek."""
    for naam in _zip(_client(tmp_path), "bewijslast").namelist():
        assert not naam.startswith("/")
        assert ".." not in naam


def test_de_findings_in_de_zip_zijn_de_echte(tmp_path: Path) -> None:
    zf = _zip(_client(tmp_path), "bewijslast")
    naam = next(n for n in zf.namelist() if n.endswith("findings.json"))
    assert json.loads(zf.read(naam))[0]["id"] == "nc1"
