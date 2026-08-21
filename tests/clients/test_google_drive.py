"""Tests voor `clients/google_drive.py` — de service-account-vervanger van de gws-CLI.

Deze tests dekken drie dingen die in de gws-variant nooit getest zijn: paginatie,
recursie in submappen, en welke parameters er per call meegaan. Dat laatste is geen
detail: `files.export` kent géén `supportsAllDrives` (de CLI slikte hem, de python-client
raist erop), en `corpora`/`driveId` mogen alleen mee bij een Shared Drive.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from iso_audit.clients import google_drive as gd

_MAP = "application/vnd.google-apps.folder"


class _Call:
    """Onthoudt de kwargs en geeft een vastgezet antwoord terug."""

    def __init__(self, opnames: list[dict[str, Any]], antwoord: Any) -> None:
        self._opnames = opnames
        self._antwoord = antwoord

    def execute(self, **kwargs: Any) -> Any:
        self._opnames[-1]["execute_kwargs"] = kwargs
        if isinstance(self._antwoord, Exception):
            raise self._antwoord
        return self._antwoord


class _Files:
    def __init__(self, opnames: list[dict[str, Any]], antwoorden: list[Any]) -> None:
        self._opnames = opnames
        self._antwoorden = antwoorden

    def _volgende(self, methode: str, kwargs: dict[str, Any]) -> _Call:
        self._opnames.append({"methode": methode, **kwargs})
        antwoord = self._antwoorden.pop(0) if self._antwoorden else {}
        return _Call(self._opnames, antwoord)

    def list(self, **kwargs: Any) -> _Call:
        return self._volgende("list", kwargs)

    def export_media(self, **kwargs: Any) -> _Call:
        return self._volgende("export_media", kwargs)

    def get_media(self, **kwargs: Any) -> _Call:
        return self._volgende("get_media", kwargs)

    def get(self, **kwargs: Any) -> _Call:
        return self._volgende("get", kwargs)


class _Service:
    def __init__(self, opnames: list[dict[str, Any]], antwoorden: list[Any]) -> None:
        self._files = _Files(opnames, antwoorden)

    def files(self) -> _Files:
        return self._files


@pytest.fixture
def dienst():  # type: ignore[no-untyped-def]
    """Geef `(opnames, zet_antwoorden)` en patch `auth.drive_read_service`."""
    opnames: list[dict[str, Any]] = []
    antwoorden: list[Any] = []

    def maak() -> _Service:
        return _Service(opnames, antwoorden)

    gd._dienst.cache_clear()
    with patch.object(gd.auth, "drive_read_service", side_effect=maak):
        yield opnames, antwoorden
    gd._dienst.cache_clear()


def test_lijst_pagineert_door(dienst: Any) -> None:
    """Zonder `nextPageToken`-lus mist een auditmap met >100 bestanden stil documenten."""
    opnames, antwoorden = dienst
    antwoorden.extend(
        [
            {"files": [{"id": "a", "name": "A", "mimeType": "text/plain"}], "nextPageToken": "p2"},
            {"files": [{"id": "b", "name": "B", "mimeType": "text/plain"}]},
        ]
    )

    uit = gd.drive_lijst_bestanden("map1")

    assert [b["id"] for b in uit] == ["a", "b"]
    assert opnames[1]["pageToken"] == "p2"
    assert "pageToken" not in opnames[0]


def test_lijst_volgt_submappen_en_laat_de_map_zelf_weg(dienst: Any) -> None:
    opnames, antwoorden = dienst
    antwoorden.extend(
        [
            {
                "files": [
                    {"id": "sub", "name": "Submap", "mimeType": _MAP},
                    {"id": "a", "name": "A", "mimeType": "text/plain"},
                ]
            },
            {"files": [{"id": "c", "name": "C", "mimeType": "text/plain"}]},
        ]
    )

    uit = gd.drive_lijst_bestanden("map1")

    assert [b["id"] for b in uit] == ["c", "a"], "submap-inhoud erbij, de map zelf niet"
    assert opnames[1]["q"] == "'sub' in parents and trashed=false"


def test_shared_drive_parameters_alleen_bij_een_drive_id(dienst: Any) -> None:
    """Een lege `driveId` levert een 400; daarom alleen zetten als er een drive is."""
    opnames, antwoorden = dienst
    antwoorden.extend([{"files": []}, {"files": []}])

    gd.drive_lijst_bestanden("map1")
    assert "driveId" not in opnames[0] and "corpora" not in opnames[0]

    gd.drive_lijst_bestanden("0ABC", drive_id="0ABC")
    assert opnames[1]["driveId"] == "0ABC"
    assert opnames[1]["corpora"] == "drive"
    assert opnames[1]["includeItemsFromAllDrives"] is True
    assert opnames[1]["supportsAllDrives"] is True


def test_export_krijgt_geen_supports_all_drives(dienst: Any) -> None:
    """`files.export` heeft die parameter niet. Dit is de gate tegen 'terugrepareren'."""
    opnames, antwoorden = dienst
    antwoorden.append(b"platte tekst")

    uit = gd.drive_exporteer_google_doc("doc1")

    assert uit == "platte tekst"
    assert opnames[0]["methode"] == "export_media"
    assert "supportsAllDrives" not in opnames[0]
    assert opnames[0]["mimeType"] == "text/plain"


def test_download_krijgt_wel_supports_all_drives(dienst: Any) -> None:
    """`files.get` kent hem wél — anders is een bestand in een Shared Drive onvindbaar."""
    opnames, antwoorden = dienst
    antwoorden.append(b"\x00binair")

    assert gd.drive_download_bestand("f1") == b"\x00binair"
    assert opnames[0]["methode"] == "get_media"
    assert opnames[0]["supportsAllDrives"] is True


def test_probe_is_bounded(dienst: Any) -> None:
    """De probe mag de map niet enumereren; dat is wat `healthcheck()` doet."""
    opnames, antwoorden = dienst
    antwoorden.append({"files": []})

    gd.drive_bereikbaar("map1")

    assert opnames[0]["pageSize"] == 1
    assert opnames[0]["fields"] == "files(id)"


def test_retries_worden_meegegeven(dienst: Any) -> None:
    """De eigen retry-lus uit de gws-variant is vervangen door `num_retries`."""
    opnames, antwoorden = dienst
    antwoorden.append({"files": []})

    gd.drive_bereikbaar("map1")

    assert opnames[0]["execute_kwargs"]["num_retries"] == gd._MAX_RETRIES


# ---------- locatie-info en inhoudstelling (statusregel in het configuratiescherm) ----------


def test_locatie_info_geeft_naam_en_mime(dienst: Any) -> None:
    opnames, antwoorden = dienst
    antwoorden.append({"id": "map1", "name": "Interne audits", "mimeType": gd._MAP_MIME})

    uit = gd.drive_locatie_info("map1")

    assert uit == {"id": "map1", "naam": "Interne audits", "mime": gd._MAP_MIME}
    assert opnames[0]["methode"] == "get"
    assert opnames[0]["supportsAllDrives"] is True


def test_locatie_info_faalt_zacht(dienst: Any) -> None:
    """De naam is comfort, geen voorwaarde — een fout mag de rij niet onbruikbaar maken."""
    _, antwoorden = dienst
    antwoorden.append(RuntimeError("404 not found"))

    assert gd.drive_locatie_info("weg") is None


def test_telling_scheidt_bestanden_van_submappen(dienst: Any) -> None:
    """Nul bestanden met submappen is iets anders dan leeg: recursief leest die wél."""
    _, antwoorden = dienst
    antwoorden.append(
        {
            "files": [
                {"id": "a", "mimeType": "text/plain"},
                {"id": "b", "mimeType": gd._MAP_MIME},
                {"id": "c", "mimeType": "application/pdf"},
            ]
        }
    )

    aantal, submappen = gd.drive_inhoud_telling("map1")

    assert (aantal, submappen) == (2, True)


def test_telling_lege_map(dienst: Any) -> None:
    _, antwoorden = dienst
    antwoorden.append({"files": []})

    assert gd.drive_inhoud_telling("map1") == (0, False)


def test_telling_pagineert_niet_door(dienst: Any) -> None:
    """Eén pagina volstaat; doorpagineren maakt van een statusregel weer een enumeratie."""
    opnames, antwoorden = dienst
    antwoorden.extend(
        [
            {"files": [{"id": "a", "mimeType": "text/plain"}], "nextPageToken": "p2"},
            {"files": [{"id": "b", "mimeType": "text/plain"}]},
        ]
    )

    aantal, _ = gd.drive_inhoud_telling("map1")

    assert aantal == 1
    assert len(opnames) == 1
    assert "pageToken" not in opnames[0]


# --- snelkoppelingen -------------------------------------------------------
#
# 29 snelkoppelingen werden overgeslagen omdat `shortcutDetails` niet in de veldenlijst stond.
# Ze wijzen naar echte documenten, en ze maken de voor de hand liggende workaround — een map
# met snelkoppelingen naar de relevante stukken — stil onbruikbaar.

_SNELKOPPELING = "application/vnd.google-apps.shortcut"


def test_veldenlijst_vraagt_shortcut_details(dienst: Any) -> None:
    """Zonder deze velden is er geen spoor naar waar een snelkoppeling heen wijst."""
    _, antwoorden = dienst
    antwoorden.append({"files": []})

    gd.drive_lijst_bestanden("map1")

    assert "shortcutDetails(targetId, targetMimeType)" in gd._LIJST_VELDEN


def test_snelkoppeling_wordt_gevolgd_naar_het_doel(dienst: Any) -> None:
    """Naam én `modifiedTime` komen van het doel: het leeftijdsfilter beslist daarop."""
    opnames, antwoorden = dienst
    antwoorden.extend(
        [
            {
                "files": [
                    {
                        "id": "kort",
                        "name": "link naar VvT",
                        "mimeType": _SNELKOPPELING,
                        "modifiedTime": "2026-08-01T00:00:00Z",
                        "shortcutDetails": {
                            "targetId": "echt",
                            "targetMimeType": "application/pdf",
                        },
                    }
                ]
            },
            {
                "id": "echt",
                "name": "VvT Conduction ISO 27001.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2024-03-03T00:00:00Z",
            },
        ]
    )

    uit = gd.drive_lijst_bestanden("map1")

    assert [b["id"] for b in uit] == ["echt"]
    assert uit[0]["name"] == "VvT Conduction ISO 27001.pdf"
    assert uit[0]["modifiedTime"] == "2024-03-03T00:00:00Z"
    assert opnames[1]["methode"] == "get" and opnames[1]["fileId"] == "echt"


def test_snelkoppeling_zonder_bereikbaar_doel_valt_niet_stil(dienst: Any) -> None:
    """Een doel dat niet op te halen is, blijft als snelkoppeling in de lijst; de source-laag
    meldt hem bij de dekking. Weglaten zou hetzelfde stille gat opnieuw maken."""
    _, antwoorden = dienst
    antwoorden.extend(
        [
            {
                "files": [
                    {
                        "id": "kort",
                        "name": "link",
                        "mimeType": _SNELKOPPELING,
                        "shortcutDetails": {"targetId": "weg"},
                    }
                ]
            },
            RuntimeError("404"),
        ]
    )

    uit = gd.drive_lijst_bestanden("map1")

    assert [b["id"] for b in uit] == ["kort"]
    assert uit[0]["mimeType"] == _SNELKOPPELING


def test_snelkoppeling_naar_map_wordt_gevolgd_zonder_lus(dienst: Any) -> None:
    """Een mapboom heeft geen cycli; een snelkoppeling naar een bovenliggende map wel."""
    _, antwoorden = dienst
    antwoorden.extend(
        [
            {
                "files": [
                    {
                        "id": "kort",
                        "name": "terug naar boven",
                        "mimeType": _SNELKOPPELING,
                        "shortcutDetails": {"targetId": "map1", "targetMimeType": _MAP},
                    },
                    {"id": "a", "name": "A", "mimeType": "text/plain"},
                ]
            },
            {"id": "map1", "name": "Wortel", "mimeType": _MAP},
        ]
    )

    uit = gd.drive_lijst_bestanden("map1")

    assert [b["id"] for b in uit] == ["a"], "de startmap wordt niet opnieuw doorlopen"
