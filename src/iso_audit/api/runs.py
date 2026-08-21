"""Runs binnen een audit: append-only registratie en aanvullend samenvoegen.

Een tweede run in dezelfde audit **vult aan**: nieuwe kandidaten komen erbij, wat al
getrieerd is blijft getrieerd. Dat is wat de praktijk vraagt — Jira erbij zetten na
een Drive-only run — maar het vraagt een dedup-regel, anders triageert de auditor
hetzelfde twee keer.

## Dedup

Sleutel: ``(standard, clause, source, genormaliseerde titel)``. Deterministisch in
code, geen LLM en geen gelijkenis-drempel. Dat laatste is een bewuste weigering: een
drempel die niemand kan uitleggen hoort niet in een auditwerktuig, en "0.83 leek genoeg"
is geen antwoord aan een auditor.

Overgeslagen duplicaten worden **geteld bij het run-record**, niet stil weggelaten —
dezelfde discipline als het ``dropped``-spoor uit `auditmemo-curate`. Een run die
dertig kandidaten oplevert waarvan achttien al bekend zijn, moet niet lijken alsof hij
niets deed.

## Wat een run niet doet

Bestaande regels in ``findings.json`` wijzigen of verwijderen. Alleen toevoegen.
Daarmee blijft de triage-trail als geheel geldig: een beslissing verwijst naar een
bevinding die niet onder haar voeten is veranderd.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUNS = "runs.jsonl"


@dataclass(frozen=True)
class Kosten:
    """Wat een run kostte, met alles wat nodig is om het later na te vertellen.

    Vier velden bij elkaar, want los van elkaar zeggen ze te weinig. Een bedrag zonder model
    is niet te herleiden; zonder peildatum niet te controleren (prijzen wijzigen buiten deze
    repo om); en zonder grondslag niet te interpreteren, want lijstprijs is niet hetzelfde als
    wat er gefactureerd wordt — Sonnet 5 had op 2026-08-17 een introtarief dat een derde onder
    de lijstprijs lag.
    """

    usd: float
    model: str
    peildatum: str
    grondslag: str
    calls: int = 0
    fouten: int = 0

    def als_record(self) -> dict[str, Any]:
        return {
            "usd": round(self.usd, 4),
            "model": self.model,
            "peildatum": self.peildatum,
            "grondslag": self.grondslag,
            "calls": self.calls,
            "fouten": self.fouten,
        }


@dataclass(frozen=True)
class Dekking:
    """Welk deel van de bron een run heeft gezien en gelezen, en per reden wat niet.

    Waarom dit in het run-record hoort en niet alleen in het log: het log verdwijnt bij een
    podherstart, en "welk deel van de bron heeft het tool gezien" is precies wat een
    certificerende instantie vraagt. Een auditor die 299 documenten ziet, ziet niet dat er 213
    buiten stonden — dezelfde redenering waarom de kosten op 2026-08-17 van het log naar het
    run-record zijn verhuisd.

    Aantallen per reden, geen bestandsnamen: 213 namen per record maakt de trail onleesbaar, en
    de namen staan al in het handmatige-reviewspoor.
    """

    gezien: int
    gelezen: int
    overgeslagen: dict[str, int]

    def als_record(self) -> dict[str, Any]:
        return {
            "gezien": self.gezien,
            "gelezen": self.gelezen,
            "niet_gelezen": sum(self.overgeslagen.values()),
            "overgeslagen": dict(self.overgeslagen),
        }


FINDINGS = "findings.json"

_WS = re.compile(r"\s+")


def _nu() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def dedup_sleutel(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    """Deterministische sleutel voor deduplicatie tussen runs.

    Normalisatie van de titel is lowercasing plus whitespace-collaps. Bewust niet
    meer: interpunctie strippen of synonymen matchen maakt de regel onuitlegbaar en
    daarmee onbruikbaar in een audit.
    """
    titel = _WS.sub(" ", str(finding.get("title", "")).strip().lower())
    return (
        str(finding.get("standard", "")),
        str(finding.get("clause", "")),
        str(finding.get("source") or ""),
        titel,
    )


def voeg_toe(
    audit_dir: str | Path,
    kandidaten: list[dict[str, Any]],
) -> tuple[int, int]:
    """Voeg kandidaten aanvullend toe aan de werkset.

    Retourneert ``(toegevoegd, overgeslagen)``. Bestaande bevindingen worden niet
    aangeraakt — ook niet als een kandidaat "beter" lijkt: dat oordeel is aan de
    auditor, niet aan een merge-functie.
    """
    pad = Path(audit_dir) / FINDINGS
    bestaand: list[dict[str, Any]] = (
        json.loads(pad.read_text(encoding="utf-8")) if pad.is_file() else []
    )
    bekend = {dedup_sleutel(f) for f in bestaand}

    toegevoegd = 0
    overgeslagen = 0
    for k in kandidaten:
        sleutel = dedup_sleutel(k)
        if sleutel in bekend:
            overgeslagen += 1
            continue
        bekend.add(sleutel)
        bestaand.append(k)
        toegevoegd += 1

    if toegevoegd:
        pad.write_text(
            json.dumps(bestaand, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    return toegevoegd, overgeslagen


def registreer(
    audit_dir: str | Path,
    *,
    door: str,
    modus: str,
    norm: str,
    bronnen: list[str],
    hoofdstuk: str | None = None,
    toegevoegd: int = 0,
    overgeslagen: int = 0,
    fout: str | None = None,
) -> dict[str, Any]:
    """Schrijf één append-only run-record en retourneer het.

    Ook een mislukte run wordt geregistreerd, met zijn fout. Weglaten maakt het
    overzicht schoner en het dossier onvolledig — een run die faalde op een
    ontbrekende credential is precies wat je later wil terugzien.
    """
    dir_ = Path(audit_dir)
    nummer = som(dir_) + 1
    record: dict[str, Any] = {
        "run_id": f"run-{nummer:04d}",
        "soort": "start",
        "gestart": _nu(),
        "door": door,
        "modus": modus,
        "norm": norm,
        "bronnen": bronnen,
        "hoofdstuk": hoofdstuk or "",
        "toegevoegd": toegevoegd,
        "overgeslagen": overgeslagen,
        "status": "fout" if fout else "loopt",
    }
    if fout:
        record["fout"] = fout[:500]
        record["geeindigd"] = record["gestart"]
    _append(dir_, record)
    return record


def afsluiten(
    audit_dir: str | Path,
    run_id: str,
    *,
    toegevoegd: int = 0,
    overgeslagen: int = 0,
    fout: str | None = None,
    kosten: Kosten | None = None,
    dekking: Dekking | None = None,
) -> dict[str, Any]:
    """Schrijf het afsluitrecord van een run — append-only, niets wordt overschreven.

    Waarom twee records en geen update: `runs.jsonl` is de audit-trail, en append-only is
    daar de garantie. Tot 2026-08-14 las de route `laatste_merge` direct nadat de
    worker-thread was gestart — dus altijd `(0, 0)` — en schreef `status: "klaar"`. Elk
    live-run-record beweerde daardoor permanent "klaar, 0 toegevoegd, 0 overgeslagen",
    geschreven vóórdat er iets gelezen was, en append-only betekent dat je dat niet meer
    kunt rechtzetten.

    De uitkomst is eigendom van de worker; die roept dit aan als hij klaar is of faalt.
    Lezers gebruiken `samengevat()`, dat per `run_id` de laatste stand teruggeeft.
    """
    dir_ = Path(audit_dir)
    record: dict[str, Any] = {
        "run_id": run_id,
        "soort": "afsluiting",
        "geeindigd": _nu(),
        "toegevoegd": toegevoegd,
        "overgeslagen": overgeslagen,
        "status": "fout" if fout else "klaar",
    }
    if fout:
        record["fout"] = fout[:500]
    if kosten is not None:
        # Bedrag, model, peildatum én grondslag bij elkaar in één record. Losgekoppeld is een
        # bedrag niet navertelbaar: prijzen wijzigen buiten deze repo om, en lijstprijs is niet
        # hetzelfde als wat er gefactureerd wordt. Tot 2026-08-17 stond het bedrag alleen in
        # het log terwijl de rest van de runhistorie wél in de trail zat.
        record["kosten"] = kosten.als_record()
    if dekking is not None:
        # Zelfde reden als bij de kosten: zonder dit staat er in de trail hoeveel documenten
        # zijn toegevoegd, maar niet welk deel van de bron ongelezen bleef.
        record["dekking"] = dekking.als_record()
    _append(dir_, record)
    return record


AFGEBROKEN_REDEN = (
    "Het proces dat deze run uitvoerde is gestopt (podherstart, crash of deploy). "
    "Wat er tot dat moment is vastgelegd blijft staan."
)
"""Reden bij een run die door een procesherstart is afgebroken.

