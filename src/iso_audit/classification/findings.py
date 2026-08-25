"""Finding-classifier — consolideert audit/finding_classification.py (v1) en
audit/finding_classification_20260420.py (v2) per milestone B §2.2.5.

v2-functionaliteit overgenomen (caching, kostenteller, rehash, dry-run-cost,
mis-tag-filter, sharpness-prompts). `review_en_bevestig` uit v1 toegevoegd
(de enige niet-v2-functie waar v2 op leunde). De legacy `sla_op_in_sheets`-
wrapper is geschrapt; callers importeren rechtstreeks uit
`iso_audit.reporting.sheets_gws`.

Verbeteringen t.o.v. v1:

1. **System prompt met `cache_control` (ephemeral)** — bedoeld om statische delen
   uit cache te lezen. LET OP: dit slaat bij de huidige promptgroottes **niet aan**.
   De systeem-prompts zijn 122-726 tokens en het minimum cacheerbare prefix is 4096
   tokens op Haiku 4.5, 1024 op Sonnet 5 en 512 op Opus 5; onder dat minimum cachet
   de API stil niet. Gemeten over 215 classificaties in de referentie-checkout
   (2026-08-17): cache_read en cache_write allebei nul. De eerdere claim "~10x
   goedkoper" stond hier jarenlang en was niet waar.
2. **Per-call token usage + kostenlogging** via `Kostenteller`.
3. **`schat_kosten`** — kostenschatting vooraf zonder API-calls.
4. **Rehash / selective re-classify** — UPSERT i.p.v. INSERT-OR-IGNORE,
   checkpoint op `(doc_id, clausule_id, norm)`.
5. **`AUDIT_CLASSIFICATION_MODEL`-env** voor model-keuze (default Haiku 4.5). Raakt
   alleen dit bestand: memo-tekst, thema-bepaling en rapportgeneratie draaien op
   `modellen.STANDAARD`.

Gebruik:
    # Alleen kostenschatting (géén API-calls):
    python -m iso_audit.classification.findings --dry-run-cost \\
        --norm 27001 --chapter 7

    # Rehash chapter 7 (verse API-calls, bestaande rows worden vervangen):
    python -m iso_audit.classification.findings --norm 27001 --chapter 7 --rehash
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import anthropic
from dotenv import load_dotenv

from iso_audit import modellen
from iso_audit.classification.respons import GEEN_THINKING, OnleesbaarAntwoordError, tekst_uit

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_MODEL = modellen.uit_omgeving()
MAX_TEKST = 2000
MIRO_BATCH = 20
CHARS_PER_TOKEN = 4  # ruwe schatting voor dry-run-cost

# Prijzen USD per miljoen tokens. Bron: anthropic.com/pricing.
# Cache-write 5m = 1.25x input; cache-read = 0.1x input (standaard tariefstructuur).
#
# LET OP — op 2026-08-14 gecorrigeerd, niet alleen verversd. De oude tabel had Haiku
# 4.5 op 0.80/4.00 (werkelijk 1.00/5.00), waardoor elke kostenregel in een
# auditrapport ~25% te laag uitviel, en Opus op 15.00/75.00 (werkelijk 5.00/25.00).
# Een te lage kostenpost is schadelijker dan geen kostenpost, omdat hij compleet lijkt.
PRIJZEN_PEILDATUM = "2026-08-20"
"""Datum waarop deze tarieven zijn gecontroleerd. Prijzen wijzigen buiten deze repo
om; rapporteer deze datum mee bij elk kostenbedrag."""

PRIJZEN_GRONDSLAG = "werkelijk tarief"
"""Wélke prijs hier staat: `lijstprijs` of `werkelijk tarief` (inclusief tijdelijke acties).

Een bedrag met een peildatum maar zonder grondslag is niet navertelbaar. Op verzoek van de
opdrachtgever (2026-08-20) staat hier het **werkelijke tarief**: het bedrag in het rapport
moet zo dicht mogelijk bij de factuur liggen. Concreet raakt dat één regel: Sonnet 5 heeft tot
en met 31 augustus 2026 een introductietarief van $2,00/$10,00 in plaats van $3,00/$15,00 per
miljoen tokens.

Wat dit *niet* is: de factuur. Hier staat het publieke tarief dat op de peildatum gold. Heeft
Conduction een eigen afspraak met Anthropic (volumekorting, commitment), dan wijkt de factuur
daar nog van af en is dit een bovengrens.

Bewust geen datumlogica in de tabel die zelf tussen tarieven kiest: dat is een tweede
administratie die achterloopt op de leverancier, precies wat `PRIJZEN_PEILDATUM` moet
voorkomen. In plaats daarvan noteert `TIJDELIJK_TARIEF_TOT` welk tarief tijdelijk is, en
waarschuwt `prijs_voor()` zodra die datum verstreken is."""

TIJDELIJK_TARIEF_TOT: dict[str, str] = {
    modellen.SONNET_5: "2026-08-31",
}
"""Modellen waarvan het tarief hieronder een tijdelijke actie is, met de einddatum.

