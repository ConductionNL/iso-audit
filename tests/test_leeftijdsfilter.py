"""Een document zonder wijzigingstijd is niet oud, alleen onbekend.

Gemeten op 2026-08-29 in het portaal: *"Leeftijdsfilter (2024-08-29): 88 actief, 1448
gearchiveerd (>2 jaar oud)"*. Van die 1448 waren er 1283 repository-documenten en 162
webpagina's, allemaal die dag opgehaald. Ze hadden alleen geen `modified_at`, en een lege string
is in Python altijd kleiner dan een datum-string — dus gold élk document zonder datum als ouder
dan twee jaar.

Gevolg: de hele repo- en websitebron leverde geen enkele bevinding, terwijl de documenten netjes
waren ingelezen én aan clausules gekoppeld. Zestien minuten ophalen, 1.080 clausulekoppelingen,
en dan stil weggegooid met een melding die iets anders beweerde dan er gebeurde.

Twee dingen dus: een onbekende datum telt als actief, en de melding zegt hoeveel documenten geen
datum hadden. Bij twijfel meenemen — een document ten onrechte wegen kost een modelaanroep, een
document ten onrechte weglaten kost bewijs.
"""

from __future__ import annotations

from iso_audit.pipeline import splits_op_leeftijd

_CUTOFF = "2024-08-29"


def test_een_recent_document_is_actief() -> None:
    actief, oud, zonder = splits_op_leeftijd([{"modified_at": "2026-01-01"}], _CUTOFF)
    assert len(actief) == 1 and not oud and not zonder


def test_een_oud_document_wordt_gearchiveerd() -> None:
    actief, oud, zonder = splits_op_leeftijd([{"modified_at": "2019-01-01"}], _CUTOFF)
    assert not actief and len(oud) == 1 and not zonder


def test_een_document_zonder_datum_telt_als_actief() -> None:
    """Dit is de fout die 1448 documenten liet verdwijnen."""
    actief, oud, zonder = splits_op_leeftijd([{"modified_at": ""}, {}], _CUTOFF)
    assert len(actief) == 2, "onbekend is niet oud"
    assert not oud
    assert len(zonder) == 2, "maar het moet wel geteld worden"


def test_de_telling_klopt_bij_een_mengeling() -> None:
    docs = [
        {"modified_at": "2026-01-01", "naam": "nieuw"},
        {"modified_at": "2019-01-01", "naam": "oud"},
        {"modified_at": "", "naam": "onbekend"},
    ]
    actief, oud, zonder = splits_op_leeftijd(docs, _CUTOFF)
    assert {d["naam"] for d in actief} == {"nieuw", "onbekend"}
    assert {d["naam"] for d in oud} == {"oud"}
    assert {d["naam"] for d in zonder} == {"onbekend"}


def test_niets_raakt_zoek() -> None:
    """Elk document komt in precies één van de twee eerste groepen terecht."""
    docs = [{"modified_at": d} for d in ("2026-01-01", "2019-01-01", "", "2025-06-06")]
    actief, oud, _ = splits_op_leeftijd(docs, _CUTOFF)
    assert len(actief) + len(oud) == len(docs)
