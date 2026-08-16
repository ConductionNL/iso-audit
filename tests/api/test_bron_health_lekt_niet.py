"""Structurele gate: geen enkele bron geeft een ruwe leveranciersmelding aan de client.

## Waarom dit apart staat

`config/verbinding.py` is op 2026-08-14 toegevoegd om leveranciersfouten te normaliseren,
en `tests/config/test_verbinding.py` was groen. Toch lekte het door: die test gebruikt een
adapter die een exception **gooit**, en dat is precies de enige tak die wél gesanitiseerd
werd. Adapters die hun fout zélf afvangen en als ``{"status": "fail", "reden": ...}``
teruggeven, gingen eromheen — en `ui.html` rendert die tekst rechtstreeks.

Gemeten voorbeelden van wat er zo in de browser belandde:

- ``Jira API 401 op https://<tenant>.atlassian.net/rest/api/3/myself: <responsbody>``
- ``gws-fout: Command '['gws', 'sheets', ...]' returned non-zero exit status 1.``

Deze test gaat daarom over **elke** geregistreerde bron en over het pad dat de vorige gate
niet raakte. Hij faalt ook op een bron die pas volgend jaar wordt toegevoegd.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from iso_audit.api import session as sess
from iso_audit.config import verbinding

_MARKER = "LEKMARKER-https://tenant.example/rest/api/3/myself: {'token': 'ATATTxyz'}"
"""Staat model voor een echte leveranciersmelding: URL plus responsbody. Als deze string
de client bereikt, bereikt een echt token dat ook."""


def _bronnen() -> list[str]:
    from iso_audit.ingest import beschikbare_bronnen

    return beschikbare_bronnen()


class _ZelfAfvangend:
    """Adapter die faalt zoals de echte adapters faalden: fout zelf afvangen en teruggeven."""

    def __init__(self, naam: str) -> None:
        self.naam = naam

    def healthcheck(self) -> dict[str, object]:
        return {"status": "fail", "naam": self.naam, "reden": _MARKER}


class _Gooiend:
    def __init__(self, naam: str) -> None:
        self.naam = naam

    def healthcheck(self) -> dict[str, object]:
        raise RuntimeError(_MARKER)


@pytest.mark.parametrize("adapter", [_ZelfAfvangend, _Gooiend], ids=["zelf-afgevangen", "gegooid"])
@pytest.mark.parametrize("naam", _bronnen())
def test_geen_bron_geeft_een_ruwe_melding_door(
    naam: str, adapter: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MIRO_API_TOKEN", raising=False)

    def _maak() -> Any:
        return adapter(naam)

    with patch("iso_audit.sources.get", return_value=_maak):
        uit = sess._check_source(naam)

    assert uit["connected"] is False
    assert uit["soort"], "een falende bron moet een soort hebben, anders kan de UI niets zeggen"
    assert "LEKMARKER" not in str(uit.get("reden", "")), "ruwe leveranciersmelding lekte"
    assert "ATATT" not in str(uit), "tokenfragment lekte via een ander veld"
    assert "tenant.example" not in str(uit), "tenant-URL lekte"


@pytest.mark.parametrize("naam", _bronnen())
def test_de_teruggegeven_reden_is_een_vaste_tekst(
    naam: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De tekst komt uit `verbinding.TEKST` en is dus niet door een leverancier bepaald.

    Uitzondering: `niet_geconfigureerd` — dat is een fout die wij zelf vaststellen (een
    leeg veld), dus daar mag een adapter zijn eigen, veilige tekst meegeven.
    """
    monkeypatch.delenv("MIRO_API_TOKEN", raising=False)

    with patch("iso_audit.sources.get", return_value=lambda: _ZelfAfvangend(naam)):
        uit = sess._check_source(naam)

    if uit.get("soort") != "niet_geconfigureerd":
        assert str(uit["reden"]) in set(verbinding.TEKST.values())