Zonder dit vervalt de keuze voor werkelijke tarieven stil: op 1 september loopt het
introtarief van Sonnet 5 af, staat er nog $2,00 in de tabel, en rapporteert elk auditrapport
een derde te laag. Een te laag bedrag is schadelijker dan geen bedrag, want het ziet compleet
uit — dezelfde reden waarom de Haiku-prijs op 2026-08-14 is gecorrigeerd."""

PRIJZEN: dict[str, dict[str, float]] = {
    modellen.HAIKU_4_5: {
        "input": 1.00,
        "output": 5.00,
        "cache_write_5m": 1.25,
        "cache_read": 0.10,
    },
    # Introtarief t/m 2026-08-31; lijstprijs is 3.00/15.00. Zie TIJDELIJK_TARIEF_TOT.
    modellen.SONNET_5: {
        "input": 2.00,
        "output": 10.00,
        "cache_write_5m": 2.50,
        "cache_read": 0.20,
    },
    modellen.OPUS_5: {
        "input": 5.00,
        "output": 25.00,
        "cache_write_5m": 6.25,
        "cache_read": 0.50,
    },
}
"""Prijzen USD per miljoen tokens, op de alias gesleuteld. Een gedateerd model-ID uit een
historisch record wordt door `prijs_voor()` naar zijn alias herleid; dat scheelt een tweede
regel per model die uit de eerste kan lopen."""

KIESBARE_MODELLEN: tuple[str, ...] = modellen.KIESBAAR
"""Doorgeefluik naar `iso_audit.modellen.KIESBAAR`; de UI en de tests importeren dit hier."""

_TARIEF_GEWAARSCHUWD: set[str] = set()


def prijs_voor(model: str) -> dict[str, float] | None:
    """Tarieven voor `model`, of `None` als het model geen prijsregel heeft.

    Herleidt een gedateerd model-ID naar zijn alias, zodat historische records uit de
    audit-trail geprijsd blijven zonder dubbele regels in de tabel.

    Waarschuwt eenmalig per model als het tarief een verlopen tijdelijke actie is: dan
    staat er een te laag bedrag in de tabel en dat is erger dan geen bedrag.
    """
    alias = modellen.normaliseer(model)
    tot = TIJDELIJK_TARIEF_TOT.get(alias)
    if tot and datetime.now(UTC).date().isoformat() > tot and alias not in _TARIEF_GEWAARSCHUWD:
        _TARIEF_GEWAARSCHUWD.add(alias)
        logger.warning(
            "Tarief voor %s was een actie tot %s en is verlopen; het gerapporteerde bedrag "
            "is te laag. Werk PRIJZEN en PRIJZEN_PEILDATUM bij.",
            alias,
            tot,
        )
    return PRIJZEN.get(alias)


# ---------------------------------------------------------------------------
# Token + kosten tracking
# ---------------------------------------------------------------------------


@dataclass
class Kostenteller:
    """Houdt token-verbruik en kosten bij over één classifier-run."""

    model: str = DEFAULT_MODEL
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    elapsed_s: float = 0.0
    fouten: int = 0

    def voeg_toe(self, usage: Any, elapsed_s: float) -> None:
        self.calls += 1
        self.elapsed_s += elapsed_s
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0

    def kosten_usd(self) -> float:
        p = prijs_voor(self.model)
        if not p:
            return 0.0
        return (
            self.input_tokens * p["input"]
            + self.output_tokens * p["output"]
            + self.cache_write_tokens * p["cache_write_5m"]
            + self.cache_read_tokens * p["cache_read"]
        ) / 1_000_000

    def rapport(self) -> str:
        return (
            f"model={self.model} calls={self.calls} fouten={self.fouten} | "
            f"input={self.input_tokens:,} (cache_read={self.cache_read_tokens:,} "
            f"cache_write={self.cache_write_tokens:,}) | "
            f"output={self.output_tokens:,} | "
            f"elapsed={self.elapsed_s:.1f}s | "
            f"kosten=${self.kosten_usd():.4f}"
        )


# ---------------------------------------------------------------------------
# Prompts — system (statisch, gecached) + user (variabel)
# ---------------------------------------------------------------------------


def _laad_prompt(naam: str) -> str:
    """Lees een systeemprompt uit `classification/prompts/<naam>.md`.

    De prompts stonden tot 2026-08-24 als tripelquoted strings in dit bestand, terwijl
    `CLAUDE.md` belooft dat ze versiegestuurd op schijf staan. Dat is geen nettigheid: de
    prompt bepaalt of iets een NC of een OFI wordt, en `classifications.prompt_versie` bewaart
    alleen een sha256 — daarmee is te zien **dát** de prompt veranderde, niet wat er stond.

    Via `importlib.resources` en niet via een pad, zodat het ook werkt vanuit een wheel.
    """
    from importlib.resources import files

    return (files("iso_audit.classification.prompts") / f"{naam}.md").read_text(encoding="utf-8")


_SYSTEM_SCHERP = _laad_prompt("v2-scherp")
_SYSTEM_GENUANCEERD = _laad_prompt("v2-genuanceerd")
_SYSTEM_MIRO = _laad_prompt("v2-miro")


def _systeem_voor(scherpte: float, herkomst: str = "Drive") -> str:
    if herkomst == "Miro":
        return _SYSTEM_MIRO
    return _SYSTEM_SCHERP if scherpte >= 0.75 else _SYSTEM_GENUANCEERD


def _bouw_doc_user_prompt(
    doc: dict[str, Any], clausule_ids: list[str], clausules: dict[str, Any]
) -> str:
    clausules_lijst = "\n".join(
        f"- {cid}: {clausules.get(cid, {}).get('titel', cid)}" for cid in clausule_ids
    )
    return (
        f"Document: {doc['naam']}\n\n"
        f"Tekst:\n---\n{doc['tekst'][:MAX_TEKST]}\n---\n\n"
        f"Clausules:\n{clausules_lijst}\n"
    )


def _bouw_miro_user_prompt(notities: list[dict[str, Any]], clausules: dict[str, Any]) -> str:
    regels: list[str] = []
    for n in notities:
        nid = n.get("miro_item_id", n.get("id", "?"))
        cid = n.get("clausule", "?")
        titel = clausules.get(cid, {}).get("titel", "")
        tekst = (n.get("tekst") or "")[:200]
        regels.append(f"- ID: {nid} | Clausule: {cid} {titel} | Tekst: {tekst}")
    return "Items:\n" + "\n".join(regels)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


SDK_NIET_STREAMEND_PLAFOND = 21_333
"""Boven dit output-budget weigert de SDK een niet-streamende aanroep.

