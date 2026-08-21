"""Tests voor `iso_audit.reporting.local_report` — pure helpers + integratie."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from iso_audit.reporting import local_report

# ---------- _norm_label ----------


def test_norm_label_kent_drie_keys() -> None:
    assert local_report._norm_label("9001") == "ISO 9001:2015"
    assert local_report._norm_label("27001") == "ISO 27001:2022"
    assert local_report._norm_label("beide") == "ISO 9001:2015 + ISO 27001:2022"


def test_norm_label_unknown_fallback() -> None:
    assert local_report._norm_label("X") == "X"


# ---------- _audit_run_dir ----------


def test_audit_run_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCAL_REPORT_DIR", raising=False)
    monkeypatch.delenv("AUDIT_RUN_ID", raising=False)
    pad = local_report._audit_run_dir()
    assert "output/audit_reports" in pad
    assert "audit_" in Path(pad).name


def test_audit_run_dir_run_id_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOCAL_REPORT_DIR", raising=False)
    monkeypatch.setenv("AUDIT_RUN_ID", "mijn-run")
    pad = local_report._audit_run_dir()
    assert Path(pad).name == "mijn-run"


def test_audit_run_dir_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_REPORT_DIR", "/elders/rapporten")
    monkeypatch.setenv("AUDIT_RUN_ID", "wordt-genegeerd")
    assert local_report._audit_run_dir() == "/elders/rapporten"


# ---------- _doc_link ----------


def test_doc_link_drive() -> None:
    bev = {"doc_id": "doc-1", "document_naam": "Beleid", "herkomst": "Drive"}
    assert local_report._doc_link(bev) == "[Beleid](https://drive.google.com/file/d/doc-1/view)"


def test_doc_link_zonder_doc_id() -> None:
    bev = {"document_naam": "Onbekend"}
    assert local_report._doc_link(bev) == "_Onbekend_"


def test_doc_link_miro_zonder_board_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIRO_BOARD_ID", raising=False)
    bev = {"doc_id": "m1", "document_naam": "Sticky", "herkomst": "Miro"}
    assert local_report._doc_link(bev) == "_Sticky_"


def test_doc_link_miro_met_board_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIRO_BOARD_ID", "board-x")
    bev = {"doc_id": "m1", "document_naam": "Sticky", "herkomst": "Miro"}
    link = local_report._doc_link(bev)
    assert "miro.com/app/board/board-x" in link
    assert "moveToWidget=m1" in link


# ---------- _groepeer_per_clausule ----------


def test_groepeer_per_clausule_sorts_by_volgorde() -> None:
    """Bevindingen binnen één clausule worden gesorteerd NC → OFI → positief."""
    bev = [
        {"clausule": "10.2", "classificatie": "OFI"},
        {"clausule": "10.2", "classificatie": "NC"},
        {"clausule": "10.2", "classificatie": "positief"},
    ]
    result = local_report._groepeer_per_clausule(bev)
    classifs = [b["classificatie"] for b in result["10.2"]]
    assert classifs == ["NC", "OFI", "positief"]


def test_groepeer_per_clausule_clausule_sortering() -> None:
    """Clausules worden lexicografisch gesorteerd in de output-dict."""
    bev = [
        {"clausule": "5.1", "classificatie": "OFI"},
        {"clausule": "4.1", "classificatie": "OFI"},
    ]
    keys = list(local_report._groepeer_per_clausule(bev).keys())
    assert keys == ["4.1", "5.1"]


# ---------- _render_ofi_uitleg ----------


def test_render_ofi_uitleg_bevat_count() -> None:
    regels = local_report._render_ofi_uitleg(42)
    body = "\n".join(regels)
    assert "## 2a. Wat zijn OFI's?" in body
    assert "42 OFI's" in body


# ---------- _render_aanbevelingen ----------


def test_render_aanbevelingen_zonder_nc_ofi() -> None:
    regels = local_report._render_aanbevelingen([])
    body = "\n".join(regels)
    assert "Geen openstaande aanbevelingen" in body


def test_render_aanbevelingen_met_nc() -> None:
    bev: list[dict[str, Any]] = [
        {
            "classificatie": "NC",
            "clausule": "10.2",
            "document_naam": "Memo X",
            "beschrijving": "geen evaluatie",
            "onderbouwing": "...",
        }
    ]
    regels = local_report._render_aanbevelingen(bev)
    body = "\n".join(regels)
    assert "**NC** — Memo X" in body
    assert "ISO 9001 §10.2 / ISO 27001 §10.1" in body


def test_render_aanbevelingen_met_ofi_thema() -> None:
    bev: list[dict[str, Any]] = [
        {
            "classificatie": "OFI",
            "clausule": "8.15",
            "beschrijving": "logging monitoring",
            "onderbouwing": "",
            "document_naam": "Log-doc",
        }
    ]
    regels = local_report._render_aanbevelingen(bev)
    body = "\n".join(regels)
    assert "OFI — Logging & monitoring" in body


def test_render_aanbevelingen_overig_apart_genoemd() -> None:
    """OFI's met thema 'Overig' worden separaat geteld zolang er ook andere
    rijen zijn (geen 'Overig' in de aanbeveling-tabel zelf)."""
    bev: list[dict[str, Any]] = [
        # Thema-bare OFI's: per bepaal_thema vallen die in 'Overig'.
        {
            "classificatie": "OFI",
            "clausule": "6.1",
            "beschrijving": "iets unieks",
            "onderbouwing": "",
        },
        {
            "classificatie": "OFI",
            "clausule": "6.2",
            "beschrijving": "ook uniek",
            "onderbouwing": "",
        },
        # Eén Logging-OFI om het tabel-pad te activeren.
        {
            "classificatie": "OFI",
            "clausule": "8.15",
            "beschrijving": "logging review",
            "onderbouwing": "",
        },
    ]
    regels = local_report._render_aanbevelingen(bev)
    body = "\n".join(regels)
    assert "2 OFI's geclassificeerd als 'Overig'" in body
    # En de Logging-rij staat ook in de tabel.
    assert "OFI — Logging & monitoring" in body


# ---------- schrijf_rapport (integratie) ----------


def test_schrijf_rapport_basis(tmp_path: Path) -> None:
    bevindingen: list[dict[str, Any]] = [
        {
            "clausule": "10.2",
            "clausule_titel": "Non-conformiteit en corrigerende maatregel",
            "classificatie": "NC",
            "herkomst": "Drive",
            "document_naam": "Memo offboarding",
            "doc_id": "d1",
            "beschrijving": "Geen evaluatie aanwezig",
            "onderbouwing": "Norm §10.2 vereist effect-meting",
        }
    ]
    pad = local_report.schrijf_rapport(
        bevindingen=bevindingen,
        ontbrekende_clausules=[],
        handmatige_review=[],
        management_summary="Korte samenvatting.",
        norm="9001",
        output_dir=str(tmp_path),
    )
    md = Path(pad).read_text(encoding="utf-8")
    assert "# Auditrapport ISO 9001:2015" in md
    assert "Korte samenvatting." in md
    assert "Non-conformiteiten (NC) | 1 |" in md
    assert "🔴 NC" in md
    assert "**onvoldoende**" in md
    # NC zit ook in de aanbeveling-tabel.
    assert "**NC** — Memo offboarding" in md


def test_schrijf_rapport_zonder_bevindingen(tmp_path: Path) -> None:
    pad = local_report.schrijf_rapport(
        bevindingen=[],
        ontbrekende_clausules=[],
        handmatige_review=[],
        management_summary="",
        norm="27001",
        output_dir=str(tmp_path),
    )
    md = Path(pad).read_text(encoding="utf-8")
    assert "voldoende" in md  # geen NC → voldoende
    assert "_(geen bevindingen)_" in md


def test_schrijf_rapport_gearchiveerd_sectie(tmp_path: Path) -> None:
    gearchiveerd = [
        {"id": "d1", "naam": "Oud beleid", "modified_at": "2023-01-15T10:00:00Z"},
    ]
    pad = local_report.schrijf_rapport(
        bevindingen=[],
        ontbrekende_clausules=[],
        handmatige_review=[],
        management_summary="",
        norm="9001",
        output_dir=str(tmp_path),
        gearchiveerd=gearchiveerd,
    )
    md = Path(pad).read_text(encoding="utf-8")
    assert "## 7. Gearchiveerde documenten" in md
    assert "Oud beleid" in md
    assert "2023-01-15" in md


def test_schrijf_rapport_scherpte_in_bestandsnaam(tmp_path: Path) -> None:
    pad = local_report.schrijf_rapport(
        bevindingen=[],
        ontbrekende_clausules=[],
        handmatige_review=[],
        management_summary="",
        norm="9001",
        output_dir=str(tmp_path),
        scherpte=0.5,
    )
    assert "_s05" in Path(pad).name
