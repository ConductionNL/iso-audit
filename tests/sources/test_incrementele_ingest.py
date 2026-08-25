"""Een ongewijzigd document wordt niet opnieuw opgehaald.

Gemeten op 2026-08-24 met drie runs op één database: het dure deel — de modelaanroepen — werd
volledig hergebruikt (0 calls in ronde 2 en 3), maar een herhaalde run duurde nog steeds
zestien minuten. Die gaan bijna helemaal op aan opnieuw ophalen en uitpakken van documenten die
niet veranderd zijn:

| bron | listing | inhoud per document | totaal |
|---|---|---|---|
| Drive | 65 s voor 456 docs | 2,49 s | 1.202 s |
| Nextcloud | 3,2 s voor 121 docs | 0,55 s | 69 s |

De listing blijft volledig draaien — dat is de enige manier om te merken dat een document
verdwenen of bijgekomen is, en het is 65 s van de 1.200. Alleen `fetch_content` wordt
overgeslagen.

`ingest_log` werd al elke run geschreven en nooit gelezen; `documents.modified_at` stond er al
en werd alleen gebruikt voor de twee-jaar-archiefgrens.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from iso_audit.sources.protocol_ingest import bekende_teksten, mag_overslaan


def _bekend() -> dict[str, tuple[str, str]]:
    """Wat er in de database staat: id -> (wijzigingstijd, tekst)."""
    return {"d1": ("2026-01-01T10:00:00Z", "de tekst van gisteren")}


def test_ongewijzigd_document_wordt_overgeslagen() -> None:
    hergebruik = mag_overslaan("d1", "2026-01-01T10:00:00Z", _bekend())
    assert hergebruik == "de tekst van gisteren"


def test_gewijzigd_document_wordt_opnieuw_gelezen() -> None:
    assert mag_overslaan("d1", "2026-02-02T09:00:00Z", _bekend()) is None


def test_onbekend_document_wordt_gelezen() -> None:
    assert mag_overslaan("d99", "2026-01-01T10:00:00Z", _bekend()) is None


def test_zonder_wijzigingstijd_wordt_altijd_gelezen() -> None:
    """Planning levert rijen uit een sheet zonder tijdstempel — 150 van de 709 in de meting.

    Geen geraden tijd: dan zou een document als ongewijzigd gelden terwijl niemand dat weet, en
    dat is een stille aanname op de plek waar het tool zijn dekking verantwoordt.
    """
    assert mag_overslaan("d1", "", _bekend()) is None
    assert mag_overslaan("d1", None, _bekend()) is None


def test_een_leeg_bewaarde_tekst_wordt_opnieuw_gelezen() -> None:
    """Leeg opgeslagen betekent niet gelezen; overslaan zou de leegte bevriezen."""
    assert mag_overslaan("d1", "2026-01-01T10:00:00Z", {"d1": ("2026-01-01T10:00:00Z", "")}) is None


def test_bekende_teksten_leest_uit_de_database() -> None:
    conn = sqlite3.connect(":memory:")
    from iso_audit.store import initialiseer

    initialiseer(conn)
    conn.execute(
        "INSERT INTO documents (id, naam, tekst, herkomst, mime_type, modified_at, ingested_at)"
        " VALUES ('d1', 'Doc', 'tekst', 'Drive', 'txt', '2026-01-01T10:00:00Z', '2026-01-01')"
    )
    conn.commit()

    bekend = bekende_teksten(conn, "Drive")

    assert bekend["d1"] == ("2026-01-01T10:00:00Z", "tekst")


def test_bekende_teksten_scheidt_op_herkomst() -> None:
    """Twee bronnen kunnen hetzelfde id gebruiken; die mogen niet door elkaar lopen."""
    conn = sqlite3.connect(":memory:")
    from iso_audit.store import initialiseer

    initialiseer(conn)
    for herkomst in ("Drive", "Nextcloud"):
        conn.execute(
            "INSERT INTO documents (id, naam, tekst, herkomst, mime_type, modified_at,"
            " ingested_at) VALUES (?, 'Doc', ?, ?, 'txt', '2026-01-01T10:00:00Z', '2026-01-01')",
            (f"id-{herkomst}", herkomst, herkomst),
        )
    conn.commit()

    assert set(bekende_teksten(conn, "Drive")) == {"id-Drive"}


@pytest.mark.parametrize("opnieuw", [True, False])
def test_opnieuw_lezen_negeert_de_cache(opnieuw: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """Na een wijziging in de lezers is de opgeslagen tekst verouderd zonder dat de bron dat weet.

    Op 2026-08-24 werden 32 OpenDocument-bestanden voor het eerst leesbaar. Met alleen een
    tijdstempel-vergelijking zouden die als "ongewijzigd" zijn overgeslagen en nooit binnen zijn
    gekomen. Een cache zonder uitweg is een val.
    """
    from iso_audit.sources import protocol_ingest

    monkeypatch.setattr(protocol_ingest, "OPNIEUW_LEZEN", opnieuw)
    uitkomst = mag_overslaan("d1", "2026-01-01T10:00:00Z", _bekend())
    assert (uitkomst is None) is opnieuw


def _doc(id_: str, gewijzigd: str) -> Any:
    from iso_audit.sources.base import Document

    return Document(
        id=id_,
        titel=f"{id_}.docx",
        bron="drive",
        type="docx",
        laatst_gewijzigd=gewijzigd,
        inhoud_uri=id_,
    )