`_calculate_nonstreaming_timeout` in `anthropic/_base_client.py` rekent
`3600 * max_tokens / 128000` als verwachte duur en raist een `ValueError` zodra die boven de
tien minuten komt. Dat is `max_tokens > 21333`, en met `450 * n + 128` gebeurt dat vanaf 48
clausules in één document.

Waarom dit getal hier staat en niet als grens wordt gebruikt: het budget hoort bij de
werkelijkheid van het model, niet bij een SDK-drempel. Daarom streamen we de aanroep — dan
geldt de drempel niet. Het getal staat er om de keuze uitlegbaar te houden."""


def _vraag_model(client: Any, **kw: Any) -> Any:
    """Eén classificatie-aanroep, streamend, met het volledige bericht als resultaat.

    Streamend en niet `messages.create`, om één gemeten reden. Op 2026-08-21 strandde een
    productierun op document 2 van 119: `Bevindingen_beide_v3.3_2026-05-05.csv` raakt 63
    clausules, dus `max_tokens` werd 28.478, en de SDK weigert dat niet-streamend met
    `ValueError: Streaming is required for operations that may take longer than 10 minutes`.
    Die fout is geen `APIError`, dus hij glipte langs de per-document foutopvang en nam de
    hele run mee — 117 documenten die niet meer geclassificeerd werden.

    Twee dingen kwamen daar samen: het ruimere budget van 2026-08-17 (`450 * n + 128`) en de
    dekkingsuitbreiding van 2026-08-18, die `text/csv` leesbaar maakte en dat bestand met zijn
    63 clausules het landschap in bracht.

    `get_final_message()` levert hetzelfde object als een niet-streamende aanroep — content,
    usage en `stop_reason` — zodat de afkap-controle en de kostenteller ongewijzigd werken.
    """
    with client.messages.stream(**kw) as stroom:
        bericht: Any = stroom.get_final_message()
    return bericht


def _max_tokens_voor(aantal_items: int) -> int:
    """Output-budget per classificatie-aanroep.

    Gemeten op 2026-08-17 tegen de echte API, uitvoertokens per item bij een compleet
    antwoord (`stop_reason: end_turn`):

    | model | 1 clausule | 3 clausules |
    |---|---|---|
    | Haiku 4.5 | 193 | — |
    | Sonnet 5 | 276 | 218 |
    | Opus 5 | 410 | 365 |

    Het budget stond op `150 * n + 64` en was daarmee op Haiku gekalibreerd. Sonnet 5 en
    Opus 5 werden afgekapt (`stop_reason: max_tokens`), waarna `_parse_json_list` geen
    sluithaak vond en stil een lege lijst teruggaf — zelfde uitkomst als een leeg oordeel.

    450 dekt Opus 5 met marge; 128 is voor de JSON-omlijsting. Ruimer zetten kost niets: je
    betaalt voor gegenereerde tokens, niet voor het plafond, en bij `max_tokens=4000` stopten
    beide modellen uit zichzelf rond 276 en 410. Zodra thinking aangaat moet dit budget
    opnieuw omhoog, want dan begrenst `max_tokens` thinking én antwoord samen.
    """
    return 450 * aantal_items + 128


def _parse_json_list(tekst: str) -> list[dict[str, Any]]:
    """Extract de eerste JSON-array uit een respons-tekst."""
    start = tekst.find("[")
    eind = tekst.rfind("]") + 1
    if start == -1 or eind <= start:
        return []
    data: list[dict[str, Any]] = json.loads(tekst[start:eind])
    return data


# Patronen die aangeven dat een bevinding eigenlijk een mis-tagging op Miro is
# (item verwijst naar een clausule waar het niet thuishoort) — geen echte NC
# tegen Conduction, maar data-kwaliteit van het Miro-bord. Skippen uit DB.
_MIRO_MISTAG_PATRONEN: tuple[str, ...] = (
    "misclassificatie",
    "niet relevant voor clausule",
    "niet relevant voor deze clausule",
    "hoort niet bij clausule",
    "hoort niet bij deze clausule",
    "item verwijst naar clausule",
    "item verwijst alleen naar",
    "item noemt alleen",
    "item bevat alleen",
    "vraag over",
)


def _is_miro_mistag(beschrijving: str) -> bool:
    if not beschrijving:
        return False
    lower = beschrijving.lower().lstrip("*_ \t")
    return any(lower.startswith(p) or (p in lower[:60]) for p in _MIRO_MISTAG_PATRONEN)


def _maak_system_param(system_tekst: str) -> list[dict[str, Any]]:
    """System prompt met ephemeral cache_control voor 5m prompt caching."""
    return [{"type": "text", "text": system_tekst, "cache_control": {"type": "ephemeral"}}]


def _classificeer_doc(
    doc: dict[str, Any],
    clausule_ids: list[str],
    clausules: dict[str, Any],
    client: anthropic.Anthropic,
    teller: Kostenteller,
    scherpte: float = 1.0,
    conn: sqlite3.Connection | None = None,
    audit_id: str = "",
) -> list[dict[str, Any]]:
    """Eén API-call per doc (alle opgegeven clausules in één response).

    Als `conn` + `audit_id` zijn meegegeven, wordt de classificatie vóór
    JSON-parsing gepersisteerd in `classifications` (§2.6.4).
    """
    system = _systeem_voor(scherpte, herkomst="Drive")
    user = _bouw_doc_user_prompt(doc, clausule_ids, clausules)
    t0 = time.time()
    try:
        resp = _vraag_model(
            client,
            model=teller.model,
            max_tokens=_max_tokens_voor(len(clausule_ids)),
            thinking=GEEN_THINKING,
            system=_maak_system_param(system),
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIError as e:
        teller.fouten += 1
        logger.warning("API-fout (doc %s): %s", doc.get("naam", "")[:40], e)
        return []
    elapsed = time.time() - t0
    teller.voeg_toe(resp.usage, elapsed)
    # Eerst de ruwe respons vastleggen, dan pas oordelen: een onleesbaar antwoord is precies
    # het geval waarin je de raw output in de trail wil hebben om te zien wát er terugkwam.
    onleesbaar: str | None = None
    try:
        raw = tekst_uit(resp)
    except OnleesbaarAntwoordError as e:
        raw = ""
        onleesbaar = str(e)
    # Afgekapt is niet leeg. Bij `max_tokens` mist de sluithaak, vindt `_parse_json_list`
    # geen array en geeft die stil een lege lijst terug — niet te onderscheiden van "het
    # model vond niets". Gemeten op 2026-08-17: precies zo verdwenen de bevindingen van
    # Sonnet 5 en Opus 5.
    if onleesbaar is None and getattr(resp, "stop_reason", None) == "max_tokens":
        onleesbaar = "antwoord afgekapt op max_tokens; het budget is te krap voor dit model"
    if conn is not None and audit_id:
        from iso_audit.store import log_classification

        log_classification(
            conn,
            audit_id=audit_id,
            finding_id=f"{(doc.get('herkomst') or 'drive').lower()}:{doc['id']}:{','.join(sorted(clausule_ids))}",
            system_prompt=system,
            user_prompt=user,
            model=teller.model,
            raw_output=raw,
            usage=_usage_dict(resp.usage),
            elapsed_s=elapsed,
        )
    if onleesbaar is not None:
        # Tokens verbruikt, geen antwoord kunnen lezen: storing, geen leeg oordeel.
        teller.fouten += 1
        logger.warning("Onleesbaar antwoord (doc %s): %s", doc.get("naam", "")[:40], onleesbaar)
        return []
    try:
        return _parse_json_list(raw)
    except (json.JSONDecodeError, IndexError) as e:
        teller.fouten += 1
        logger.warning("JSON-parse fout (doc %s): %s", doc.get("naam", "")[:40], e)
        return []


def _classificeer_miro_batch(
    notities: list[dict[str, Any]],
    clausules: dict[str, Any],
    client: anthropic.Anthropic,
    teller: Kostenteller,
    conn: sqlite3.Connection | None = None,
    audit_id: str = "",
) -> list[dict[str, Any]]:
    """Eén API-call per Miro-batch (default 20 items).

    Als `conn` + `audit_id` zijn meegegeven, wordt de classificatie vóór
    JSON-parsing gepersisteerd in `classifications` (§2.6.4).
    """
    system = _systeem_voor(scherpte=1.0, herkomst="Miro")
    user = _bouw_miro_user_prompt(notities, clausules)
    t0 = time.time()
    try:
        resp = _vraag_model(
            client,
            model=teller.model,
            max_tokens=_max_tokens_voor(len(notities)),
            thinking=GEEN_THINKING,
            system=_maak_system_param(system),
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.APIError as e:
        teller.fouten += 1
        logger.warning("API-fout (Miro batch): %s", e)
        return []
    elapsed = time.time() - t0
    teller.voeg_toe(resp.usage, elapsed)
    onleesbaar: str | None = None
    try:
        raw = tekst_uit(resp)
    except OnleesbaarAntwoordError as e:
        raw = ""
        onleesbaar = str(e)
    if onleesbaar is None and getattr(resp, "stop_reason", None) == "max_tokens":
        onleesbaar = "antwoord afgekapt op max_tokens; het budget is te krap voor dit model"
    if conn is not None and audit_id:
        from iso_audit.store import log_classification

        ids = ",".join(sorted(n.get("miro_item_id", n.get("id", "")) for n in notities))
        log_classification(
            conn,
            audit_id=audit_id,
            finding_id=f"miro:{ids}",
            system_prompt=system,
            user_prompt=user,
            model=teller.model,
            raw_output=raw,
            usage=_usage_dict(resp.usage),
            elapsed_s=elapsed,
        )
    if onleesbaar is not None:
        teller.fouten += 1
        logger.warning("Onleesbaar antwoord (Miro batch): %s", onleesbaar)
        return []
    try:
        return _parse_json_list(raw)
    except (json.JSONDecodeError, IndexError) as e:
        teller.fouten += 1
        logger.warning("JSON-parse fout (Miro batch): %s", e)
        return []


def _usage_dict(usage: Any) -> dict[str, Any]:
    """Converteer Anthropic-usage-object naar JSON-serialiseerbare dict."""
    if usage is None:
        return {}
    return {
        "input_tokens": getattr(usage, "input_tokens", 0),
        "output_tokens": getattr(usage, "output_tokens", 0),
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0),
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0),
    }


# ---------------------------------------------------------------------------
# DB helpers — checkpoint-granulariteit op (doc_id, clausule_id, norm)
# ---------------------------------------------------------------------------


def _gedaan_per_doc(conn: sqlite3.Connection, norm: str) -> dict[str, set[str]]:
    """`{doc_id: {clausule_id, ...}}` van reeds geclassificeerde document-bronnen.

    Alle niet-Miro-bronnen (Drive, Jira, Planning, …) gaan via het document-pad
    en delen deze dedup; Miro heeft een eigen pad (`_gedaan_miro`).
    """
    result: dict[str, set[str]] = defaultdict(set)
    rows = conn.execute(
        "SELECT doc_id, clausule_id FROM bevindingen WHERE herkomst != 'Miro' AND norm=?",
        (norm,),
    ).fetchall()
    for doc_id, cid in rows:
        result[doc_id].add(cid)
    return result


def _gedaan_miro(conn: sqlite3.Connection, norm: str) -> set[str]:
    """Set van Miro-item-IDs die al een bevinding hebben voor deze norm."""
    rows = conn.execute(
        "SELECT DISTINCT doc_id FROM bevindingen WHERE herkomst='Miro' AND norm=?",
        (norm,),
    ).fetchall()
    return {r[0] for r in rows}


def _upsert_bevindingen(
    conn: sqlite3.Connection, bevindingen: list[dict[str, Any]], norm: str
) -> None:
    """UPSERT: overschrijft bestaande rij bij conflict op composite key.

    `norm` is de run-parameter en kan `beide` zijn; een bevinding die zijn eigen norm meebrengt
    (uit de koppeling) wint daarvan. Zonder die voorrang kreeg elke bevinding `beide` en moest
    `run_job._resolve_standard()` achteraf raden — met een half gevulde norm-DB raadde die er op
    2026-08-24 448 van de 903 verkeerd.
    """
    for bev in bevindingen:
        rij_norm = str(bev.get("norm") or "") or norm
        conn.execute(
            """
            INSERT INTO bevindingen
                (doc_id, herkomst, clausule_id, norm, classificatie, ernst, beschrijving,
                 onderbouwing, onbruikbaar, pre_classificatie, document_naam, classified_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
            ON CONFLICT(doc_id, herkomst, clausule_id, norm) DO UPDATE SET
                classificatie    = excluded.classificatie,
                ernst            = excluded.ernst,
                beschrijving     = excluded.beschrijving,
                onderbouwing     = excluded.onderbouwing,
                onbruikbaar      = excluded.onbruikbaar,
                pre_classificatie= excluded.pre_classificatie,
                document_naam    = excluded.document_naam,
                classified_at    = excluded.classified_at
            """,
            (
                bev["_doc_id"],
                bev["herkomst"],
                bev["clausule"],
                rij_norm,
                bev["classificatie"],
                bev.get("ernst"),
                bev.get("beschrijving", ""),
                bev.get("onderbouwing", ""),
                1 if bev.get("onbruikbaar") else 0,
                bev.get("pre_classificatie"),
                bev["document_naam"],
            ),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Kostenschatting vooraf (geen API-calls)
# ---------------------------------------------------------------------------


@dataclass
class _KostenSchatting:
    model: str
    calls: int = 0
    input_regulier: int = 0
    input_cache_read: int = 0
    input_cache_write: int = 0
    output_budget: int = 0
    kosten_usd_schatting: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "calls": self.calls,
            "input_regulier": self.input_regulier,
            "input_cache_read": self.input_cache_read,
            "input_cache_write": self.input_cache_write,
            "output_budget": self.output_budget,
            "kosten_usd_schatting": round(self.kosten_usd_schatting, 4),
        }


def schat_kosten(
    gekoppelde_docs: list[dict[str, Any]],
    miro_notities: list[dict[str, Any]],
    clause_map: dict[str, Any],
    norm: str = "beide",
    scherpte: float = 1.0,
    model: str = DEFAULT_MODEL,
    rehash: bool = False,
) -> dict[str, Any]:
    """Schat token-verbruik en kosten zonder API-calls te doen.

    Systeem-prompt = cache-write bij 1e call, cache-read daarna. Per doc:
    input ≈ user-prompt chars / 4; output ≈ 150 tokens per aantal clausules.
    Miro: 1 call per batch van `MIRO_BATCH` notities. Bij `rehash=False`
    worden (doc, clausule) die al in DB staan overgeslagen.
    """
    from iso_audit.store import initialiseer, verbinding

    conn = verbinding()
    initialiseer(conn)
    gedaan = _gedaan_per_doc(conn, norm)
    gedaan_miro_ids = _gedaan_miro(conn, norm)
    conn.close()

    system_tekst = _systeem_voor(scherpte, herkomst="Drive")
    system_tokens = max(len(system_tekst) // CHARS_PER_TOKEN, 1024)
    miro_system_tokens = max(len(_SYSTEM_MIRO) // CHARS_PER_TOKEN, 1024)

    p = prijs_voor(model) or {"input": 0, "output": 0, "cache_write_5m": 0, "cache_read": 0}

    s = _KostenSchatting(model=model)

    doc_cache_gebruikt = False
    for doc in gekoppelde_docs:
        doc_id = doc["id"]
        alle_cids = list(doc.get("clausules", []))
        if not alle_cids:
            continue
        cids_todo = (
            alle_cids if rehash else [c for c in alle_cids if c not in gedaan.get(doc_id, set())]
        )
        if not cids_todo:
            continue
        user_chars = (
            len(doc.get("naam", ""))
            + min(len(doc.get("tekst", "")), MAX_TEKST)
            + 50 * len(cids_todo)
        )
        user_tokens = user_chars // CHARS_PER_TOKEN
        if not doc_cache_gebruikt:
            s.input_cache_write += system_tokens
            s.input_regulier += user_tokens
            doc_cache_gebruikt = True
        else:
            s.input_cache_read += system_tokens
            s.input_regulier += user_tokens
        s.output_budget += 150 * len(cids_todo)
        s.calls += 1

    todo_miro = [
        n
        for n in miro_notities
        if rehash or n.get("miro_item_id", n.get("id")) not in gedaan_miro_ids
    ]
    miro_cache_gebruikt = False
    for i in range(0, len(todo_miro), MIRO_BATCH):
        batch = todo_miro[i : i + MIRO_BATCH]
        user_chars = sum(300 for _ in batch)
        user_tokens = user_chars // CHARS_PER_TOKEN
        if not miro_cache_gebruikt:
            s.input_cache_write += miro_system_tokens
            s.input_regulier += user_tokens
            miro_cache_gebruikt = True
        else:
            s.input_cache_read += miro_system_tokens
            s.input_regulier += user_tokens
        s.output_budget += 150 * len(batch)
        s.calls += 1

    s.kosten_usd_schatting = (
        s.input_regulier * p["input"]
        + s.input_cache_read * p["cache_read"]
        + s.input_cache_write * p["cache_write_5m"]
        + s.output_budget * p["output"]
    ) / 1_000_000
    return s.as_dict()


# ---------------------------------------------------------------------------
# Hoofdfunctie
# ---------------------------------------------------------------------------


@dataclass
class _ClassifyContext:
    """Interne staat tijdens een classifier-run; verkleint argument-passing."""

    conn: sqlite3.Connection
    client: anthropic.Anthropic
    teller: Kostenteller
    clausules: dict[str, Any]
    norm: str
    scherpte: float
    rehash: bool
    audit_id: str = ""
    gedaan: dict[str, set[str]] = field(default_factory=dict)
    gedaan_miro_ids: set[str] = field(default_factory=set)


def _maak_audit_id() -> str:
    """Genereer een run-scoped audit_id (UTC-tijdstempel)."""
    return f"audit-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def classificeer_alle_bevindingen(
    gekoppelde_docs: list[dict[str, Any]],
    miro_notities: list[dict[str, Any]],
    clause_map: dict[str, Any],
    norm: str = "beide",
    scherpte: float = 1.0,
    rehash: bool = False,
    model: str | None = None,
    audit_id: str | None = None,
    op_kosten: Callable[[Kostenteller], None] | None = None,
) -> list[dict[str, Any]]:
    """Classificeer Drive-docs en Miro-notities; UPSERT in `bevindingen`-tabel.

    `audit_id` groepeert de classifications-rows van deze run. Default: een
    UTC-tijdstempel.

    `op_kosten` wordt aangeroepen met de kostenteller zodra de classificatie klaar is, zodat
    de aanroeper de kosten in het run-record kan zetten. Een callback en geen tweede
    returnwaarde: dat zou elke bestaande aanroeper breken voor één veld.

    Returnt alle bevindingen voor de norm uit de DB (incl. eerdere runs)
    voor downstream-rapportage.
    """
    from iso_audit.store import initialiseer, verbinding

    teller = Kostenteller(model=model or DEFAULT_MODEL)
    conn = verbinding()
    initialiseer(conn)

    ctx = _ClassifyContext(
        conn=conn,
        client=anthropic.Anthropic(),
        teller=teller,
        clausules=clause_map.get("clausules", {}),
        norm=norm,
        scherpte=scherpte,
        rehash=rehash,
        audit_id=audit_id or _maak_audit_id(),
        gedaan=_gedaan_per_doc(conn, norm),
        gedaan_miro_ids=_gedaan_miro(conn, norm),
    )

    _classify_drive(ctx, gekoppelde_docs)
    _classify_miro(ctx, miro_notities)
    logger.info("Kosten-rapport: %s", teller.rapport())
    if op_kosten is not None:
        op_kosten(teller)

    rows = conn.execute(
        "SELECT * FROM bevindingen WHERE norm=? ORDER BY clausule_id", (norm,)
    ).fetchall()
    conn.close()

    alle: list[dict[str, Any]] = [
        {
            "clausule": r["clausule_id"],
            "clausule_titel": ctx.clausules.get(r["clausule_id"], {}).get(
                "titel", r["clausule_id"]
            ),
            "document_naam": r["document_naam"] or "",
            "doc_id": r["doc_id"],
            "herkomst": r["herkomst"],
            "classificatie": r["classificatie"],
            "beschrijving": r["beschrijving"] or "",
            "onderbouwing": r["onderbouwing"] or "",
            "pre_classificatie": r["pre_classificatie"],
            "id": r["id"],
        }
        for r in rows
    ]

    nc = sum(1 for b in alle if b["classificatie"] == "NC")
    ofi = sum(1 for b in alle if b["classificatie"] == "OFI")
    pos = sum(1 for b in alle if b["classificatie"] == "positief")
    logger.info(
        "Klaar: %d bevindingen — NC: %d, OFI: %d, positief: %d",
        len(alle),
        nc,
        ofi,
        pos,
    )
    return alle


GELDIGE_OORDELEN = frozenset({"NC", "OFI", "positief"})
"""De enige drie waarden die als oordeel tellen.

Wat er nog meer binnenkomt is geen oordeel: het model schrijft "hier valt niets over te zeggen"
soms als de **string** `"null"` in plaats van JSON-`null` (twee keer gemeten op 2026-08-24), en
een variant als "gedeeltelijk" levert een bevinding op die geen UI-filter kent en die in de memo
tussen wal en schip valt."""

_GEEN_OORDEEL = frozenset({"null", "none", "geen", "nvt", "n.v.t."})


def _geldig_oordeel(waarde: Any) -> str | None:
    """Normaliseer een classificatie; `None` betekent: geen oordeel, geen bevinding."""
    if not isinstance(waarde, str):
        return None
    schoon = waarde.strip()
    if not schoon or schoon.lower() in _GEEN_OORDEEL:
        return None
    for geldig in GELDIGE_OORDELEN:
        if schoon.lower() == geldig.lower():
            return geldig
    logger.warning("Onbekende classificatie %r genegeerd; geen bevinding aangemaakt", schoon)
    return None


def bouw_bevindingen(
    *,
    doc: dict[str, Any],
    clausules: list[str],
    resultaten: list[dict[str, Any]],
    clausule_titels: dict[str, Any],
) -> list[dict[str, Any]]:
    """Zet modelantwoorden om in bevindingen — zonder oordeel geen bevinding.

    De vorige versie deed `.get("classificatie", "OFI")`, en daarmee werd elk ontbrekend
    antwoord een OFI met een lege beschrijving en lege onderbouwing. Twee gevallen vielen
    daaronder: het model zweeg over een clausule, of het zei expliciet `null` — de uitweg die
    de prompts sinds 2026-08-24 aanbieden voor "dit document gaat hier niet over".

    In de run van 2026-08-24 waren dat er 55: een oordeel zonder inhoud dat wél meetelde in het
    rapport. En het is de mechaniek achter 6,8 bevindingen per document: elk paar dat de
    zoektermen opleverden moest een oordeel worden, ook als er niets over te zeggen viel.

    Een NC zonder onderbouwing wordt niet weggegooid maar gemarkeerd als `onbruikbaar`. Dát het
    model een NC zonder onderbouwing teruggaf, is zelf een gegeven over de classificatie — en de
    norm vraagt bij een NC om correctie, root-cause-analyse en formele verificatie, wat op een
    leeg oordeel niet kan.
    """
    per_clausule = {r.get("clausule"): r for r in resultaten if isinstance(r, dict)}
    # De norm per clausule komt uit de koppeling: `clause_matches` weet uit welke norm een
    # match komt, en zonder deze regel kreeg een bevinding de run-parameter (`beide`) mee.
    # Achttien nummers bestaan in beide normen; dan zijn het twee bevindingen, want §7.5 is in
    # 9001 "Gedocumenteerde informatie" en in 27001 iets heel anders.
    normen_per_clausule: dict[str, list[str]] = {}
    for cid, match_norm in doc.get("clausule_normen") or []:
        normen_per_clausule.setdefault(str(cid), []).append(str(match_norm))

    bevindingen: list[dict[str, Any]] = []
    for cid in clausules:
        res = per_clausule.get(cid) or {}
        classificatie = _geldig_oordeel(res.get("classificatie"))
        if classificatie is None:
            continue  # geen oordeel is geen bevinding
        for match_norm in normen_per_clausule.get(cid) or [""]:
            bevindingen.append(
                _bevinding(doc, cid, match_norm, res, classificatie, clausule_titels)
            )
    return bevindingen


def _bevinding(
    doc: dict[str, Any],
    cid: str,
    match_norm: str,
    res: dict[str, Any],
    classificatie: str,
    clausule_titels: dict[str, Any],
) -> dict[str, Any]:
    """Eén bevindingsrij; `match_norm` leeg betekent: de aanroeper beslist, zoals voorheen."""
    beschrijving = res.get("beschrijving") or ""
    onderbouwing = res.get("onderbouwing") or ""
    return {
        "_doc_id": doc["id"],
        # Bron van de bevinding (Drive/Jira/Planning/…) — terugvoerbaar.
        "herkomst": doc.get("herkomst") or "Drive",
        "clausule": cid,
        "clausule_titel": clausule_titels.get(cid, {}).get("titel", cid),
        "document_naam": doc["naam"],
        "classificatie": classificatie,
        "ernst": res.get("ernst"),
        "beschrijving": beschrijving,
        "onderbouwing": onderbouwing,
        "onbruikbaar": not beschrijving.strip() and not onderbouwing.strip(),
        "norm": match_norm,
        "pre_classificatie": None,
    }


def _classify_drive(ctx: _ClassifyContext, docs: list[dict[str, Any]]) -> None:
    clausules_per_doc: dict[str, list[str]] = defaultdict(list)
    doc_map: dict[str, dict[str, Any]] = {}
    for doc in docs:
        doc_map[doc["id"]] = doc
        for cid in doc.get("clausules", []):
            clausules_per_doc[doc["id"]].append(cid)

    todo_pairs: list[tuple[str, list[str]]] = []
    for doc_id, cids in clausules_per_doc.items():
        if ctx.rehash:
            todo_pairs.append((doc_id, cids))
            continue
        missend = [c for c in cids if c not in ctx.gedaan.get(doc_id, set())]
        if missend:
            todo_pairs.append((doc_id, missend))

    logger.info(
        "Drive: %d/%d docs te classificeren (rehash=%s)",
        len(todo_pairs),
        len(clausules_per_doc),
        ctx.rehash,
    )

    for i, (doc_id, cids) in enumerate(todo_pairs, 1):
        doc = doc_map[doc_id]
        logger.info("[%d/%d] %s (%d clausules)", i, len(todo_pairs), doc["naam"][:50], len(cids))
        resultaten = _classificeer_doc(
            doc,
            cids,
            ctx.clausules,
            ctx.client,
            ctx.teller,
            scherpte=ctx.scherpte,
            conn=ctx.conn,
            audit_id=ctx.audit_id,
        )
        bevs = bouw_bevindingen(
            doc={"id": doc_id, "naam": doc["naam"], "herkomst": doc.get("herkomst") or "Drive"},
            clausules=cids,
            resultaten=resultaten,
            clausule_titels=ctx.clausules,
        )
        _upsert_bevindingen(ctx.conn, bevs, ctx.norm)


def _classify_miro(ctx: _ClassifyContext, miro_notities: list[dict[str, Any]]) -> None:
    todo_miro = [
        n
        for n in miro_notities
        if ctx.rehash or n.get("miro_item_id", n.get("id")) not in ctx.gedaan_miro_ids
    ]
    logger.info("Miro: %d/%d notities te classificeren", len(todo_miro), len(miro_notities))

    for i in range(0, len(todo_miro), MIRO_BATCH):
        batch = todo_miro[i : i + MIRO_BATCH]
        logger.info("Miro batch %d (%d items)", i // MIRO_BATCH + 1, len(batch))
        resultaten = _classificeer_miro_batch(
            batch,
            ctx.clausules,
            ctx.client,
            ctx.teller,
            conn=ctx.conn,
            audit_id=ctx.audit_id,
        )
        res_map = {r["id"]: r for r in resultaten}
        bevs: list[dict[str, Any]] = []
        skip_teller = 0
        mistag_teller = 0
        for notitie in batch:
            nid = notitie.get("miro_item_id", notitie.get("id", ""))
            cid = notitie.get("clausule", "")
            if not cid:
                skip_teller += 1
                continue
            res = res_map.get(nid, {})
            if _is_miro_mistag(res.get("beschrijving", "")):
                mistag_teller += 1
                ctx.conn.execute(
                    "DELETE FROM bevindingen WHERE doc_id=? AND herkomst='Miro' "
                    "AND clausule_id=? AND norm=?",
                    (nid, cid, ctx.norm),
                )
                continue
            bevs.append(
                {
                    "_doc_id": nid,
                    "herkomst": "Miro",
                    "clausule": cid,
                    "clausule_titel": ctx.clausules.get(cid, {}).get("titel", cid),
                    "document_naam": f"Miro: {notitie.get('tekst', '')[:60]}...",
                    "classificatie": res.get("classificatie", "OFI"),
                    "beschrijving": res.get("beschrijving", ""),
                    "onderbouwing": res.get("onderbouwing", ""),
                    "pre_classificatie": notitie.get("pre_classificatie"),
                }
            )
        if skip_teller or mistag_teller:
            logger.warning(
                "Miro batch %d: %d zonder clausule + %d mis-tagged overgeslagen",
                i // MIRO_BATCH + 1,
                skip_teller,
                mistag_teller,
            )
        _upsert_bevindingen(ctx.conn, bevs, ctx.norm)


# ---------------------------------------------------------------------------
# Review (handmatige bevestiging — uit v1)
# ---------------------------------------------------------------------------


def review_en_bevestig(
    bevindingen: list[dict[str, Any]], auto_accept: bool = False
) -> list[dict[str, Any]]:
    """Interactieve review-loop; bij `auto_accept=True` wordt alles geaccepteerd."""
    volgorde = {"NC": 0, "OFI": 1, "positief": 2}
    gesorteerd = sorted(bevindingen, key=lambda b: volgorde.get(b["classificatie"], 9))

    nc = sum(1 for b in bevindingen if b["classificatie"] == "NC")
    ofi = sum(1 for b in bevindingen if b["classificatie"] == "OFI")
    pos = sum(1 for b in bevindingen if b["classificatie"] == "positief")

    if auto_accept:
        logger.info(
            "Auto-accept: %d bevindingen (NC: %d, OFI: %d, positief: %d)",
            len(bevindingen),
            nc,
            ofi,
            pos,
        )
        return list(bevindingen)

    print("\n" + "=" * 70)
    print("REVIEW BEVINDINGEN")
    print("=" * 70)
    print(f"Totaal: {len(bevindingen)} | NC: {nc} | OFI: {ofi} | Positief: {pos}\n")

    gecorrigeerd: list[dict[str, Any]] = []
    for i, bev in enumerate(gesorteerd, 1):
        print(f"[{i}/{len(gesorteerd)}] {bev['clausule']}: {bev['clausule_titel']}")
        print(f"  {bev['herkomst']} — {bev['document_naam'][:60]}")
        print(f"  {bev['classificatie']} — {bev['beschrijving'][:100]}")
        invoer = input("  [Enter=ok | nc/ofi/p=corrigeer | s=sla over]: ").strip().lower()
        if invoer == "nc":
            bev = {**bev, "classificatie": "NC"}
        elif invoer == "ofi":
            bev = {**bev, "classificatie": "OFI"}
        elif invoer in ("p", "pos", "positief"):
            bev = {**bev, "classificatie": "positief"}
        elif invoer == "s":
            continue
        gecorrigeerd.append(bev)

    print(f"\nReview klaar: {len(gecorrigeerd)} bevindingen.\n")
    return gecorrigeerd


# ---------------------------------------------------------------------------
# CLI — dry-run-cost zonder API-calls + volledige run
# ---------------------------------------------------------------------------


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="finding-classifier (v2) — kostenschatting + rehash"
    )
    parser.add_argument("--norm", choices=["9001", "27001", "beide"], default="27001")
    parser.add_argument("--chapter", default=None, help="Beperk tot hoofdstuk (bv. 7)")
    parser.add_argument("--scherpte", type=float, default=1.0)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--rehash", action="store_true", help="Ignoreer checkpoint, overschrijf bestaand"
    )
    parser.add_argument(
        "--dry-run-cost",
        action="store_true",
        help="Toon alleen kostenschatting, géén API-calls",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # NB: Drive-ingest leeft pas in §2.3.2 als `iso_audit.sources.drive`.
    # Tot dan kan de CLI alleen Miro classificeren. We checken runtime-
    # beschikbaarheid via importlib (geen statisch import zodat mypy --strict
    # niet faalt op de nog niet bestaande module).
    import importlib

    from iso_audit.classification.clause_mapping import (
        filter_clause_map,
        koppel_documenten,
        laad_clause_map,
    )
    from iso_audit.miro.ingest import haal_notities_op, koppel_aan_clausules

    drive_loader = None
    try:
        _drive_mod = importlib.import_module("iso_audit.sources.drive")
        drive_loader = _drive_mod.haal_documenten_op
    except ImportError:
        logger.warning("Drive-ingest niet beschikbaar (§2.3.2 pending); Drive-docs overgeslagen")

    clause_map = laad_clause_map(args.norm)
    if args.chapter:
        clause_map = filter_clause_map(clause_map, args.chapter)

    gekoppeld: list[dict[str, Any]] = []
    if drive_loader:
        documenten, _ = drive_loader()
        gekoppeld, _ = koppel_documenten(documenten, clause_map)

    miro_notities: list[dict[str, Any]] = []
    try:
        miro_raw = haal_notities_op()
        miro_notities = koppel_aan_clausules(miro_raw, clause_map)
    except Exception as e:
        logger.warning("Miro overgeslagen: %s", e)

    if args.dry_run_cost:
        schatting = schat_kosten(
            gekoppeld,
            miro_notities,
            clause_map,
            norm=args.norm,
            scherpte=args.scherpte,
            model=args.model,
            rehash=args.rehash,
        )
        print("\n=== Kostenschatting (geen API-calls) ===")
        for k, v in schatting.items():
            print(f"  {k}: {v}")
        return 0

    bevindingen = classificeer_alle_bevindingen(
        gekoppeld,
        miro_notities,
        clause_map,
        norm=args.norm,
        scherpte=args.scherpte,
        rehash=args.rehash,
        model=args.model,
    )
    print(f"\n{len(bevindingen)} bevindingen in DB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
