"""Sheets-lezen via het org-service-account, zonder de `gws`-CLI.

Tegenhanger van `clients/google_drive.py`; zie die module voor het waarom. Functienamen
en returnshapes zijn gelijk aan de `gws_*`-varianten die ze vervangen, zodat de adapter
één importregel wisselt en de bestaande tests blijven gelden.

Gebruikt `auth.sheets_read_service()` — een aparte, alleen-lezen scope. `sheets_service()`
draagt `_WRITE_SCOPES` (inclusief mail en agenda) en hoort dus niet onder een read-only
bron te hangen.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from iso_audit import auth

logger = logging.getLogger("iso_audit.audit")


@lru_cache(maxsize=1)
def _dienst() -> Any:
    """Eén Sheets-service hergebruiken; zie `google_drive._dienst` voor het waarom.

    Hier weegt het extra: `sheets_lees_alle_tabs` doet één call per tab, en de
    auditplanning heeft zeven tabs.
    """
    return auth.sheets_read_service()


_MAX_RETRIES = 3

_STANDAARD_BEREIK = "A1:ZZ10000"
_TAB_BEREIK = "A1:AZ500"
"""Bereiken letterlijk gelijk aan de gws-variant: `sources/planning.py` parseert op
kolomindex, dus een ander bereik verschuift de kolommen."""


def sheets_lees_sheet(spreadsheet_id: str, bereik: str | None = None) -> list[list[Any]]:
    """Lees een bereik uit een Google Sheet.

    `bereik=None` leest het eerste blad volledig. Returnt een lijst rijen, elke rij een
    lijst cellen.
    """
    data = (
        _dienst()
        .spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=bereik or _STANDAARD_BEREIK)
        .execute(num_retries=_MAX_RETRIES)
    )
    values: list[list[Any]] = data.get("values", [])
    return values


def sheets_tabnamen(spreadsheet_id: str) -> list[str]:
    """De tabtitels van een spreadsheet.

    Met een `fields`-masker: zonder masker haalt `spreadsheets.get` álle bladmetadata op
    (opmaak, conditional formats, beschermde bereiken) voor een lijstje titels.
    """
    meta = (
        _dienst()
        .spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
        .execute(num_retries=_MAX_RETRIES)
    )
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def sheets_lees_alle_tabs(spreadsheet_id: str) -> dict[str, list[list[Any]]]:
    """Lees alle tabs — `{tab_naam: [[rij], ...]}`.

    Tabs die op een fout uitkomen worden overgeslagen en gelogd, niet geraised: één
    kapotte tab mag een auditplanning niet onleesbaar maken. Daarom ook per tab een
    losse `values.get` en geen `batchGet` — die faalt op de héle batch.
    """
    tabs = sheets_tabnamen(spreadsheet_id)
    resultaat: dict[str, list[list[Any]]] = {}
    overgeslagen: list[str] = []
    for tab in tabs:
        try:
            resultaat[tab] = sheets_lees_sheet(spreadsheet_id, f"'{tab}'!{_TAB_BEREIK}")
            logger.info("Tab '%s': %d rijen", tab, len(resultaat[tab]))
        except Exception as e:
            logger.warning("Tab '%s' overgeslagen: %s", tab, e)
            overgeslagen.append(tab)
    # Eén regel die zegt hoeveel van hoeveel er gelezen is. De per-tab-waarschuwingen
    # stonden er al, maar niemand telt waarschuwingen: op 2026-08-21 werd een planning half
    # gelezen door quotumfouten en meldde de run niets over die halve lezing. Zelfde
    # redenering als bij de Drive-dekking — wat je niet leest, moet je zeggen.
    if overgeslagen:
        logger.warning(
            "Planning-sheet: %d van %d tabs gelezen, %d overgeslagen (%s)",
            len(resultaat),
            len(tabs),
            len(overgeslagen),
            ", ".join(overgeslagen),
        )
    else:
        logger.info("Planning-sheet: alle %d tabs gelezen", len(tabs))
    return resultaat
