"""Tests voor `iso_audit.sources.drive` — DriveSource + legacy API, gws gemockt."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from iso_audit.sources import drive
from iso_audit.sources.base import Document


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for v in drive.FOLDER_ENV_VARS:
        monkeypatch.delenv(v, raising=False)


# ---------- _resolve_folder_id ----------


def test_resolve_expliciet() -> None:
    assert drive._resolve_folder_id("abc123") == "abc123"


def test_resolve_strip_query_params() -> None:
    assert drive._resolve_folder_id("abc123?hl=nl") == "abc123"


def test_resolve_env_eerste_variabele(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_SOURCE_FOLDER_ID", "uit-source")
    monkeypatch.setenv("AUDIT_DRIVE_FOLDER_ID", "uit-drive")
    # Eerste variabele in FOLDER_ENV_VARS wint.
    assert drive._resolve_folder_id() == "uit-source"


def test_resolve_fallback_naar_tweede_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_DRIVE_FOLDER_ID", "fallback")
    assert drive._resolve_folder_id() == "fallback"


def test_resolve_zonder_env_raised() -> None:
    with pytest.raises(OSError, match="Geen Drive-map"):
        drive._resolve_folder_id()


# ---------- _resolve_folder_ids (multi-folder) ----------


def test_resolve_ids_komma_sep_string() -> None:
    """Komma-gescheiden string wordt naar lijst gesplitst."""
    assert drive._resolve_folder_ids("a,b,c") == ["a", "b", "c"]


def test_resolve_ids_lijst_argument() -> None:
    """Lijst-argument wordt direct doorgegeven."""
    assert drive._resolve_folder_ids(["a", "b"]) == ["a", "b"]


def test_resolve_ids_beide_env_vars_samengevoegd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Beide env-vars met verschillende waarden → samengevoegd, dedup, volgorde behouden."""
    monkeypatch.setenv("AUDIT_SOURCE_FOLDER_ID", "0AAP-shared")
    monkeypatch.setenv("AUDIT_DRIVE_FOLDER_ID", "1YJoG-folder")
    assert drive._resolve_folder_ids() == ["0AAP-shared", "1YJoG-folder"]


def test_resolve_ids_dedup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dezelfde ID in beide env-vars verschijnt maar één keer."""
    monkeypatch.setenv("AUDIT_SOURCE_FOLDER_ID", "samepath")
    monkeypatch.setenv("AUDIT_DRIVE_FOLDER_ID", "samepath")
    assert drive._resolve_folder_ids() == ["samepath"]


def test_resolve_ids_komma_in_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Komma-sep binnen één env-var wordt ook gesplitst."""
    monkeypatch.setenv("AUDIT_SOURCE_FOLDER_ID", "a, b ,c")
    assert drive._resolve_folder_ids() == ["a", "b", "c"]


# ---------- _is_uitgesloten ----------


@pytest.mark.parametrize(
    "naam, uitgesloten",
    [
        ("NEN-EN-ISO 9001 NL.pdf", True),
        ("ISO_IEC_27001-2022.docx", True),
        ("About the Sample Files.txt", True),
        ("Beleid Conduction.docx", False),
        ("", False),
    ],
)
def test_is_uitgesloten(naam: str, uitgesloten: bool) -> None:
    assert drive._is_uitgesloten(naam) is uitgesloten


# ---------- DriveSource init + properties ----------


def test_drivesource_init_shared_drive() -> None:
    src = drive.DriveSource(folder_id="0A1234567890")
    assert src.folder_id == "0A1234567890"
    assert src.drive_id == "0A1234567890"
    assert src.naam == "drive"


def test_drivesource_init_reguliere_map() -> None:
    src = drive.DriveSource(folder_id="1abc")
    assert src.folder_id == "1abc"
    assert src.drive_id is None


def test_drivesource_init_query_strip() -> None:
    src = drive.DriveSource(folder_id="1abc?usp=share")
    assert src.folder_id == "1abc"


def test_drivesource_init_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_SOURCE_FOLDER_ID", "env-id")
    src = drive.DriveSource()
    assert src.folder_id == "env-id"


# ---------- list_documents ----------


def test_list_documents_yields_alleen_ondersteunde() -> None:
    bestanden = [
        {
            "id": "f1",
            "name": "Beleid.docx",
            "mimeType": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "modifiedTime": "2026-01-01T00:00:00Z",
        },
        {
            "id": "f2",
            "name": "Doc.gdoc",
            "mimeType": "application/vnd.google-apps.document",
            "modifiedTime": "2026-02-02T00:00:00Z",
        },
        # Skip:
        {"id": "f3", "name": "afb.png", "mimeType": "image/png", "modifiedTime": ""},
        {"id": "f4", "name": "rapport.pdf", "mimeType": "application/pdf", "modifiedTime": ""},
        # Uitgesloten op naam:
        {
            "id": "f5",
            "name": "ISO_IEC_27001.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "modifiedTime": "",
        },
    ]
    src = drive.DriveSource(folder_id="x")
    with patch.object(drive, "drive_lijst_bestanden", return_value=bestanden):
        docs = list(src.list_documents())
    ids = {d.id for d in docs}
    assert ids == {"f1", "f2"}


