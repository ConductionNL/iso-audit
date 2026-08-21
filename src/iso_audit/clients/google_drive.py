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

_SNELKOPPELING_MIME = "application/vnd.google-apps.shortcut"

_LIJST_VELDEN = (
    "nextPageToken, files(id, name, mimeType, modifiedTime, "
    "shortcutDetails(targetId, targetMimeType))"
)
"""`shortcutDetails` hoort erbij sinds 2026-08-18. Zonder die velden kwam een
snelkoppeling binnen als een bestand met mime `…google-apps.shortcut` en zonder enig
spoor naar waar hij heen wees; de source-laag liet er 29 stil vallen."""


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
    submap-records zelf komen niet mee. Snelkoppelingen worden opgelost naar hun doel.
    """
    return _lijst_recursief(_dienst(), folder_id, drive_id)


def _volg_snelkoppeling(service: Any, snelkoppeling: dict[str, Any]) -> dict[str, Any] | None:
    """Los een Drive-snelkoppeling op naar het record van het doelbestand, of `None`.

    Bewust een extra `files.get` in plaats van het snelkoppeling-record hergebruiken met
    `targetMimeType` erin geplakt: naam en `modifiedTime` van een snelkoppeling zijn die
    van de snelkoppeling, niet van het document. Dat laatste is niet cosmetisch — het
    leeftijdsfilter in de pipeline (2 jaar) beslist op `modifiedTime`, en dan zou een oud
    document via een verse snelkoppeling als actueel doorgaan, of een actueel document via
    een oude snelkoppeling als gearchiveerd wegvallen.

    Lukt de `get` niet, dan is dat geen reden om te raden: de caller houdt het
    snelkoppeling-record, en de source-laag meldt hem als niet-gevolgd.
    """
    doel_id = (snelkoppeling.get("shortcutDetails") or {}).get("targetId")
    naam = str(snelkoppeling.get("name", "(zonder naam)"))
    if not doel_id:
        logger.warning(
            "Snelkoppeling '%s' wijst nergens naar; Drive geeft geen doelbestand terug. "
            "Het blijft buiten het landschap en staat in de handmatige review.",
            naam,
        )
        return None
    try:
        doel: dict[str, Any] = (
            service.files()
            .get(
                fileId=doel_id,
                fields="id, name, mimeType, modifiedTime",
                supportsAllDrives=True,
            )
            .execute(num_retries=_MAX_RETRIES)
        )
    except Exception:
        # Leesbaar Nederlands en geen JSON-gebeurtenis: deze regel komt via de
        # voortgangs-handler in `api/run_job.py` in het portaal terecht, dus een auditor
        # leest hem. `{"event": "drive_snelkoppeling_niet_gevolgd"}` met een ruw bestand-ID
        # erachter zei niet wat er aan de hand was en klonk alarmerender dan het is.
        logger.warning(
            "Snelkoppeling '%s' kon niet gevolgd worden: het doelbestand bestaat niet meer, "
            "staat in de prullenbak, of is niet gedeeld met het service-account. Het blijft "
            "buiten het landschap en staat in de handmatige review (doel-id %s).",
            naam,
            doel_id,
        )
        return None
    return doel


def _lijst_recursief(
    service: Any,
    folder_id: str,
    drive_id: str | None,
    bezocht: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Recursie op één service-object, zodat er per aanroep één credential-uitwisseling is.

    `bezocht` houdt de al bezochte mappen bij. Dat was niet nodig zolang alleen echte
    submappen werden gevolgd — een mapboom heeft geen cycli — maar een snelkoppeling naar
    een bovenliggende map wél, en die volgen we sinds 2026-08-18.
    """
    if bezocht is None:
        bezocht = {folder_id}
    alle: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        params = _lijst_params(folder_id, drive_id)
        params["fields"] = _LIJST_VELDEN
        params["pageSize"] = 100
        if page_token:
            params["pageToken"] = page_token

        result = service.files().list(**params).execute(num_retries=_MAX_RETRIES)
        for gevonden in result.get("files", []):
            bestand = gevonden
            if bestand["mimeType"] == _SNELKOPPELING_MIME:
                doel = _volg_snelkoppeling(service, bestand)
                if doel is None:
                    # Niet stil laten vallen: het snelkoppeling-record gaat mee, en de
                    # source-laag meldt hem bij de dekking als niet-gevolgd.
                    alle.append(bestand)
                    continue
                bestand = doel
            if bestand["mimeType"] == _MAP_MIME:
                if bestand["id"] in bezocht:
                    continue
                bezocht.add(bestand["id"])
                alle.extend(_lijst_recursief(service, bestand["id"], drive_id, bezocht))
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


