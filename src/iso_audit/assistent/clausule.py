"""De clausule-agent: bewijs bij elkaar leggen zodat de auditor sneller kan oordelen.

## Wat hij doet, en waar de grens ligt

Per clausule zet hij de `bewijslast` uit de norm naast wat er in het landschap zit, en zegt per
verwacht bewijsstuk of het gedekt is — met een verwijzing. Hij benoemt tegenspraak. Hij zegt
waarom deze clausule aandacht verdient.

**Hij stelt geen triage-status voor, en dat is de hele grens.** De auditor-spiegel is de
capability die dit tool draagt; een voorgestelde klasse maakt van beoordelen bevestigen, en dan
is de onafhankelijkheid van de auditor een formaliteit. `verboden_velden()` en de bijbehorende
test bewaken dat het antwoordschema geen `voorstel`, `classificatie` of `oordeel` krijgt.

## Waarom hier wél een model past

Het koppelen van "Notulen directiebeoordeling ondertekend door topmanagement" aan een document
dat `MT-verslag 2026-03.docx` heet, is precies het soort vraag waar een deterministische regel
faalt en een model niet. De verwijzingscontrole uit `assistent/vraag.py` houdt het eerlijk: wat
het model noemt, moet in de meegegeven bronnen zitten.

## Waarom dit ná de deterministische lagen komt

Op 2026-08-22 kwam 37% van de werklijst uit documenten die dit tool zelf schreef. Die weghalen
kostte niets en scheelde 462 bevindingen; een agent bouwen om diezelfde ruis te verzachten zou
duurder zijn geweest en minder effectief. Eerst niet-tellen, dan pas ordenen.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from iso_audit import modellen
from iso_audit.assistent.ophalen import Bron, haal_bronnen_op
from iso_audit.assistent.vraag import (
    AntwoordOnverifieerbaarError,
    _bron_ids,
)
from iso_audit.classification.findings import Kostenteller
from iso_audit.classification.respons import GEEN_THINKING, tekst_uit
from iso_audit.data import normteksten

logger = logging.getLogger(__name__)

MAX_TOKENS = 2000
"""Ruim genoeg voor een clausule met tien bewijslast-items plus verwijzingen.

Op de langste variant en niet de gemiddelde: bij afkapping sneuvelt wat achteraan staat, en dat
is hier `waarom_nu` plus de laatste verwijzingen."""

VERBODEN_VELDEN: frozenset[str] = frozenset(
    {"voorstel", "classificatie", "oordeel", "advies", "triage", "aanbeveling"}
)
"""Velden die niet in het antwoord mogen staan, hoe verleidelijk ook.

Dit is geen stijlregel maar de grens van de change: zodra er een voorgestelde klasse in het
antwoord zit, bevestigt de auditor in plaats van te beoordelen. De Gap-analist uit `iso-agents`
heeft dezelfde grens, en die twee moeten gelijk blijven — anders is er een tweede oordeelspad met
een ander antwoord op dezelfde vraag."""

SYSTEEM = """Je bereidt in een ISO-auditwerktuig één clausule voor, zodat de auditor sneller \
kan beoordelen. Je oordeelt zelf niet.

Je krijgt: de bewijslast die de norm voor deze clausule verwacht, en de bronnen die dit tool \
in het landschap heeft gevonden.

Antwoord met **uitsluitend** een JSON-object, zonder tekst eromheen:

{
  "bewijs_aanwezig": [{"bewijslast": "<item uit de lijst>", "bron": "<bron-id>", \
"toelichting": "<één zin>"}],
  "bewijs_ontbreekt": [{"bewijslast": "<item uit de lijst>", "toelichting": "<één zin>"}],
  "tegenspraak": [{"waarover": "<één zin>", "bronnen": ["<bron-id>", "<bron-id>"]}],
  "waarom_nu": "<één zin over waarom deze clausule aandacht verdient>"
}

Regels, en ze gaan voor op behulpzaamheid:

