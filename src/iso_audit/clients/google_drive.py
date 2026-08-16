"""Drive-lezen via het org-service-account, zonder de `gws`-CLI.

## Waarom deze module bestaat

`clients/gws.py` roept de `gws`-CLI aan met `subprocess`, en die CLI authenticeert met
een **persoonlijke** OAuth-sessie (`gws auth login`). Daarmee hing de auditcapability aan
één medewerker, en stond de binary bovendien niet in het container-image — Drive kon in
het cluster dus helemaal niet werken.

Deze module doet dezelfde vier dingen via `google-api-python-client`, met de credentials
uit `iso_audit.auth` (service-account-keyfile). Geen binary, geen persoonlijke sessie.

## Vorm bewust gelijk gehouden

De functies hebben dezelfde parameters en returnshapes als hun `gws_*`-tegenhangers. Dat
is geen toeval maar het migratieplan: de adapters wisselen daardoor één importregel, en
de bestaande tests in `tests/sources/` — die deze functies bij naam patchen — blijven
inhoudelijk gelijk. Zo bewijst de bestaande suite dat het gedrag niet verschoof.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from iso_audit import auth

logger = logging.getLogger("iso_audit.audit")


@lru_cache(maxsize=1)
def _dienst() -> Any:
    """Eén Drive-service hergebruiken binnen dit proces.

    Niet om het bouwen te sparen — dat kost 0,07s — maar om de **token-uitwisseling**.
    Gemeten: de eerste API-call op een vers credentials-object kostte 33s, een volgende
    call op hetzelfde object 0,48s. Een nieuwe service per document zou die eerste kost
    per document opnieuw betalen.

    `google-auth` verlengt het token zelf op het credentials-object, dus hergebruik is
    veilig. Tests roepen `_dienst.cache_clear()` zodat een gestubde service niet
    doorlekt naar de volgende test.
    """
    return auth.drive_read_service()


_MAX_RETRIES = 3
"""Meegegeven aan `execute()`. De client retryt zelf op 5xx, 429 en op een 403 met
`rateLimitExceeded` — dat dekt de gevallen waarvoor `clients/gws.py` een eigen
retry-lus had. Eén getal, één plek."""

_MAP_MIME = "application/vnd.google-apps.folder"

_LIJST_VELDEN = "nextPageToken, files(id, name, mimeType, modifiedTime)"


def _lijst_params(folder_id: str, drive_id: str | None) -> dict[str, Any]:
    """Query-parameters voor één `files.list`-pagina.

    De `q`-string blijft letterlijk zoals `clients/gws.py` hem bouwde: de recursie en de
    dedup in `sources/drive.py` hangen aan deze semantiek.
    """
    params: dict[str, Any] = {
        "q": f"'{folder_id}' in parents and trashed=false",
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
    }
    if drive_id:
        # Alleen zetten als er een Shared Drive in het spel is; een lege `driveId`
        # levert een 400.
        params["corpora"] = "drive"
        params["driveId"] = drive_id
    return params


def drive_lijst_bestanden(folder_id: str, drive_id: str | None = None) -> list[dict[str, Any]]:
    """Lijst recursief alle bestanden in `folder_id`.

    Ondersteunt reguliere Drive-mappen en Shared Drives (`0A...`-IDs). Returnt
    `{id, name, mimeType, modifiedTime}` per bestand; submappen worden gevolgd, de
    submap-records zelf komen niet mee.
    """
    return _lijst_recursief(_dienst(), folder_id, drive_id)


def _lijst_recursief(service: Any, folder_id: str, drive_id: str | None) -> list[dict[str, Any]]:
    """Recursie op één service-object, zodat er per aanroep één credential-uitwisseling is."""
    alle: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        params = _lijst_params(folder_id, drive_id)
        params["fields"] = _LIJST_VELDEN
        params["pageSize"] = 100
        if page_token:
            params["pageToken"] = page_token

        result = service.files().list(**params).execute(num_retries=_MAX_RETRIES)
        for bestand in result.get("files", []):
            if bestand["mimeType"] == _MAP_MIME:
                alle.extend(_lijst_recursief(service, bestand["id"], drive_id))
            else:
                alle.append(bestand)

        page_token = result.get("nextPageToken")
        if not page_token:
            return alle


def drive_bereikbaar(folder_id: str, drive_id: str | None = None) -> None:
    """Lichte reachability-probe: één niet-recursieve `files.list` (pageSize=1).

    Bewijst dat de credential werkt én de map bereikbaar is, zonder de map recursief te
    enumereren — dat laatste kan minuten duren en hoort niet in een healthcheck.

    :raises: propageert de onderliggende API-fout als de probe faalt.
    """
    params = _lijst_params(folder_id, drive_id)
    params["fields"] = "files(id)"
    params["pageSize"] = 1
    _dienst().files().list(**params).execute(num_retries=_MAX_RETRIES)


def drive_exporteer_google_doc(file_id: str) -> str:
    """Exporteer een Google Doc als plain text.

    `files.export` kent **geen** `supportsAllDrives`-parameter — die hoort bij de
    `files`-collectie, niet bij export. De `gws`-CLI slikte hem; de python-client raist
    erop. Export van een Doc in een Shared Drive werkt zonder die vlag. Niet
    "terugrepareren".
    """
    ruw: bytes = (
        _dienst()
        .files()
        .export_media(fileId=file_id, mimeType="text/plain")
        .execute(num_retries=_MAX_RETRIES)
    )
    return ruw.decode("utf-8", errors="replace")


def drive_download_bestand(file_id: str) -> bytes:
    """Download een bestand (`.docx`, `.txt`, en andere niet-Google-native formaten)."""
    ruw: bytes = (
        _dienst()
        .files()
        .get_media(fileId=file_id, supportsAllDrives=True)
        .execute(num_retries=_MAX_RETRIES)
    )
    return ruw
