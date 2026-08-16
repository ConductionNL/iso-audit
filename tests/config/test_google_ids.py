"""Tests voor `config/google_ids.py`.

De invoer hieronder zijn de **echt gemeten** waarden van 2026-08-14: een Shared-Drive-URL
die een auditor deelde, en de Sheets-URL die in een omgevingsbestand stond. Geen verzonnen
strings — dat is precies het verschil tussen een gate die vangt en een gate die lijkt te
vangen.
"""

from __future__ import annotations

import pytest

from iso_audit.config.google_ids import uit_url

# Zoals gemeten in de configuratie van het portaal op 2026-08-14.
_ECHTE_DRIVE_URL = "https://drive.google.com/drive/folders/1YJoG0i-DmPoOHHNE7LqGtaZr9FCjxRm9"
_ECHTE_SHEETS_URL = (
    "https://docs.google.com/spreadsheets/d/1BV2yajU7tQWU4dJPGc79V-mnH_-bQWCHKzhcU7XY37A"
    "/edit?usp=drive_web&ouid=101148019356761389932"
)


@pytest.mark.parametrize(
    ("invoer", "verwacht"),
    [
        (_ECHTE_DRIVE_URL, "1YJoG0i-DmPoOHHNE7LqGtaZr9FCjxRm9"),
        (_ECHTE_SHEETS_URL, "1BV2yajU7tQWU4dJPGc79V-mnH_-bQWCHKzhcU7XY37A"),
        # Shared Drive uit de deel-link, met taalparameter.
        ("https://drive.google.com/drive/folders/0AAPHjn2R39GWUk9PVA?hl=nl", "0AAPHjn2R39GWUk9PVA"),
        # Account-specifieke vorm die Drive geeft als je meerdere accounts hebt.
        ("https://drive.google.com/drive/u/0/folders/0ABC-def_1", "0ABC-def_1"),
        ("https://drive.google.com/open?id=1XYZ-abc", "1XYZ-abc"),
        ("https://docs.google.com/document/d/1DOC-id/edit", "1DOC-id"),
        # Al een ID: ongewijzigd doorlaten.
        ("0AAPHjn2R39GWUk9PVA", "0AAPHjn2R39GWUk9PVA"),
        ("  1BV2yaj  ", "1BV2yaj"),
        # Losse query-staart aan een gekopieerd ID; deed `_split_ids` al.
        ("1BV2yaj?usp=sharing", "1BV2yaj"),
    ],
)
def test_herleidt_naar_het_id(invoer: str, verwacht: str) -> None:
    assert uit_url(invoer) == verwacht


def test_onbekende_url_gaat_ongewijzigd_door() -> None:
    """Geen "pak de langste tekenreeks"-heuristiek: die pakt bij een onbekende vorm stil
    het verkeerde deel, en dan is de foutmelding verderop opnieuw misleidend."""
    vreemd = "https://example.invalid/iets/anders"
    assert uit_url(vreemd) == vreemd


def test_de_gemeten_urls_gaven_zonder_herleiding_een_ander_resultaat() -> None:
    """Aantoonbaar dat dit een echt verschil maakt en geen no-op is."""
    for url in (_ECHTE_DRIVE_URL, _ECHTE_SHEETS_URL):
        assert uit_url(url) != url
        assert "/" not in uit_url(url)