def test_list_documents_geeft_metadata_door() -> None:
    bestanden = [
        {
            "id": "f1",
            "name": "Beleid.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "modifiedTime": "2026-01-01T00:00:00Z",
        }
    ]
    src = drive.DriveSource(folder_id="x")
    with patch.object(drive, "drive_lijst_bestanden", return_value=bestanden):
        doc = next(iter(src.list_documents()))
    assert doc.id == "f1"
    assert doc.titel == "Beleid.docx"
    assert doc.bron == "drive"
    assert doc.type == "docx"
    assert doc.laatst_gewijzigd == "2026-01-01T00:00:00Z"
    assert doc.inhoud_uri == "f1"


def test_list_documents_lege_modifiedtime() -> None:
    """`modifiedTime` ontbrekend → lege string in `laatst_gewijzigd`."""
    bestanden = [
        {"id": "f1", "name": "x.txt", "mimeType": "text/plain"},
    ]
    src = drive.DriveSource(folder_id="y")
    with patch.object(drive, "drive_lijst_bestanden", return_value=bestanden):
        doc = next(iter(src.list_documents()))
    assert doc.laatst_gewijzigd == ""


# ---------- multi-folder ----------


def test_list_documents_multi_folder_unie() -> None:
    """Twee folders met disjoint files → union van docs."""
    folder_a = [
        {
            "id": "a1",
            "name": "A.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
    ]
    folder_b = [
        {
            "id": "b1",
            "name": "B.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
    ]
    src = drive.DriveSource(folder_id=["foldA", "foldB"])

    def _fake_list(fid: str, drive_id: str | None = None) -> list[dict[str, Any]]:
        return folder_a if fid == "foldA" else folder_b

    with patch.object(drive, "drive_lijst_bestanden", side_effect=_fake_list):
        ids = {d.id for d in src.list_documents()}
    assert ids == {"a1", "b1"}


def test_list_documents_multi_folder_dedup_op_file_id() -> None:
    """Hetzelfde file-id in beide folders → maar één keer in output."""
    overlap = [
        {
            "id": "same-1",
            "name": "Doc.docx",
            "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
    ]
    src = drive.DriveSource(folder_id=["foldA", "foldB"])
    with patch.object(drive, "drive_lijst_bestanden", return_value=overlap):
        docs = list(src.list_documents())
    assert len(docs) == 1
    assert docs[0].id == "same-1"


def test_drivesource_shared_drive_detection_per_folder() -> None:
    """`0A`-prefix wordt per folder als shared-drive-id behandeld."""
    src = drive.DriveSource(folder_id=["0A-shared", "1-regular"])
    # Property `folder_ids` levert beide; `folder_id`/`drive_id` retro-compat naar de eerste.
    assert src.folder_ids == ["0A-shared", "1-regular"]
    assert src.folder_id == "0A-shared"
    assert src.drive_id == "0A-shared"  # eerste is shared
    # Verifieer dat de tweede regular als folder-only is geregistreerd.
    assert src._drive_id_voor["1-regular"] is None


# ---------- fetch_content ----------


def test_fetch_content_google_doc() -> None:
    src = drive.DriveSource(folder_id="x")
    doc = Document(
        id="d1",
        titel="Doc",
        bron="drive",
        type="google_doc",
        laatst_gewijzigd="",
        inhoud_uri="d1",
    )
    with patch.object(drive, "drive_exporteer_google_doc", return_value="text!") as mock:
        out = src.fetch_content(doc)
    assert out == "text!"
    mock.assert_called_once_with("d1")


def test_fetch_content_plain_text() -> None:
    src = drive.DriveSource(folder_id="x")
    doc = Document(
        id="d1",
        titel="x.txt",
        bron="drive",
        type="txt",
        laatst_gewijzigd="",
        inhoud_uri="d1",
    )
    with patch.object(drive, "drive_download_bestand", return_value=b"hello"):
        out = src.fetch_content(doc)
    assert out == "hello"


def test_fetch_content_andere_bron_raised() -> None:
    src = drive.DriveSource(folder_id="x")
    doc = Document(
        id="d1",
        titel="x",
        bron="jira",
        type="google_doc",
        laatst_gewijzigd="",
        inhoud_uri="d1",
    )
    with pytest.raises(ValueError, match="DriveSource"):
        src.fetch_content(doc)


def test_fetch_content_onbekend_type_raised() -> None:
    src = drive.DriveSource(folder_id="x")
    doc = Document(
        id="d1",
        titel="x",
        bron="drive",
        type="onbekend",
        laatst_gewijzigd="",
        inhoud_uri="d1",
    )
    with pytest.raises(ValueError, match="Onbekend Document-type"):
        src.fetch_content(doc)


# ---------- list_findings + healthcheck ----------


def test_list_findings_geeft_lege_iterator() -> None:
    src = drive.DriveSource(folder_id="x")
    assert list(src.list_findings("sessie-1")) == []


def test_healthcheck_ok() -> None:
    src = drive.DriveSource(folder_id="x")
    with patch.object(drive, "drive_lijst_bestanden", return_value=[{"id": "a"}]):
        h = src.healthcheck()
    assert h["status"] == "ok"
    assert h["naam"] == "drive"
    assert h["aantal_bestanden"] == 1


def test_healthcheck_fail_geeft_een_soort_en_lekt_de_ruwe_melding_niet() -> None:
    """De melding van de leverancier hoort in het serverlog, niet in het antwoord.

    Deze test asserteerde eerder dat "boom" in `reden` stond — dat legde het lek vast als
    gewenst gedrag. De ruwe tekst kan een URL met credential of een responsbody bevatten.
    """
    src = drive.DriveSource(folder_id="x")
    with patch.object(drive, "drive_lijst_bestanden", side_effect=RuntimeError("boom")):
        h = src.healthcheck()
    assert h["status"] == "fail"
    assert h["soort"]
    assert "boom" not in str(h["reden"])


def test_healthcheck_multi_folder_aggregeert() -> None:
    """Healthcheck telt bestanden per folder + totaal."""
    src = drive.DriveSource(folder_id=["foldA", "foldB"])

    def _fake_list(fid: str, drive_id: str | None = None) -> list[dict[str, Any]]:
        return [{"id": f"{fid}-1"}, {"id": f"{fid}-2"}] if fid == "foldA" else [{"id": "b-1"}]

    with patch.object(drive, "drive_lijst_bestanden", side_effect=_fake_list):
        h = src.healthcheck()
    assert h["status"] == "ok"
    assert h["aantal_bestanden"] == 3
    assert h["per_folder"] == {"foldA": 2, "foldB": 1}


def test_healthcheck_multi_folder_fail_eerste_folder() -> None:
    """Eerste falende folder → status=fail met de specifieke folder benoemd."""
    src = drive.DriveSource(folder_id=["foldA", "foldB"])

    def _fake_list(fid: str, drive_id: str | None = None) -> list[dict[str, Any]]:
        if fid == "foldB":
            raise RuntimeError("permission denied op foldB")
        return [{"id": "a-1"}]

    with patch.object(drive, "drive_lijst_bestanden", side_effect=_fake_list):
        h = src.healthcheck()
    assert h["status"] == "fail"
    # De folder staat in `tenant` (die hoort bewust in de trail), niet in de vrije tekst:
    # daar zou de ruwe leveranciersmelding mee naar binnen komen.
    assert h["tenant"] == "foldB"
    assert "permission denied" not in str(h["reden"])


# ---------- Registry-registratie ----------


def test_drivesource_geregistreerd() -> None:
    """DriveSource zou via @register beschikbaar moeten zijn in SourceRegistry."""
    from iso_audit.sources import available, get

    assert "drive" in available()
    assert get("drive") is drive.DriveSource


# ---------- Legacy haal_documenten_op ----------


def test_haal_documenten_op_lege_lijst_raised() -> None:
    with (
        patch.object(drive, "drive_lijst_bestanden", return_value=[]),
        pytest.raises(RuntimeError, match="Geen bestanden"),
    ):
        drive.haal_documenten_op(folder_id="x")


def test_haal_documenten_op_happy_path() -> None:
    bestanden = [
        {"id": "f1", "name": "x.txt", "mimeType": "text/plain", "modifiedTime": "2026-01-01"},
    ]
    with (
        patch.object(drive, "drive_lijst_bestanden", return_value=bestanden),
        patch.object(drive, "drive_download_bestand", return_value=b"content"),
    ):
        docs, review = drive.haal_documenten_op(folder_id="x")
    assert len(docs) == 1
    assert docs[0]["tekst"] == "content"
    assert review == []


def test_haal_documenten_op_niet_tekstueel_naar_review() -> None:
    bestanden = [
        {"id": "f1", "name": "afb.png", "mimeType": "image/png", "modifiedTime": ""},
    ]
    with patch.object(drive, "drive_lijst_bestanden", return_value=bestanden):
        docs, review = drive.haal_documenten_op(folder_id="x")
    assert docs == []
    assert len(review) == 1
    assert "image/png" in review[0]["reden"]


def test_haal_documenten_op_leesfout_naar_review() -> None:
    bestanden = [
        {
            "id": "f1",
            "name": "Doc.gdoc",
            "mimeType": "application/vnd.google-apps.document",
            "modifiedTime": "",
        },
    ]
    with (
        patch.object(drive, "drive_lijst_bestanden", return_value=bestanden),
        patch.object(drive, "drive_exporteer_google_doc", side_effect=RuntimeError("oops")),
    ):
        docs, review = drive.haal_documenten_op(folder_id="x")
    assert docs == []
    assert review[0]["reden"].startswith("Leesfout")


# Type-cast voor mypy zodat tests/typing klopt.
_ = Any