Waarom dit bestaat: een run leeft in een thread van het portaalproces. Sneuvelt dat proces,
dan is er niemand meer die het afsluitrecord schrijft en blijft het startrecord voor altijd
`loopt` beweren. Op 2026-08-21 stonden er vier zulke records in één audit — het proces was
omgevallen met SIGSEGV, maar de historie zei "loopt nog…" alsof er vier runs bezig waren.

Een audittrail die beweert dat er iets loopt wat niet loopt, is erger dan een lege trail: je
kunt er niet uit opmaken welke run echt gedraaid heeft."""


def sluit_verweesde_runs(audit_dir: str | Path) -> list[str]:
    """Sluit runs die `loopt` zeggen maar niet meer kunnen lopen. Retourneert hun ID's.

    Bedoeld om **bij het opstarten** van het portaal te draaien: een run leeft in een thread
    van dit proces, dus een run die bij een verse start nog `loopt` zegt, is per definitie
    afgebroken. Append-only, net als elk ander afsluitrecord — er wordt niets herschreven.
    """
    dir_ = Path(audit_dir)
    if not (dir_ / RUNS).is_file():
        return []
    verweesd = [
        str(r["run_id"]) for r in samengevat(dir_) if r.get("status") == "loopt" and r.get("run_id")
    ]
    for rid in verweesd:
        afsluiten(dir_, rid, fout=AFGEBROKEN_REDEN)
    return verweesd


def _append(audit_dir: Path, record: dict[str, Any]) -> None:
    """Eén regel toevoegen. Eén `write` van één regel < 4 KiB is op POSIX atomair genoeg
    voor gelijktijdige appends; dat is dezelfde aanname waarop `triage_log.jsonl` leunt."""
    with (audit_dir / RUNS).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def lijst(audit_dir: str | Path) -> list[dict[str, Any]]:
    """Alle run-records, oudste eerst. Onleesbare regels worden overgeslagen."""
    pad = Path(audit_dir) / RUNS
    if not pad.is_file():
        return []
    records: list[dict[str, Any]] = []
    for regel in pad.read_text(encoding="utf-8").splitlines():
        regel = regel.strip()
        if not regel:
            continue
        try:
            records.append(json.loads(regel))
        except json.JSONDecodeError:
            continue
    return records


def samengevat(audit_dir: str | Path) -> list[dict[str, Any]]:
    """Per run de laatste stand, oudste eerst — de vorm waar de UI iets aan heeft.

    `lijst()` blijft de ruwe append-only waarheid; hier worden de records per `run_id`
    over elkaar heen gelegd (laatste wint per veld). Een run met alleen een startrecord
    houdt `status: "loopt"`.
    """
    per_run: dict[str, dict[str, Any]] = {}
    for r in lijst(audit_dir):
        rid = str(r.get("run_id", ""))
        if not rid:
            continue
        if rid in per_run:
            per_run[rid].update(r)
        else:
            per_run[rid] = dict(r)
    return list(per_run.values())


def som(audit_dir: str | Path) -> int:
    """Aantal runs — niet het aantal records.

    Sinds een run twee records heeft (start + afsluiting) zou tellen op regels elke run
    dubbel tellen. Dat raakt twee dingen: de nummering in `registreer()` en
    `aantal_runs` op het dashboard (`overzicht.regel`).
    """
    return len({str(r.get("run_id", "")) for r in lijst(audit_dir) if r.get("run_id")})


def geraadpleegde_bronnen(audit_dir: str | Path) -> list[str]:
    """Bronnen uit afgeronde runs, gesorteerd.

    Runs met status `loopt` of `fout` vallen af: een run die op een ontbrekende credential
    faalde heeft niets gelezen, en die kolom is een bewijsuitspraak.

    Een sim-run leest ook niets en zou hier strikt genomen ook niet in horen. Dat filter
    is er bewust **niet**: het zou de betekenis van de dashboardkolom veranderen, en dat is
    een aparte beslissing dan het repareren van een run-record dat "klaar, 0, 0" beweerde
    voordat er iets gelezen was.
    """
    uniek: set[str] = set()
    for r in samengevat(audit_dir):
        if r.get("status") != "klaar":
            continue
        for b in r.get("bronnen") or []:
            if b:
                uniek.add(str(b))
    return sorted(uniek)
