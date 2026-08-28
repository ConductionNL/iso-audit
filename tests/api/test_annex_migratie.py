"""Bestaande 27001-bevindingen verwijzen na de A-prefix nog naar de juiste maatregel.

Op 2026-08-28 kregen de Bijlage A-maatregelen de `A.`-prefix, zodat de managementclausules 4 t/m
10 erbij konden: §5.1 is "Leiderschap en betrokkenheid", A.5.1 is "Beleid voor
informatiebeveiliging". Zonder migratie zou een bestaande bevinding op `5.1` na de wijziging naar
de verkéérde clausule wijzen — en een bevinding die naar een andere eis verwijst dan waarop ze
is vastgesteld, is erger dan geen bevinding.

De migratie is eenduidig omdat er vóór deze wijziging niets anders bestond: élke 27001-clausule
in de opgeslagen gegevens was een Bijlage A-maatregel. Dat geldt eenmalig en niet meer zodra er
een run met de nieuwe nummering is geweest — vandaar dat de migratie alleen nummers zonder
prefix omzet die als maatregel bestaan, en alles wat al klopt met rust laat.

9001 blijft ongemoeid: die norm heeft geen Bijlage A.
"""

from __future__ import annotations

from iso_audit.api.annex_migratie import migreer_clausule


def test_een_oude_maatregel_krijgt_de_prefix() -> None:
    assert migreer_clausule("5.1", "27001") == "A.5.1"
    assert migreer_clausule("8.14", "27001") == "A.8.14"


def test_een_al_gemigreerde_clausule_blijft_staan() -> None:
    """Twee keer draaien mag niet A.A.5.1 opleveren."""
    assert migreer_clausule("A.5.1", "27001") == "A.5.1"


def test_een_managementclausule_die_geen_maatregel_is_blijft_staan() -> None:
    """4.1 bestaat niet in Bijlage A, dus er valt niets te migreren."""
    assert migreer_clausule("4.1", "27001") == "4.1"
    assert migreer_clausule("9.2", "27001") == "9.2"


def test_negenduizendeen_wordt_niet_aangeraakt() -> None:
    """ISO 9001 heeft geen Bijlage A; prefixen zou de clausule onvindbaar maken."""
    assert migreer_clausule("5.1", "9001") == "5.1"
    assert migreer_clausule("8.14", "9001") == "8.14"


def test_een_onbekend_nummer_blijft_zoals_het_is() -> None:
    """Liever een nummer dat niet bestaat dan een dat naar de verkeerde eis wijst."""
    assert migreer_clausule("99.9", "27001") == "99.9"


def test_elke_gemigreerde_clausule_bestaat_in_de_norm_db() -> None:
    """De hele reden van de migratie: na afloop moet elke verwijzing kloppen."""
    from pathlib import Path

    import yaml

    db = set(
        yaml.safe_load(Path("examples/norms/iso-27001-2022.yaml").read_text(encoding="utf-8"))[
            "clauses"
        ]
    )
    oud = [k[2:] for k in db if k.startswith("A.")]
    for nummer in oud:
        assert migreer_clausule(nummer, "27001") in db, nummer
