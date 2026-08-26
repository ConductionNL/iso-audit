"""De vaste clausule-koppeling voor repository- en websitedocumenten.

`koppel_documenten` matcht Nederlandse normtermen op de documenttekst. Voor beleid en notulen
werkt dat; voor wat de nieuwe bronnen leveren niet. Een `SECURITY.md` is Engels en bevat geen
enkele zoekterm, maar is bewijs voor §8.8 vanwege *wat hij is*. "Branch-bescherming: niet
ingesteld" is de kern van §8.32 zonder één normterm.

De belangrijkste test hier is de eerste: elke gekoppelde clausule moet in de norm-DB bestaan. Een
koppeling naar een clausule die er niet is, levert een bevinding op die nergens over gaat — dat
is precies de fout die op 2026-08-24 448 van de 903 bevindingen verkeerd labelde.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from iso_audit.classification.bron_clausules import (
    alle_koppelingen,
    voor_repo_document,
    voor_webpagina,
)

_SLUG = {"27001": "iso-27001-2022", "9001": "iso-9001-2015"}


def _bestaande_clausules(norm: str) -> set[str]:
    ruw = yaml.safe_load(Path(f"examples/norms/{_SLUG[norm]}.yaml").read_text(encoding="utf-8"))
    return set(ruw["clauses"])


def test_elke_gekoppelde_clausule_bestaat_in_de_norm_db() -> None:
    """Een koppeling naar een niet-bestaande clausule is een bevinding over niets."""
    per_norm: dict[str, set[str]] = {}
    for clausule, norm in alle_koppelingen():
        per_norm.setdefault(norm, set()).add(clausule)
    for norm, clausules in per_norm.items():
        ontbreekt = clausules - _bestaande_clausules(norm)
        assert not ontbreekt, f"{norm}: {sorted(ontbreekt)} staan niet in de norm-DB"


def test_de_repository_instellingen_raken_toegang_en_wijzigingsbeheer() -> None:
    """Vier-ogen is een instelling op een branch, niet een zin in een handboek."""
    koppeling = voor_repo_document("instellingen")
    assert ("8.4", "27001") in koppeling
    assert ("8.32", "27001") in koppeling


def test_security_md_hangt_aan_kwetsbaarhedenbeheer() -> None:
    assert ("8.8", "27001") in voor_repo_document("SECURITY.md")


def test_codeowners_hangt_aan_rollen_en_wijzigingsbeheer() -> None:
    for pad in ("CODEOWNERS", ".github/CODEOWNERS"):
        koppeling = voor_repo_document(pad)
        assert ("5.2", "27001") in koppeling, pad
        assert ("8.32", "27001") in koppeling, pad


@pytest.mark.parametrize("pad", [".github/workflows/ci.yml", ".forgejo/workflows/test.yaml"])
def test_workflows_raken_ontwikkeling_scheiding_en_wijziging(pad: str) -> None:
    """Beide forges, want de mapnaam verschilt en de eis niet."""
    koppeling = voor_repo_document(pad)
    assert {("8.25", "27001"), ("8.31", "27001"), ("8.32", "27001")} == set(koppeling)


def test_een_onbekend_pad_levert_niets_op() -> None:
    """Liever geen koppeling dan een geraden koppeling; de zoektermen blijven draaien."""
    assert voor_repo_document("docs/handleiding.md") == ()


def test_de_privacyverklaring_hangt_aan_privacy() -> None:
    assert voor_webpagina("https://www.conduction.nl/privacy/") == (("5.34", "27001"),)


def test_een_subpagina_erft_de_koppeling() -> None:
    """`/privacy/` en `/privacy/cookies/` gaan over hetzelfde."""
    assert voor_webpagina("https://x.nl/privacy/cookies/") == (("5.34", "27001"),)


def test_de_voorwaardenpagina_raakt_beide_normen() -> None:
    """Een SLA is een contractuele eis (27001 §5.31) én een eis aan de dienst (9001 §8.2)."""
    koppeling = voor_webpagina("https://www.conduction.nl/terms/")
    assert ("5.31", "27001") in koppeling
    assert ("8.2", "9001") in koppeling


def test_een_gewone_pagina_krijgt_geen_koppeling() -> None:
    assert voor_webpagina("https://www.conduction.nl/academy/welcome/") == ()


def test_een_prefix_matcht_niet_halverwege_een_woord() -> None:
    """`/terms-and-tricks/` is geen voorwaardenpagina."""
    assert voor_webpagina("https://x.nl/terms-and-tricks/") == ()


# --- aangesloten op de koppeling --------------------------------------------


def _koppel(documenten: list[dict]) -> tuple[list[dict], list[dict]]:
    from iso_audit.classification.clause_mapping import koppel_alle_normen

    return koppel_alle_normen(documenten, "beide")


def test_een_security_md_zonder_normtermen_valt_niet_buiten_de_boot() -> None:
    """Dit is de hele reden dat de vaste koppeling bestaat.

    De zoektermen zijn Nederlands; `SECURITY.md` is Engels en zou zonder dit als
    niet-geclassificeerd wegvallen — terwijl hij bewijs is voor §8.8 vanwege wát hij is.
    """
    doc = {
        "id": "github:ConductionNL/iso-audit#SECURITY.md",
        "naam": "SECURITY.md",
        "herkomst": "Repo",
        "tekst": "Please report vulnerabilities to security@example.org.",
    }
    gekoppeld, niet = _koppel([doc])
    assert not niet
    assert ("8.8", "27001") in gekoppeld[0]["clausule_normen"]


def test_de_repository_instellingen_landen_op_wijzigingsbeheer() -> None:
    doc = {
        "id": "github:ConductionNL/iso-audit#instellingen",
        "naam": "instellingen",
        "herkomst": "Repo",
        "tekst": "Branch-bescherming op de hoofdbranch: niet ingesteld.",
    }
    gekoppeld, _ = _koppel([doc])
    assert ("8.32", "27001") in gekoppeld[0]["clausule_normen"]
    assert ("8.4", "27001") in gekoppeld[0]["clausule_normen"]


def test_een_webpagina_landt_op_zijn_eis() -> None:
    doc = {
        "id": "https://www.conduction.nl/privacy/",
        "naam": "/privacy/",
        "herkomst": "Website",
        "tekst": "Privacy statement.",
    }
    gekoppeld, _ = _koppel([doc])
    assert ("5.34", "27001") in gekoppeld[0]["clausule_normen"]


def test_de_zoektermen_blijven_gewoon_draaien() -> None:
    """De vaste koppeling komt erbij, niet in plaats van. Een SECURITY.md die over back-ups
    gaat, krijgt die clausule er gewoon bij."""
    doc = {
        "id": "github:x/y#SECURITY.md",
        "naam": "SECURITY.md",
        "herkomst": "Repo",
        "tekst": "Dit document beschrijft ook de back-up en het continuïteitsplan.",
    }
    gekoppeld, _ = _koppel([doc])
    ids = {cid for cid, _ in gekoppeld[0]["clausule_normen"]}
    assert "8.8" in ids, "vaste koppeling ontbreekt"
    assert len(ids) > 1, f"zoektermen leverden niets extra's: {ids}"


def test_andere_bronnen_krijgen_geen_vaste_koppeling() -> None:
    """Drive en Jira leveren lopende tekst; daar zijn de zoektermen voor gemaakt."""
    doc = {"id": "d1", "naam": "SECURITY.md", "herkomst": "Drive", "tekst": "niets herkenbaars"}
    gekoppeld, niet = _koppel([doc])
    assert not gekoppeld and len(niet) == 1
