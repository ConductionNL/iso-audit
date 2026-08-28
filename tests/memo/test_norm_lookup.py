"""Tests voor `iso_audit.memo.norm_lookup`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from iso_audit.memo.norm_lookup import (
    ClausuleOntbreektError,
    NormDatabaseError,
    laad_norm_db,
)


def _schrijf_db(directory: Path) -> None:
    doc = {
        "metadata": {"standard": "ISO 27001:2022", "slug": "iso-27001-2022", "source": "test"},
        "clauses": {
            "A.6.5": {
                "title_nl": "Verantwoordelijkheden na beëindiging",
                "title_en": "",
                "text_nl": "Verplichtingen die van kracht blijven na beëindiging ...",
                "text_en": "",
            }
        },
    }
    (directory / "iso-27001-2022.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")


def test_citation_resolvet_nl(tmp_path: Path) -> None:
    _schrijf_db(tmp_path)
    db = laad_norm_db(tmp_path)
    cit = db.citation("iso-27001-2022", "A.6.5", "nl")
    assert cit.clause == "A.6.5"
    assert "beëindiging" in cit.title
    assert cit.text.startswith("Verplichtingen")


def test_ontbrekende_clausule_hard_fail(tmp_path: Path) -> None:
    _schrijf_db(tmp_path)
    db = laad_norm_db(tmp_path)
    with pytest.raises(ClausuleOntbreektError, match="ontbreekt"):
        db.citation("iso-27001-2022", "9.9", "nl")


def test_ontbrekende_taal_hard_fail(tmp_path: Path) -> None:
    """EN-tekst is leeg → hard-fail (geen verzonnen/leeg citaat)."""
    _schrijf_db(tmp_path)
    db = laad_norm_db(tmp_path)
    with pytest.raises(ClausuleOntbreektError, match="en"):
        db.citation("iso-27001-2022", "A.6.5", "en")


def test_ontbrekende_standaard_hard_fail(tmp_path: Path) -> None:
    _schrijf_db(tmp_path)
    db = laad_norm_db(tmp_path)
    with pytest.raises(ClausuleOntbreektError):
        db.citation("iso-14001-2015", "A.6.5", "nl")


def test_lege_directory_faalt(tmp_path: Path) -> None:
    with pytest.raises(NormDatabaseError, match="Geen norm-bestanden"):
        laad_norm_db(tmp_path)


def test_niet_bestaande_directory_faalt(tmp_path: Path) -> None:
    with pytest.raises(NormDatabaseError):
        laad_norm_db(tmp_path / "bestaat-niet")


def test_voorbeeld_db_dekt_referentie_clausules() -> None:
    """De meegeleverde voorbeeld-DB resolvet de clausules die de referentie-memo citeert."""
    db = laad_norm_db("examples/norms")
    for standard, clause in [
        ("iso-9001-2015", "10.2"),
        ("iso-27001-2022", "A.6.5"),
        ("iso-27001-2022", "A.5.11"),
        ("iso-27001-2022", "A.5.18"),
        ("iso-27001-2022", "A.8.15"),
        ("iso-27001-2022", "A.8.16"),
    ]:
        cit = db.citation(standard, clause, "nl")
        assert cit.text  # niet leeg
