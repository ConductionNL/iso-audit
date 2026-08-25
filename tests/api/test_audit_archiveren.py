"""Een audit archiveren: uit het overzicht, niet van de schijf.

De vraag was "die eerdere runs moeten weg, en handig als die weggegooid kunnen worden". Wat een
auditor daarbij wil is een schone werklijst — niet het vernietigen van een dossier. Dat verschil
is hier het hele ontwerp:

- **Archiveren verplaatst, het verwijdert niet.** De map gaat naar `archief/<datum>/`, met alles
  erin. Een audit die is gedraaid is bewijs dat er een audit is gedraaid; dat weggooien maakt de
  volgende vraag ("wat is er in Q2 getoetst?") onbeantwoordbaar.
- **Wie het deed en waarom staat vast.** Zelfde regel als bij het verbergen van een run.
- **Een lopende audit gaat niet.** Halverwege een run de map verplaatsen levert een run op die
  in het niets schrijft.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from iso_audit.api.registry import AuditRegistry, RegistryError


def _registry(tmp_path: Path) -> AuditRegistry:
    return AuditRegistry(root=tmp_path / "audits")


def _maak(reg: AuditRegistry) -> str:
    return reg.maak(normen=["9001"], periode="2026-Q3", door="auditor@test")


def test_archiveren_haalt_de_audit_uit_de_lijst(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    aid = _maak(reg)

    reg.archiveer(aid, door="auditor@test", reden="oude proefaudit")

    assert not reg.bestaat(aid)


def test_de_map_blijft_bestaan_in_het_archief(tmp_path: Path) -> None:
    """Verplaatsen, niet vernietigen: een gedraaide audit is bewijs dát er geaudit is."""
    reg = _registry(tmp_path)
    aid = _maak(reg)
    (reg.pad(aid) / "findings.json").write_text('[{"id": "nc-1"}]', encoding="utf-8")

    doel = reg.archiveer(aid, door="auditor@test", reden="oude proefaudit")

    assert doel.is_dir()
    assert json.loads((doel / "findings.json").read_text())[0]["id"] == "nc-1"


def test_wie_en_waarom_worden_vastgelegd(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    aid = _maak(reg)

    doel = reg.archiveer(aid, door="mark@conduction.nl", reden="dubbel aangemaakt")

    spoor = json.loads((doel / "gearchiveerd.json").read_text(encoding="utf-8"))
    assert spoor["door"] == "mark@conduction.nl"
    assert spoor["reden"] == "dubbel aangemaakt"
    assert spoor["audit_id"] == aid


def test_een_reden_is_verplicht(tmp_path: Path) -> None:
    """Zonder reden is later niet te zeggen of het opruimen was of iets verbergen."""
    reg = _registry(tmp_path)
    aid = _maak(reg)

    with pytest.raises(RegistryError, match="reden"):
        reg.archiveer(aid, door="auditor@test", reden="   ")


def test_een_onbekende_audit_geeft_een_leesbare_fout(tmp_path: Path) -> None:
    reg = _registry(tmp_path)
    with pytest.raises(RegistryError, match="bestaat niet"):
        reg.archiveer("bestaat-niet", door="a@test", reden="x")


def test_twee_keer_archiveren_botst_niet(tmp_path: Path) -> None:
    """Een audit met dezelfde naam kan opnieuw worden aangemaakt en opnieuw gearchiveerd."""
    reg = _registry(tmp_path)
    eerste = reg.archiveer(_maak(reg), door="a@test", reden="x")
    tweede = reg.archiveer(_maak(reg), door="a@test", reden="y")
    assert eerste != tweede
    assert eerste.is_dir() and tweede.is_dir()
