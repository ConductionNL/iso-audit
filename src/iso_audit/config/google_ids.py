"""Een Google-ID uit een geplakte URL halen.

## Waarom dit bestaat

De velden "Map-ID van de auditmap" en "Spreadsheet-ID van de planning" vragen een ID, maar
in de praktijk plakt iedereen de URL uit de adresbalk — dat is wat je hebt als je in Drive
staat. Gemeten op 2026-08-14: beide waarden waren volledige URL's, één via de UI ingevuld
en één uit een omgevingsbestand. De API krijgt dan een "ID" van 80 tekens en antwoordt met
404, wat in de UI verschijnt als "bestaat niet of is niet gedeeld met dit account". Die
melding stuurt iemand naar het deelbeleid terwijl er niets mis is met de rechten.

Weigeren zou ook kunnen, maar dat is hier de slechtere keus: de URL bevat het ID gewoon,
en een tool dat "ik zie wat je bedoelt maar doe het niet" zegt is onnodig streng op een
plek waar de bedoeling niet ambigu is.

## Bewust smal

Alleen de vier vormen die Drive en Sheets zelf produceren, elk expliciet. Geen generieke
"pak de langste tekenreeks"-heuristiek: die zou bij een onbekende URL-vorm stil het
verkeerde deel pakken, en dan is de foutmelding verderop weer misleidend. Wat niet matcht
gaat ongewijzigd door — dan is het al een ID, of het is iets dat de API hoort af te wijzen.
"""

from __future__ import annotations

import re

_PATRONEN: tuple[re.Pattern[str], ...] = (
    # https://drive.google.com/drive/folders/<id>
    re.compile(r"/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)"),
    # https://docs.google.com/spreadsheets/d/<id>/edit  (idem document, presentation)
    re.compile(r"/(?:spreadsheets|document|presentation|file)/d/([A-Za-z0-9_-]+)"),
    # https://drive.google.com/open?id=<id>
    re.compile(r"[?&]id=([A-Za-z0-9_-]+)"),
)


def uit_url(waarde: str) -> str:
    """Geef het Google-ID uit `waarde`; is het al een ID, geef het ongewijzigd terug.

    >>> uit_url("https://drive.google.com/drive/folders/0ABC-def?hl=nl")
    '0ABC-def'
    >>> uit_url("https://docs.google.com/spreadsheets/d/1XYZ/edit?usp=drive_web&ouid=1")
    '1XYZ'
    >>> uit_url("0ABC-def")
    '0ABC-def'
    """
    schoon = waarde.strip()
    if "://" not in schoon:
        # Geen URL. Wel de losse query-staart afknippen die soms aan een gekopieerd ID
        # blijft hangen; dat deed `sources/drive.py:_split_ids` al.
        return schoon.split("?")[0].strip()
    for patroon in _PATRONEN:
        gevonden = patroon.search(schoon)
        if gevonden:
            return gevonden.group(1)
    return schoon
