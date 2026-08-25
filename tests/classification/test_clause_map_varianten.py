"""De samengevoegde clause-map verliest geen enkele clausule meer.

`laad_clause_map("beide")` deed `{**map_9001, **map_27001}`. Achttien nummers bestaan in beide
normen, en daar won 27001: 103 ingangen waar er 121 horen. In een gecombineerde audit bestonden
die 18 ISO 9001-clausules simpelweg niet.

De sleutel blijft het clausulenummer — negen modules gebruiken die map en een andere sleutel
breekt ze allemaal. Wat erbij komt is `varianten`: per norm de eigen ingang. Zo is niets meer
weg, en een aanroeper die de norm kent kan de juiste titel opvragen.
"""

from __future__ import annotations

import pytest

from iso_audit.classification.clause_mapping import laad_clause_map, titel_voor


def test_de_samengevoegde_map_kent_beide_varianten() -> None:
    clausules = laad_clause_map("beide")["clausules"]
    varianten = clausules["7.5"]["varianten"]
    assert set(varianten) == {"9001", "27001"}


def test_de_titels_van_beide_normen_blijven_bestaan() -> None:
    """§7.5 is in 9001 "Gedocumenteerde informatie" en in 27001 iets heel anders."""
    varianten = laad_clause_map("beide")["clausules"]["7.5"]["varianten"]
    assert varianten["9001"]["titel"] != varianten["27001"]["titel"]
    assert "informatie" in varianten["9001"]["titel"].lower()


def test_een_nummer_in_een_norm_heeft_ook_een_variant() -> None:
    """Uniform: elke ingang heeft varianten, zodat niemand hoeft te vertakken."""
    varianten = laad_clause_map("beide")["clausules"]["8.24"]["varianten"]
    assert set(varianten) == {"27001"}


@pytest.mark.parametrize(
    ("clausule", "norm", "stukje"),
    [("7.5", "9001", "informatie"), ("8.24", "27001", "cryptograf")],
)
def test_titel_voor_geeft_de_juiste_norm(clausule: str, norm: str, stukje: str) -> None:
    assert stukje in titel_voor(clausule, norm).lower()


def test_titel_voor_valt_terug_op_het_nummer() -> None:
    """Een onbekende clausule levert het nummer op, geen lege string of een fout.

    Een lege titel in het rapport leest als een ontbrekende clausule; het nummer laat zien dat
    hij er is maar geen titel heeft."""
    assert titel_voor("99.9", "27001") == "99.9"


def test_de_map_van_een_enkele_norm_blijft_ongewijzigd() -> None:
    """Wie één norm draait, hoort niets van varianten te merken."""
    assert len(laad_clause_map("9001")["clausules"]) == 28