_TELLING_PAGE_SIZE = 100
"""Eén pagina volstaat voor de statusregel: het gaat om "staat hier iets in", niet om een
exact totaal. Een recursieve telling over een Shared Drive kost minuten (gemeten: 2,5
minuut voor 409 documenten) en het configuratiescherm opent bij elke pageload."""


def drive_inhoud_telling(folder_id: str, drive_id: str | None = None) -> tuple[int, bool]:
    """Tel niet-recursief wat er direct in een locatie staat.

    Returnt ``(aantal_bestanden, heeft_submappen)`` over **één** pagina. Beide zijn nodig
    om "leeg" van "alleen submappen" te onderscheiden: een map met uitsluitend submappen
    levert nul bestanden op, en die mag niet als lege locatie worden weggezet terwijl een
    recursieve run er wél documenten uit haalt.

    Het aantal is begrensd door de pagegrootte en dus een ondergrens, niet een totaal — de
    UI benoemt dat. Bewust geen `nextPageToken`-lus: die maakt van een statusregel weer een
    enumeratie.

    :raises: propageert de onderliggende API-fout.
    """
    params = _lijst_params(folder_id, drive_id)
    params["fields"] = "files(id, mimeType)"
    params["pageSize"] = _TELLING_PAGE_SIZE
    result = _dienst().files().list(**params).execute(num_retries=_MAX_RETRIES)
    bestanden = result.get("files", [])
    aantal = sum(1 for b in bestanden if b.get("mimeType") != _MAP_MIME)
    submappen = any(b.get("mimeType") == _MAP_MIME for b in bestanden)
    return aantal, submappen


def drive_locatie_info(locatie_id: str) -> dict[str, str] | None:
    """Naam en soort van één Drive-locatie, of ``None`` als dat niet lukt.

    Geeft ``{"id", "naam", "mime"}``. Bewust **niet** raisen: de naam is comfort in het
    configuratiescherm, geen voorwaarde om te kunnen lezen. Een locatie waarvan we de naam
    niet krijgen maar die wel bestanden oplevert is gewoon bruikbaar, en dan hoort de UI
    het ID te tonen in plaats van de rij als kapot te melden.

    De `mimeType` is het enige dat "lege map" van "dit is een bestand" onderscheidt: op
    `'<bestand-id>' in parents` antwoordt de API met een lege lijst en status 200, precies
    zoals bij een echt lege map.
    """
    try:
        info = (
            _dienst()
            .files()
            .get(fileId=locatie_id, fields="id, name, mimeType", supportsAllDrives=True)
            .execute(num_retries=_MAX_RETRIES)
        )
    except Exception:
        logger.warning(
            '{"event": "drive_locatie_onbekend", "reden": "naam niet op te halen"}',
        )
        return None
    return {
        "id": str(info.get("id", locatie_id)),
        "naam": str(info.get("name", "")),
        "mime": str(info.get("mimeType", "")),
    }


def is_map_mime(mime: str) -> bool:
    """Is dit MIME-type een Drive-map? Eén plek, zodat de constante niet gaat rondzwerven."""
    return mime == _MAP_MIME


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


def drive_exporteer_bytes(file_id: str, mime: str) -> bytes:
    """Exporteer een Google-native bestand naar `mime` en geef de ruwe bytes terug.

    Nodig voor de formaten waar de tekst niet uit een `text/plain`-export komt: een Google
    Sheet exporteert als CSV alleen het **eerste** blad, en dat is precies de stille
    onvolledigheid die deze change weghaalt. Als `.xlsx` komen alle bladen mee, en de
    xlsx-lezer die er al is doet de rest.

    Zelfde regel als bij `drive_exporteer_google_doc`: géén `supportsAllDrives` — die hoort
    bij de `files`-collectie, niet bij export.
    """
    ruw: bytes = (
        _dienst()
        .files()
        .export_media(fileId=file_id, mimeType=mime)
        .execute(num_retries=_MAX_RETRIES)
    )
    return ruw


def drive_download_bestand(file_id: str) -> bytes:
    """Download een bestand (`.docx`, `.txt`, en andere niet-Google-native formaten)."""
    ruw: bytes = (
        _dienst()
        .files()
        .get_media(fileId=file_id, supportsAllDrives=True)
        .execute(num_retries=_MAX_RETRIES)
    )
    return ruw