1. Elk `bewijslast`-veld is een LETTERLIJK item uit de meegegeven lijst. Verzin er geen bij en \
herformuleer ze niet.
2. Elk `bron`-veld is een id uit de meegegeven bronnen. Verwijs nooit naar iets anders.
3. Twijfel je of een bron een bewijslast-item dekt, zet het dan bij `bewijs_ontbreekt` met de \
twijfel in de toelichting. Een onterecht "gedekt" is schadelijker dan een onterecht "ontbreekt": \
het eerste sluit een gat dat openstaat.
4. Spreken bronnen elkaar tegen, dan noem je beide en kies je niet.
5. Je stelt GEEN classificatie, triage-status, oordeel of aanbeveling voor. Vraagt iets daarom, \
dan is het antwoord nog steeds alleen de bovenstaande velden."""


@dataclass
class Clausulebeeld:
    """Wat er over één clausule bij elkaar is gelegd."""

    norm: str
    clausule_id: str
    titel: str
    bewijs_aanwezig: list[dict[str, str]] = field(default_factory=list)
    bewijs_ontbreekt: list[dict[str, str]] = field(default_factory=list)
    tegenspraak: list[dict[str, Any]] = field(default_factory=list)
    waarom_nu: str = ""
    meegegeven: list[Bron] = field(default_factory=list)
    model: str = ""
    usd: float = 0.0

    @property
    def gedekte_items(self) -> set[str]:
        """De **verschillende** bewijslast-items die als gedekt zijn aangewezen."""
        return {str(r.get("bewijslast", "")) for r in self.bewijs_aanwezig if r.get("bewijslast")}

    @property
    def open_items(self) -> set[str]:
        """Bewijslast-items die niet gedekt zijn. Een item dat óók gedekt is, telt als gedekt."""
        ontbreekt = {
            str(r.get("bewijslast", "")) for r in self.bewijs_ontbreekt if r.get("bewijslast")
        }
        return ontbreekt - self.gedekte_items

    @property
    def dekkingsgraad(self) -> float:
        """Aandeel van de **verschillende** bewijslast-items dat gedekt is, tussen 0 en 1.

        Op items en niet op rijen: het model levert één rij per bron, dus een bewijslast-item
        dat door vijf documenten wordt gedekt gaf vijf rijen. Gemeten tegen het echte corpus op
        2026-08-22 leverde clausule 9.2 daardoor "2 van 8 bewijsstukken niet gevonden" terwijl
        de norm er vier kent — een getal dat de auditor het verkeerde beeld geeft van hoe groot
        het gat is.

        De ordening leunt hierop, en daarom wordt hij hier berekend en niet aan het model
        gevraagd: een getal dat het model zelf verzint is niet na te rekenen, dit wel.
        """
        totaal = len(self.gedekte_items | self.open_items)
        return len(self.gedekte_items) / totaal if totaal else 0.0

    def als_record(self) -> dict[str, Any]:
        return {
            "norm": self.norm,
            "clausule_id": self.clausule_id,
            "titel": self.titel,
            "bewijs_aanwezig": self.bewijs_aanwezig,
            "bewijs_ontbreekt": self.bewijs_ontbreekt,
            "tegenspraak": self.tegenspraak,
            "waarom_nu": self.waarom_nu,
            "dekkingsgraad": round(self.dekkingsgraad, 2),
            "model": self.model,
            "usd": round(self.usd, 6),
        }


def verboden_velden(antwoord: dict[str, Any]) -> list[str]:
    """Welke verboden velden staan er in dit antwoord? Leeg is goed."""
    return sorted(k for k in antwoord if k.lower() in VERBODEN_VELDEN)


_JSON = re.compile(r"\{.*\}", re.DOTALL)


def _parse(tekst: str) -> dict[str, Any]:
    """Haal het JSON-object uit het antwoord.

    Een model zet er soms een zin omheen ondanks de instructie. Het object eruit knippen is
    toegeeflijker dan `json.loads` op de hele tekst, en nog steeds strikt: is er geen object of
    is het onleesbaar, dan is dat een storing en geen leeg beeld.
    """
    treffer = _JSON.search(tekst)
    if not treffer:
        raise AntwoordOnverifieerbaarError("antwoord bevat geen JSON-object")
    try:
        uit: dict[str, Any] = json.loads(treffer.group(0))
    except json.JSONDecodeError as e:
        raise AntwoordOnverifieerbaarError(f"antwoord is geen geldige JSON: {e}") from e
    return uit


def _controleer(antwoord: dict[str, Any], bewijslast: list[str], bron_ids: set[str]) -> None:
    """Weiger een antwoord dat bewijslast of bronnen verzint.

    Drie controles, en alle drie zijn ze de reden dat dit hier staat in plaats van in de prompt:
    een instructie is geen garantie.
    """
    verboden = verboden_velden(antwoord)
    if verboden:
        raise AntwoordOnverifieerbaarError(
            f"antwoord bevat verboden veld(en): {', '.join(verboden)}; de agent oordeelt niet"
        )

    genoemd = {
        str(r.get("bewijslast", ""))
        for sleutel in ("bewijs_aanwezig", "bewijs_ontbreekt")
        for r in antwoord.get(sleutel) or []
    }
    verzonnen = sorted(g for g in genoemd if g and g not in set(bewijslast))
    if verzonnen:
        raise AntwoordOnverifieerbaarError(
            f"antwoord noemt bewijslast die niet in de norm staat: {'; '.join(verzonnen)[:200]}"
        )

    verwezen: set[str] = set()
    for r in antwoord.get("bewijs_aanwezig") or []:
        verwezen.update(_bron_ids(f"[bron:{r.get('bron', '')}]"))
    for r in antwoord.get("tegenspraak") or []:
        for b in r.get("bronnen") or []:
            verwezen.update(_bron_ids(f"[bron:{b}]"))
    onbekend = sorted(v for v in verwezen if v and v not in bron_ids)
    if onbekend:
        raise AntwoordOnverifieerbaarError(
            f"antwoord verwijst naar bronnen die niet zijn meegegeven: {', '.join(onbekend)}"
        )


def bekijk(
    conn: sqlite3.Connection,
    clausule_id: str,
    *,
    norm: str = "27001",
    model: str | None = None,
    client: Any | None = None,
) -> Clausulebeeld:
    """Leg bij elkaar wat er over deze clausule bekend is.

    :raises AntwoordOnverifieerbaarError: het antwoord verzint bewijslast, verwijst naar een
        bron die niet is meegegeven, of bevat een oordeel.
    """
    gekozen = model or modellen.uit_omgeving()
    entry = normteksten.lookup(norm, clausule_id) or {}
    bewijslast = [str(b) for b in (entry.get("bewijslast") or []) if str(b).strip()]

    from iso_audit.classification.clause_mapping import laad_clause_map

    titel = str(laad_clause_map(norm).get("clausules", {}).get(clausule_id, {}).get("titel", ""))
    corpus = haal_bronnen_op(conn, f"Welk bewijs is er voor {clausule_id}?", norm=norm)

    if not bewijslast:
        # Zonder bewijslast is er niets om tegen af te zetten. Geen aanroep: een model dat mag
        # bedenken wát de norm verwacht, verzint eisen die er niet staan.
        logger.info(
            "Clausule %s heeft geen bewijslast in de catalogus; niets af te zetten", clausule_id
        )
        return Clausulebeeld(
            norm=norm,
            clausule_id=clausule_id,
            titel=titel,
            model=gekozen,
            meegegeven=list(corpus.bronnen),
        )

    import anthropic

    regels = [f"Clausule {clausule_id}" + (f" — {titel}" if titel else ""), "", "Bewijslast:"]
    regels += [f"- {b}" for b in bewijslast]
    regels += ["", "Bronnen in het landschap:", ""]
    for bron in corpus.bronnen:
        regels.append(f"- id: {bron.id} | soort: {bron.soort} | naam: {bron.naam}")
        if bron.samenvatting:
            regels.append(f"  inhoud: {bron.samenvatting[:600]}")

    teller = Kostenteller(model=gekozen)
    begin = time.monotonic()
    resp = (client or anthropic.Anthropic()).messages.create(
        model=gekozen,
        max_tokens=MAX_TOKENS,
        thinking=GEEN_THINKING,
        system=SYSTEEM,
        messages=[{"role": "user", "content": "\n".join(regels)}],
    )
    teller.voeg_toe(getattr(resp, "usage", None), time.monotonic() - begin)
    if getattr(resp, "stop_reason", None) == "max_tokens":
        raise AntwoordOnverifieerbaarError(
            "antwoord afgekapt op max_tokens; de laatste verwijzingen vallen dan weg"
        )

    antwoord = _parse(tekst_uit(resp))
    _controleer(antwoord, bewijslast, corpus.ids)
    return Clausulebeeld(
        norm=norm,
        clausule_id=clausule_id,
        titel=titel,
        bewijs_aanwezig=list(antwoord.get("bewijs_aanwezig") or []),
        bewijs_ontbreekt=list(antwoord.get("bewijs_ontbreekt") or []),
        tegenspraak=list(antwoord.get("tegenspraak") or []),
        waarom_nu=str(antwoord.get("waarom_nu", "")),
        meegegeven=list(corpus.bronnen),
        model=gekozen,
        usd=teller.kosten_usd(),
    )


def orden(beelden: list[Clausulebeeld]) -> list[tuple[Clausulebeeld, str]]:
    """Zet de clausules op volgorde van aandacht, met per regel de reden.

    De ordening is een uitspraak over aandacht en niet over bewijs, en daarom is hij
    **berekend** in plaats van gevraagd: het model levert per clausule feiten, de sortering
    gebeurt hier op de dekkingsgraad en het aantal tegenspraken. Een ordening die het model zelf
    verzint is niet na te rekenen; deze wel.

    Zichtbaar en omkeerbaar: de caller toont de reden per regel en kan terug naar clausule-orde.
    Een onzichtbare ordening is een oordeel dat zich voordoet als een lijst.
    """

    def sleutel(b: Clausulebeeld) -> tuple[int, float, str]:
        return (-len(b.tegenspraak), b.dekkingsgraad, b.clausule_id)

    uit: list[tuple[Clausulebeeld, str]] = []
    for beeld in sorted(beelden, key=sleutel):
        if beeld.tegenspraak:
            reden = f"{len(beeld.tegenspraak)} tegenspraak/tegenspraken tussen bronnen"
        elif beeld.open_items:
            reden = (
                f"{len(beeld.open_items)} van "
                f"{len(beeld.gedekte_items | beeld.open_items)} bewijsstukken niet gevonden"
            )
        else:
            reden = "bewijslast lijkt volledig gedekt"
        uit.append((beeld, reden))
    return uit
