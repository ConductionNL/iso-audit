"""Tests voor `clients/google_sheets.py`.

Overgenomen uit `tests/sources/test_planning.py`, waar ze de gws-CLI-variant testten via
een nep-subprocess. Ze testen nu de echte implementatie via een nep-service. Het gedrag
dat behouden moet blijven: een falende tab wordt overgeslagen en niet doorgegooid, en de
bereiken blijven letterlijk gelijk omdat `sources/planning.py` op kolomindex parseert.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from iso_audit.clients import google_sheets as gs


class _Call:
    def __init__(self, antwoord: Any) -> None:
        self._antwoord = antwoord

    def execute(self, **kwargs: Any) -> Any:
        if isinstance(self._antwoord, Exception):
            raise self._antwoord
        return self._antwoord


class _Values:
    def __init__(self, opnames: list[dict[str, Any]], per_bereik: dict[str, Any]) -> None:
        self._opnames = opnames
        self._per_bereik = per_bereik

    def get(self, **kwargs: Any) -> _Call:
        self._opnames.append({"methode": "values.get", **kwargs})
        return _Call(self._per_bereik.get(kwargs.get("range", ""), {"values": []}))


class _Spreadsheets:
    def __init__(
        self, opnames: list[dict[str, Any]], meta: Any, per_bereik: dict[str, Any]
    ) -> None:
        self._opnames = opnames
        self._meta = meta
        self._values = _Values(opnames, per_bereik)

    def get(self, **kwargs: Any) -> _Call:
        self._opnames.append({"methode": "spreadsheets.get", **kwargs})
        return _Call(self._meta)

    def values(self) -> _Values:
        return self._values


class _Service:
    def __init__(
        self, opnames: list[dict[str, Any]], meta: Any, per_bereik: dict[str, Any]
    ) -> None:
        self._s = _Spreadsheets(opnames, meta, per_bereik)

    def spreadsheets(self) -> _Spreadsheets:
        return self._s


@pytest.fixture
def dienst():  # type: ignore[no-untyped-def]
    """Geef `(opnames, staat)`; `staat` bevat `meta` en `per_bereik`."""
    opnames: list[dict[str, Any]] = []
    staat: dict[str, Any] = {"meta": {"sheets": []}, "per_bereik": {}}

    def maak() -> _Service:
        return _Service(opnames, staat["meta"], staat["per_bereik"])

    gs._dienst.cache_clear()
    with patch.object(gs.auth, "sheets_read_service", side_effect=maak):
        yield opnames, staat
    gs._dienst.cache_clear()


def test_lees_sheet_gebruikt_het_standaardbereik(dienst: Any) -> None:
    opnames, staat = dienst
    staat["per_bereik"] = {"A1:ZZ10000": {"values": [["x"]]}}

    assert gs.sheets_lees_sheet("sid") == [["x"]]
    assert opnames[0]["range"] == "A1:ZZ10000"


def test_tabnamen_vraagt_een_veldmasker(dienst: Any) -> None:
    """Zonder masker haalt `spreadsheets.get` alle bladopmaak op voor een lijstje titels."""
    opnames, staat = dienst
    staat["meta"] = {"sheets": [{"properties": {"title": "Tab1"}}]}

    assert gs.sheets_tabnamen("sid") == ["Tab1"]
    assert opnames[0]["fields"] == "sheets.properties.title"


def test_alle_tabs_combineert_tabs(dienst: Any) -> None:
    _, staat = dienst
    staat["meta"] = {
        "sheets": [{"properties": {"title": "Tab1"}}, {"properties": {"title": "Tab2"}}]
    }
    staat["per_bereik"] = {
        "'Tab1'!A1:AZ500": {"values": [["a"]]},
        "'Tab2'!A1:AZ500": {"values": [["b"]]},
    }

    uit = gs.sheets_lees_alle_tabs("sid")

    assert set(uit) == {"Tab1", "Tab2"}
    assert uit["Tab1"] == [["a"]]
    assert uit["Tab2"] == [["b"]]


def test_alle_tabs_slaat_een_falende_tab_over(dienst: Any) -> None:
    """Eén kapotte tab mag een auditplanning niet onleesbaar maken. Daarom ook geen
    `batchGet`: die zou op de héle batch falen."""
    _, staat = dienst
    staat["meta"] = {
        "sheets": [{"properties": {"title": "Tab1"}}, {"properties": {"title": "Tab2"}}]
    }
    staat["per_bereik"] = {
        "'Tab1'!A1:AZ500": {"values": [["a"]]},
        "'Tab2'!A1:AZ500": RuntimeError("Tab fout"),
    }

    uit = gs.sheets_lees_alle_tabs("sid")

    assert "Tab1" in uit
    assert "Tab2" not in uit
