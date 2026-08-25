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
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

MANIFEST = "audit.json"
RUNS = "runs.jsonl"
FINDINGS = "findings.json"
TRAIL = "triage_log.jsonl"
MEMO_INPUT = "memo-input.yaml"
ACTIEF = ".actief"

_NORM_NAAM = {"9001": "ISO 9001:2015", "27001": "ISO 27001:2022"}


def _schrijf_memo_input(dir_: Path, aid: str, codes: list[str], periode: str) -> None:
    """Leg een geldige memo-input klaar bij het aanmaken van de audit.

    Zonder dit bestand kan een audit die net is aangemaakt géén live run afronden: de
    worker vult na afloop de memo-context bij en struikelt op een ontbrekend bestand —
    gemeten op 2026-08-16, nadat de pipeline alle zeven stappen en alle rapporten al met
    succes had afgerond. Een audit hoort zelfstandig te zijn vanaf het moment dat hij
    bestaat.

    De tekst is een steiger, geen inhoud: de auditor bewerkt hem in de memo-editor vóór
    generatie. Wat hier al klopt is de scope, want die volgt uit de audit zelf.
    """
    import yaml

    normen = ", ".join(_NORM_NAAM.get(c, c) for c in codes)
    data = {
        "title": f"Auditmemo — Interne audit<br>{normen}",
        "cycle": periode,
        "date": datetime.now(UTC).strftime("%d-%m-%Y"),
        "version": "v1",
        "lead_summary": (
            "Nog in te vullen. Vat hier de punten samen die een managementbesluit vragen; "
            "de volledige bevindingen staan in het detailrapport."
        ),
        "detail_report_ref": "",
        "context": {
            "audit_cycle": f"Interne audit {periode}, onderdeel van het auditprogramma.",
            "scope": {_NORM_NAAM.get(c, c): "§4 t/m §10" for c in codes},
            "sources": [],
            "dataset_counts": {},
            "scope_caveat": (
                "Deze audit is gebaseerd op de bronnen die in het portaal gekoppeld waren "
                "ten tijde van de run; zie de run-historie voor welke dat waren."
            ),
        },
    }
    (dir_ / MEMO_INPUT).write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


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


_NORM_SLUG = re.compile(r"^iso-(\d+)-\d{4}$")
"""Norm-DB-slug, bv. ``iso-9001-2015``. De norm-DB is de config: een YAML erbij zetten
maakt die norm kiesbaar, zonder codewijziging."""

PIPELINE_NORMEN = frozenset({"9001", "27001"})
"""Normen die de pipeline daadwerkelijk kan draaien.

Bewust een aparte, kleinere set dan wat de norm-DB kan bevatten. De norm-keuze staat op
vier plekken in de pipeline hardcoded (`choices=["9001","27001","beide"]`); een derde
norm toevoegen aan de norm-DB maakt hem hier dus kiesbaar maar nog niet draaibaar. In
plaats van dat stil mis te laten gaan, faalt het aanmaken met een leesbare fout."""

STANDAARD_NORMEN: tuple[str, ...] = ("9001", "27001")
"""Wat een audit standaard toetst: beide normen.

Een gecombineerde audit is de bedoeling; één norm is de uitzondering en niet de norm."""

VOORKEURSNORM = "27001"
"""Welke norm het wordt als er tóch maar één wordt gekozen.

Keuze van de auditor (2026-08-24). ISO 27001 draagt de informatiebeveiligingsaudit en kent 93
clausules tegen 28 voor 9001; een audit die één norm doet en 9001 kiest, laat het grootste deel
van de beheersmaatregelen liggen. Dit is een standaard en geen verbod — een auditor die bewust
alleen 9001 wil toetsen kan dat."""


def norm_code(norm: str) -> str:
    """Korte code voor een norm: ``iso-9001-2015`` → ``9001``; ``9001`` blijft ``9001``.

    Eén regel voor beide vormen, zodat de UI een norm-DB-slug mag doorgeven en een
    mens een korte code — en er niet twee vocabulaires naast elkaar ontstaan.
    """
    norm = norm.strip()
    m = _NORM_SLUG.match(norm)
    if m:
        return m.group(1)
    if norm.isdigit():
        return norm
    raise RegistryError(f"Onbekende norm: {norm!r}. Verwacht bv. 'iso-9001-2015' of '9001'.")


def run_code(normen: list[str]) -> str:
    """De norm-parameter waarmee de pipeline draait: ``9001``, ``27001`` of ``beide``.

    :raises RegistryError: bij een norm die de pipeline niet kent — expliciet in plaats
        van een run die stil de verkeerde norm gebruikt.
    """
    codes = sorted({norm_code(n) for n in normen})
    onbekend = [c for c in codes if c not in PIPELINE_NORMEN]
    if onbekend:
        raise RegistryError(
            f"De pipeline kan norm(en) {', '.join(onbekend)} nog niet draaien. "
            f"Ondersteund: {', '.join(sorted(PIPELINE_NORMEN))}."
        )
    if not codes:
        raise RegistryError("Kies minstens één norm.")
    return "beide" if len(codes) > 1 else codes[0]


