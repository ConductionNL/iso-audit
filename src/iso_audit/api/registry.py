"""Audit-registry: audits en runs als eerste-klas objecten (change portal-dashboard).

Een **audit** is een directory met een manifest. Een **run** is één pipeline-pas
binnen die audit, append-only geregistreerd. Triage en memo zitten op audit-niveau:
je sluit een audit af met één memo, en je mag de pipeline er meerdere keren binnen
draaien (bijvoorbeeld nadat er een bron bij komt).

```
audits/
  9001-2026-Q3/
    audit.json        norm, periode, aangemaakt, aangemaakt_door
    findings.json     de werkset — bestaand formaat, ongewijzigd
    triage_log.jsonl  append-only auditor-beslissingen — bestaand
    runs.jsonl        append-only run-registratie — nieuw
    .actief           wie er laatst muteerde (waarschuwing, geen slot)
```

## Ontwerpkeuzes

- **Geen index-database.** De dashboard-kolommen zijn alle uit de bestanden af te
  leiden. Bij een handvol audits per jaar is een tweede waarheid die synchroon moet
  blijven duurder dan een directory-scan — en een index die uit de pas loopt is in
  een auditwerktuig erger dan een trage lijst.
- **Status wordt berekend, niet opgeslagen.** Een los statusveld gaat op termijn
  liegen tegen de bestanden.
- **`AuditSession` blijft ongewijzigd.** Deze module wijst hem aan; wat er binnen een
  sessie gebeurt verandert niet.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

MANIFEST = "audit.json"
RUNS = "runs.jsonl"
FINDINGS = "findings.json"
TRAIL = "triage_log.jsonl"
ACTIEF = ".actief"

_PERIODE = re.compile(r"^\d{4}-[QH][1-4]$")
"""`2026-Q3` of `2026-H2`. Vrije tekst zou sorteren op periode onbetrouwbaar maken;
`H3`/`H4` laat de regex door en dat is bewust — de norm-kant valideert dat niet en
een te strakke check hier levert alleen frustratie zonder winst."""

ACTIEF_VENSTER = timedelta(minutes=5)
"""Hoe lang een mutatie iemand als 'recent actief' laat gelden."""


class RegistryError(ValueError):
    """Ongeldige audit-invoer of een audit die niet bestaat."""


def _nu() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def audit_id(norm: str, periode: str) -> str:
    """Bouw het audit-id uit norm en periode, bv. ``9001-2026-Q3``.

    :raises RegistryError: bij een lege norm of een periode die niet als
        ``YYYY-Qn``/``YYYY-Hn`` te sorteren is.
    """
    norm = norm.strip()
    periode = periode.strip().upper()
    if not norm or not norm.replace("-", "").isalnum():
        raise RegistryError(f"Ongeldige norm: {norm!r}. Verwacht bv. '9001' of '27001'.")
    if not _PERIODE.match(periode):
        raise RegistryError(
            f"Ongeldige periode: {periode!r}. Verwacht 'JJJJ-Qn' of 'JJJJ-Hn', bv. '2026-Q3'."
        )
    return f"{norm}-{periode}"


@dataclass(frozen=True, slots=True)
class AuditOverzicht:
    """Eén regel op het dashboard. Alles hierin is afgeleid uit de bestanden."""

    id: str
    norm: str
    periode: str
    status: str
    """``nieuw`` | ``loopt`` | ``memo-klaar`` — berekend, nooit opgeslagen."""
    bevindingen: int
    triage_open: int
    memo_klaar: bool
    bronnen: list[str]
    laatste_actor: str | None
    laatste_wijziging: str | None
    runs: int


class AuditRegistry:
    """Audits opsommen, aanmaken en aanwijzen onder één root-directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    # --- aanmaken en opzoeken ------------------------------------------------

    def pad(self, aid: str) -> Path:
        """Directory van een audit; controleert niet of hij bestaat."""
        if "/" in aid or aid in {"", ".", ".."}:
            raise RegistryError(f"Ongeldig audit-id: {aid!r}")
        return self.root / aid

    def bestaat(self, aid: str) -> bool:
        return (self.pad(aid) / MANIFEST).is_file()

    def eis(self, aid: str) -> Path:
        """Geef het pad van een bestaande audit.

        :raises RegistryError: als de audit niet bestaat — nooit stil aanmaken.
        """
        if not self.bestaat(aid):
            raise RegistryError(f"Audit {aid!r} bestaat niet.")
        return self.pad(aid)

    def maak(self, *, norm: str, periode: str, door: str) -> str:
        """Maak een audit aan en retourneer het id.

        Een bestaand id is een fout en geen aanleiding om er een suffix bij te
        verzinnen: twee audits met dezelfde norm én periode is bijna altijd een
        vergissing, en stil doorgaan maakt daar een blijvende dubbele administratie
        van.
        """
        aid = audit_id(norm, periode)
        dir_ = self.pad(aid)
        if (dir_ / MANIFEST).is_file():
            raise RegistryError(
                f"Audit {aid!r} bestaat al. Kies een andere periode of open de bestaande."
            )
        dir_.mkdir(parents=True, exist_ok=True)
        (dir_ / MANIFEST).write_text(
            json.dumps(
                {
                    "id": aid,
                    "norm": norm.strip(),
                    "periode": periode.strip().upper(),
                    "aangemaakt": _nu(),
                    "aangemaakt_door": door,
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        # Lege maar geldige werkset, zodat AuditSession direct te openen is.
        (dir_ / FINDINGS).write_text("[]\n", encoding="utf-8")
        return aid

    # --- activiteit ---------------------------------------------------------

    def markeer_actief(self, aid: str, door: str) -> None:
        """Leg vast wie als laatste muteerde. Geen slot — zie ``andere_actief``."""
        (self.eis(aid) / ACTIEF).write_text(
            json.dumps({"identiteit": door, "ts": _nu()}, ensure_ascii=False),
            encoding="utf-8",
        )

    def andere_actief(self, aid: str, door: str) -> dict[str, str] | None:
        """Retourneer de andere recente bewerker, of ``None``.

        Bewust een waarschuwing en geen vergrendeling: een slot dat blijft hangen na
        een gesloten tabblad maakt een audit onbruikbaar, en dat is een grotere
        faalmodus dan twee auditors die per ongeluk dezelfde bevinding triëren. Beide
        beslissingen blijven in de append-only trail staan, dus het blijft
        herleidbaar.
        """
        pad = self.pad(aid) / ACTIEF
        if not pad.is_file():
            return None
        try:
            rec = json.loads(pad.read_text(encoding="utf-8"))
            wie = str(rec["identiteit"])
            wanneer = datetime.strptime(str(rec["ts"]), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
        if wie == door or datetime.now(UTC) - wanneer > ACTIEF_VENSTER:
            return None
        return {"identiteit": wie, "ts": str(rec["ts"])}
