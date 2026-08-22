"""Tests voor de WebDAV-client — parsing, overslaan en de XML-weigering.

De XML-weigering is hier het zwaarste punt: nagemeten op 2026-08-22 met Python 3.12.13 en
expat 2.7.3 weigert `xml.etree.ElementTree` een entity-expansie **niet**.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from iso_audit.clients import nextcloud as dav

VERBINDING = dav.Verbinding(
    basis_url="https://cloud.example.org", gebruiker="auditor", app_wachtwoord="geheim"
)

_MULTISTATUS = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/remote.php/dav/files/auditor/Audit/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/auditor/Audit/Beleid.docx</d:href>
    <d:propstat><d:prop>
      <d:resourcetype/>
      <d:getcontenttype>application/vnd.openxmlformats-officedocument.wordprocessingml.document</d:getcontenttype>
      <d:getlastmodified>Fri, 22 Aug 2026 10:00:00 GMT</d:getlastmodified>
      <d:getcontentlength>1234</d:getcontentlength>
    </d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/auditor/Audit/Submap/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
</d:multistatus>
"""


def test_dav_root_is_gebruikersspecifiek() -> None:
    assert VERBINDING.dav_root == "https://cloud.example.org/remote.php/dav/files/auditor/"
    schuin = dav.Verbinding(basis_url="https://x.org/", gebruiker="u", app_wachtwoord="p")
    assert schuin.dav_root == "https://x.org/remote.php/dav/files/u/"


def test_parse_laat_de_opgevraagde_map_zelf_weg() -> None:
    """Anders is elke map een kind van zichzelf en loopt de recursie oneindig."""
    items = dav._parse_propfind(
        _MULTISTATUS, "/remote.php/dav/files/auditor/Audit/", "/remote.php/dav/files/auditor/"
    )

    paden = [i.pad for i in items]
    assert paden == ["Audit/Beleid.docx", "Audit/Submap/"], "paden zijn relatief aan de wortel"
    bestand = items[0]
    assert bestand.is_map is False
    assert bestand.naam == "Beleid.docx"
    assert bestand.bytes_groot == 1234
    assert items[1].is_map is True


def test_parse_weigert_een_doctype() -> None:
    """Entity-expansie: nagemeten op 2026-08-22 blokkeert ElementTree die niet zelf.

    Een WebDAV-antwoord heeft nooit legitiem een DTD, dus de weigering kost niets.
    """
    bom = """<?xml version="1.0"?>
<!DOCTYPE lolz [ <!ENTITY lol "lol"> ]>
<d:multistatus xmlns:d="DAV:"><d:response><d:href>/x</d:href></d:response></d:multistatus>"""

    with pytest.raises(dav.WebdavAntwoordError, match="DOCTYPE"):
        dav._parse_propfind(bom, "/x/", "/x/")


def test_parse_weigert_een_te_groot_antwoord() -> None:
    with pytest.raises(dav.WebdavAntwoordError, match="overschrijdt"):
        dav._parse_propfind("x" * (dav.MAX_ANTWOORD + 1), "/x/", "/x/")


def test_doctype_verderop_is_gewoon_tekst() -> None:
    """Een bestandsnaam met `<!DOCTYPE` erin mag geen listing tegenhouden."""
    xml = _MULTISTATUS.replace("Beleid.docx", "Uitleg over &lt;!DOCTYPE.md")
    items = dav._parse_propfind(
        xml, "/remote.php/dav/files/auditor/Audit/", "/remote.php/dav/files/auditor/"
    )
    assert len(items) == 2


class _Sessie:
    """Stub-sessie die per pad een vast antwoord teruggeeft."""

    def __init__(self, per_pad: dict[str, str]) -> None:
        self.per_pad = per_pad
        self.aanroepen: list[str] = []

    def request(self, methode: str, url: str, **kw: Any) -> Any:
        del methode, kw
        pad = url.split("/files/auditor/", 1)[1]
        self.aanroepen.append(pad)
        antwoord = MagicMock()
        antwoord.text = self.per_pad.get(
            pad, '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"/>'
        )
        antwoord.raise_for_status = lambda: None
        return antwoord


def _multistatus(basis: str, kinderen: list[tuple[str, bool]]) -> str:
    regels = [
        f"<d:response><d:href>/remote.php/dav/files/auditor/{basis}</d:href>"
        "<d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype>"
        "</d:prop></d:propstat></d:response>"
    ]
    for naam, is_map in kinderen:
        rt = "<d:collection/>" if is_map else ""
        mime = "" if is_map else "<d:getcontenttype>text/plain</d:getcontenttype>"
        regels.append(
            f"<d:response><d:href>/remote.php/dav/files/auditor/{basis}{naam}</d:href>"
            f"<d:propstat><d:prop><d:resourcetype>{rt}</d:resourcetype>{mime}"
            "</d:prop></d:propstat></d:response>"
        )
    return (
        '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">' + "".join(regels) + "</d:multistatus>"
    )


def test_recursie_volgt_submappen_en_telt_overgeslagen() -> None:
    """Prullenbak, versies en verborgen bestanden overslaan — maar geteld, niet stil."""
    sessie = _Sessie(
        {
            "Audit/": _multistatus(
                "Audit/",
                [("Beleid.txt", False), ("Sub/", True), (".hidden", False), ("trashbin/", True)],
            ),
            "Audit/Sub/": _multistatus("Audit/Sub/", [("Diep.txt", False)]),
        }
    )
    skips: dict[str, int] = {}

    items = dav.lijst_recursief(VERBINDING, "Audit", sessie=sessie, overgeslagen=skips)  # type: ignore[arg-type]

    assert sorted(i.pad for i in items) == ["Audit/Beleid.txt", "Audit/Sub/Diep.txt"]
    assert skips["verborgen bestand of map"] == 1
    assert skips["Nextcloud-systeemmap (prullenbak, versies of uploads)"] == 1
    assert "Audit/trashbin/" not in sessie.aanroepen, "een overgeslagen map wordt niet doorlopen"


def test_bereikbaar_meldt_401_404_en_netwerkfout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fout(code: int) -> requests.HTTPError:
        antwoord = MagicMock()
        antwoord.status_code = code
        return requests.HTTPError(response=antwoord)

    for code, fragment in ((401, "app-wachtwoord"), (404, "bestaat niet"), (500, "status 500")):
        monkeypatch.setattr(
            dav, "lijst_map", lambda *a, c=code, **k: (_ for _ in ()).throw(_fout(c))
        )
        ok, reden = dav.bereikbaar(VERBINDING)
        assert ok is False and fragment in reden

    monkeypatch.setattr(
        dav, "lijst_map", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("x"))
    )
    ok, reden = dav.bereikbaar(VERBINDING)
    assert ok is False
    assert "niet bereikbaar" in reden
    assert "x" not in reden.replace("bereikbaar", ""), "geen ruwe foutmelding naar de browser"