def audit_id(normen: list[str], periode: str) -> str:
    """Bouw het audit-id uit normen en periode, bv. ``9001-2026-Q3`` of
    ``9001_27001-2026-Q3``.

    Meerdere normen worden gesorteerd en met ``_`` verbonden — URL-veilig en zonder de
    ``+``-verwarring (die in query-strings een spatie betekent). Het id wordt nooit
    terug geparsed: het manifest houdt de normen expliciet.

    :raises RegistryError: bij een lege of onbekende norm, of een periode die niet als
        ``JJJJ-Qn``/``JJJJ-Hn`` te sorteren is.
    """
    periode = periode.strip().upper()
    if not normen:
        raise RegistryError("Kies minstens één norm.")
    codes = sorted({norm_code(n) for n in normen})
    if not _PERIODE.match(periode):
        raise RegistryError(
            f"Ongeldige periode: {periode!r}. Verwacht 'JJJJ-Qn' of 'JJJJ-Hn', bv. '2026-Q3'."
        )
    return f"{'_'.join(codes)}-{periode}"


@dataclass(frozen=True, slots=True)
class AuditOverzicht:
    """Eén regel op het dashboard. Alles hierin is afgeleid uit de bestanden."""

    id: str
    normen: list[str]
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

    def maak(self, *, normen: list[str], periode: str, door: str) -> str:
        """Maak een audit aan en retourneer het id.

        ``normen`` mag meerdere normen bevatten — een audit over 9001 én 27001 is
        gewoon één audit met één memo. De pipeline-parameter wordt afgeleid
        (:func:`run_code`) en niet apart bewaard, zodat er geen tweede waarheid over
        de scope ontstaat.

        Een bestaand id is een fout en geen aanleiding om er een suffix bij te
        verzinnen: dezelfde normen én periode is bijna altijd een vergissing, en stil
        doorgaan maakt daar een blijvende dubbele administratie van.
        """
        aid = audit_id(normen, periode)
        codes = sorted({norm_code(n) for n in normen})
        run_code(codes)  # faalt vóór het aanmaken als de pipeline dit niet kan draaien
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
                    "normen": codes,
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
        _schrijf_memo_input(dir_, aid, codes, periode.strip().upper())
        return aid

    # --- activiteit ---------------------------------------------------------

    def archiveer(self, aid: str, *, door: str, reden: str) -> Path:
        """Haal een audit uit het overzicht door hem naar het archief te verplaatsen.

        **Verplaatsen en niet verwijderen.** Een audit die gedraaid heeft, is bewijs dát er
        geaudit is; die weggooien maakt de volgende vraag — "wat is er in Q2 getoetst?" —
        onbeantwoordbaar. Het overzicht loopt over mappen met een manifest, dus verplaatsen
        haalt hem er vanzelf uit.

        **Een reden is verplicht.** Zonder reden is later niet te zeggen of dit opruimen was of
        iets wegwerken — hetzelfde onderscheid als bij het verbergen van een run.

        Retourneert het pad in het archief.

        :raises RegistryError: als de audit niet bestaat of de reden leeg is.
        """
        import json
        import shutil
        from datetime import UTC, datetime

        if not reden.strip():
            raise RegistryError(
                "Geef een reden op. Zonder reden is later niet te zien of dit opruimen was."
            )
        bron = self.eis(aid)
        nu = datetime.now(UTC)
        map_ = self.root.parent / "archief" / nu.strftime("%Y-%m-%d")
        map_.mkdir(parents=True, exist_ok=True)
        # Een teller erbij als het al bestaat: twee archiveringen binnen dezelfde seconde is
        # zeldzaam maar niet onmogelijk, en dan mag de tweede de eerste niet overschrijven —
        # dat zou precies het dossier weggooien dat we bewaren.
        doel = map_ / f"{aid}-{nu:%H%M%S}"
        nummer = 2
        while doel.exists():
            doel = map_ / f"{aid}-{nu:%H%M%S}-{nummer}"
            nummer += 1
        shutil.move(str(bron), str(doel))
        (doel / "gearchiveerd.json").write_text(
            json.dumps(
                {
                    "audit_id": aid,
                    "door": door,
                    "reden": reden.strip(),
                    "op": nu.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        logging.getLogger(__name__).info(
            "Audit %s gearchiveerd door %s: %s", aid, door, reden.strip()
        )
        return doel

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
