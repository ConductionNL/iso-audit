"""Veilig lezen en schrijven van de werkset (`findings.json`).

Twee schrijvers raken dit bestand: `runs.voeg_toe()` uit de run-thread hangt kandidaten aan, en
`session.apply_triage()` uit de verzoek-thread muteert één bevinding. Beide deden lees-alles →
wijzig → schrijf-alles zonder enige coördinatie, en dat ging op 2026-08-24 in productie mis:

- **Een verloren beslissing.** De auditor zette 902 bevindingen op `valide`; `nc-5.17`
  (11:49:21Z) stond daarna weer op `open`. De run had de werkset gelezen vóór die triage en
  schreef zijn eigen snapshot terug. De trail hield de beslissing wel — die is append-only — dus
  trail en werkset spraken elkaar tegen. Voor een audittool is dat de ergste soort fout: het
  spoor zegt dat de auditor geoordeeld heeft, de werkset zegt van niet, en de memo-gate
  blokkeert op het verschil.
- **Een half gelezen bestand.** `Path.write_text` kapt het bestand eerst af. Een lezer die er
  precies dan bij is, krijgt nul bytes en een `JSONDecodeError` — of erger, een werkset die
  korter is dan hij hoort te zijn.

Twee maatregelen, elk tegen één van die twee:

1. **Atomair schrijven.** Naar een tijdelijk bestand in dezelfde map en dan `os.replace()`, wat
   op POSIX een atomaire rename is. Elke lezer ziet óf de oude óf de nieuwe versie, nooit een
   halve — ook een lezer die geen slot neemt, en dat zijn de meeste (elke `GET /findings`).
2. **Eén exclusief slot om lees-wijzig-schrijf.** `fcntl.flock` op een lockbestand ernaast.
   Bewust een bestandsslot en geen `threading.Lock`: flock werkt tussen threads én tussen
   processen. Vandaag draait alles in één uvicorn-proces, maar zodra hier een tweede worker of
   een losse component bij komt, blijft dit werken — en dat is precies de kant waar dit project
   op gaat.

Waarom geen SQLite voor de werkset, die er al is: dat is een migratie van het formaat waar de
UI, de memo-bouwer en de trail alle drie op staan. Dit lost het meetbare probleem op zonder dat
formaat aan te raken. Een verhuizing naar de DB is een eigen change met een eigen afweging.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SLOT_ACHTERVOEGSEL = ".lock"
"""Het slot zit op een eigen bestand en niet op `findings.json` zelf.

Een slot op het databestand zou verdwijnen bij de `os.replace()` hieronder: de rename vervangt
de inode, en het slot hangt aan de oude. Het lockbestand blijft staan en wordt nooit
overschreven."""


def slotpad(pad: Path) -> Path:
    return pad.with_name(pad.name + SLOT_ACHTERVOEGSEL)


@contextmanager
def slot(pad: Path) -> Iterator[None]:
    """Exclusief slot op de werkset, voor de duur van een lees-wijzig-schrijf.

    Blokkeert tot het slot vrij is. Bewust zonder time-out: een triage die een halve seconde
    wacht op de run is goed, een triage die stil doorgaat op verouderde gegevens niet.
    """
    slot_bestand = slotpad(pad)
    slot_bestand.parent.mkdir(parents=True, exist_ok=True)
    with slot_bestand.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def lees(pad: Path) -> list[dict[str, Any]]:
    """Lees de werkset; een ontbrekend bestand is een lege werkset."""
    if not pad.is_file():
        return []
    ruw = pad.read_text(encoding="utf-8")
    gegevens: list[dict[str, Any]] = json.loads(ruw) if ruw.strip() else []
    return gegevens


def schrijf(pad: Path, gegevens: list[dict[str, Any]]) -> None:
    """Schrijf de werkset atomair: tijdelijk bestand in dezelfde map, dan `os.replace()`.

    Dezelfde map is een eis en geen nettigheid: `os.replace()` is alleen atomair binnen één
    bestandssysteem, en `/tmp` is in de container een eigen mount.
    """
    pad.parent.mkdir(parents=True, exist_ok=True)
    fd, tijdelijk = tempfile.mkstemp(dir=str(pad.parent), prefix=pad.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(gegevens, fh, ensure_ascii=False, indent=1)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tijdelijk, pad)
    except BaseException:
        Path(tijdelijk).unlink(missing_ok=True)
        raise
