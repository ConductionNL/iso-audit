"""Clausule-mapping — koppelt documenten en notities aan norm-clausules.

Laadt `clause_map_<norm>.yaml` (uit `iso_audit.data.clause_maps`) en matcht
documenten op zoektermen. Rapporteert ontbrekende clausule-dekking.

Gemigreerd uit `Ops_to_Biz/audit/clause_mapping.py` per milestone B §2.2.4.
Schema en regex-matching ongewijzigd; alleen padresolutie en type-hints
aangepast.
"""

from __future__ import annotations

import logging
import re
from importlib import resources
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def filter_clause_map(clause_map: dict[str, Any], chapter: str) -> dict[str, Any]:
    """Beperk `clause_map` tot clausules die beginnen met het opgegeven hoofdstuk-prefix.

    Voorbeelden::

        filter_clause_map(m, "4")   → alleen 4.1, 4.2, ...
        filter_clause_map(m, "8")   → alleen 8.x (9001 én 27001)
        filter_clause_map(m, "5.1") → alleen 5.1x sub-clausules
    """
    prefix = chapter.rstrip(".") + "."
    gefilterd = {
        k: v
        for k, v in clause_map.get("clausules", {}).items()
        if k.startswith(prefix) or k == chapter
    }
    if not gefilterd:
        beschikbaar = sorted({k.split(".")[0] for k in clause_map.get("clausules", {})})
        raise ValueError(
            f"Geen clausules gevonden voor hoofdstuk {chapter!r}. "
            f"Beschikbare hoofdstukken: {', '.join(beschikbaar)}"
        )
    result = dict(clause_map)
    result["clausules"] = gefilterd
    logger.info(
        "Hoofdstuk-filter '%s': %d clausules geselecteerd",
        chapter,
        len(gefilterd),
    )
    return result


def laad_clause_map(norm: str) -> dict[str, Any]:
    """Laad de clause-map voor de gegeven norm (`'9001'`, `'27001'` of `'beide'`)."""
    if norm == "beide":
        map_9001 = _laad_bestand("clause_map_9001.yaml")
        map_27001 = _laad_bestand("clause_map_27001.yaml")
        samengevoegd = dict(map_9001)
        samengevoegd["clausules"] = {
            **map_9001.get("clausules", {}),
            **map_27001.get("clausules", {}),
        }
        samengevoegd["norm"] = "ISO 9001:2015 + ISO 27001:2022"
        return samengevoegd
    if norm not in ("9001", "27001"):
        raise ValueError(f"onbekende norm {norm!r} (verwacht '9001', '27001' of 'beide')")
    return _laad_bestand(f"clause_map_{norm}.yaml")


def _laad_bestand(bestandsnaam: str) -> dict[str, Any]:
    """Laad een YAML-bestand uit `iso_audit.data.clause_maps` via importlib.resources."""
    res = resources.files("iso_audit.data.clause_maps") / bestandsnaam
    if not res.is_file():
        raise FileNotFoundError(f"Clause-map niet gevonden: {bestandsnaam}")
    with res.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return data


def koppel_documenten(
    documenten: list[dict[str, Any]], clause_map: dict[str, Any], norm: str = ""
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Koppel elk document aan één of meer clausules én sub-punten via zoektermen.

    Retourneert `(gekoppeld, niet_geclassificeerd)`.
    - `gekoppeld` — documenten met de velden `clausule_normen` (lijst tuples
      `(clausule_id, norm)`), `clausules` (de clausule-IDs daaruit) en `sub_punt_matches`
      (lijst tuples `(clausule_id, sub_punt_id)`).
    - `niet_geclassificeerd` — documenten zonder enige clausule-match.

    **`norm` hoort bij de koppeling en niet bij het clausulenummer.** Achttien nummers bestaan
    in beide normen en betekenen daar iets anders: 9001 §7.5 is "Gedocumenteerde informatie",
    27001 §7.5 is "Beveiligd ontwikkelen". Zolang een match alleen een nummer droeg, moest
    `run_job._resolve_standard()` achteraf raden bij welke norm hij hoorde — en dat raadde er
    op 2026-08-24 448 van de 903 verkeerd.

    Aanroepen met de map van één norm, niet met een samenvoeging: `laad_clause_map("beide")`
    laat 27001 de 9001-ingang overschrijven, waardoor 18 van de 28 ISO 9001-clausules in een
    gecombineerde audit nooit getoetst werden.

    `clausules` wordt uit `clausule_normen` afgeleid en niet apart bijgehouden — twee lijsten
    die hetzelfde beweren lopen uiteen zodra iemand er één vergeet.
    """
    clausules: dict[str, Any] = clause_map.get("clausules", {})
    gekoppeld: list[dict[str, Any]] = []
    niet_geclassificeerd: list[dict[str, Any]] = []

    for doc in documenten:
        tekst_lower = doc.get("tekst", "").lower()
        naam_lower = doc.get("naam", "").lower()
        gecombineerd = tekst_lower + " " + naam_lower

        gevonden_clausules: list[str] = []
        sub_punt_matches: list[tuple[str, str]] = []

        for clausule_id, data in clausules.items():
            zoektermen = data.get("zoektermen", [])
            clausule_match = any(
                re.search(r"\b" + re.escape(term.lower()) + r"\b", gecombineerd)
                for term in zoektermen
            )
            if clausule_match:
                gevonden_clausules.append(clausule_id)

            for sp in data.get("sub_punten", []):
                sp_termen = sp.get("zoektermen", [])
                if any(
                    re.search(r"\b" + re.escape(term.lower()) + r"\b", gecombineerd)
                    for term in sp_termen
                ):
                    sub_punt_matches.append((clausule_id, sp["id"]))
                    if clausule_id not in gevonden_clausules:
                        gevonden_clausules.append(clausule_id)

        doc_met_koppeling: dict[str, Any] = {
            **doc,
            "clausule_normen": [(cid, norm) for cid in gevonden_clausules],
            "clausules": gevonden_clausules,
            "sub_punt_matches": sub_punt_matches,
        }

        if gevonden_clausules:
            gekoppeld.append(doc_met_koppeling)
            logger.debug(
                "Document '%s' → clausules: %s, sub-punten: %s",
                doc.get("naam", "?"),
                gevonden_clausules,
                sub_punt_matches,
            )
        else:
            niet_geclassificeerd.append(doc_met_koppeling)
            logger.info("Geen clausule-match voor: %s", doc.get("naam", "?"))

    return gekoppeld, niet_geclassificeerd


def normen_van(norm: str) -> tuple[str, ...]:
    """De losse normen achter een norm-parameter: `"beide"` → `("9001", "27001")`."""
    return ("9001", "27001") if norm == "beide" else (norm,)


def koppel_alle_normen(
    documenten: list[dict[str, Any]],
    norm: str,
    clause_map_per_norm: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Koppel per norm en voeg de resultaten per document samen.

    Vervangt de aanroep `koppel_documenten(docs, laad_clause_map("beide"))`. Die samenvoeging
    is `{**map_9001, **map_27001}`, en achttien clausulenummers bestaan in beide normen — daar
    won 27001, waardoor 18 van de 28 ISO 9001-clausules in een gecombineerde audit nooit
    getoetst werden (§5.1 Leiderschap, §6.1 Risico's en kansen, §7.5 Gedocumenteerde
    informatie, §8.4 Externe processen …). De samengevoegde map had 103 ingangen waar er 121
    horen.

    Per norm koppelen betekent dat een document twee koppelingen op hetzelfde nummer kan
    krijgen, elk met zijn eigen norm. Het document zelf komt één keer terug.

    `clause_map_per_norm` is er voor het hoofdstuk-filter en voor tests; standaard wordt de
    map van elke norm zelf geladen.
    """
    maps = clause_map_per_norm or {n: laad_clause_map(n) for n in normen_van(norm)}
    per_doc: dict[str, dict[str, Any]] = {}
    volgorde: list[str] = []

    for deelnorm, clause_map in maps.items():
        gekoppeld, _ = koppel_documenten(documenten, clause_map, norm=deelnorm)
        for doc in gekoppeld:
            doc_id = str(doc["id"])
            if doc_id not in per_doc:
                per_doc[doc_id] = {**doc, "clausule_normen": [], "sub_punt_matches": []}
                volgorde.append(doc_id)
            samen = per_doc[doc_id]
            samen["clausule_normen"] = [*samen["clausule_normen"], *doc["clausule_normen"]]
            samen["sub_punt_matches"] = [*samen["sub_punt_matches"], *doc["sub_punt_matches"]]

    for samen in per_doc.values():
        # Afgeleid en niet apart bijgehouden: twee lijsten die hetzelfde beweren lopen uiteen.
        # Ontdubbeld met behoud van volgorde — hetzelfde nummer uit twee normen is één
        # clausule-id voor de aanroepers die alleen het nummer gebruiken.
        gezien: set[str] = set()
        ids: list[str] = []
        for cid, _ in samen["clausule_normen"]:
            if cid not in gezien:
                gezien.add(cid)
                ids.append(cid)
        samen["clausules"] = ids

    gekoppeld_samen = [per_doc[doc_id] for doc_id in volgorde]
    niet = [d for d in documenten if str(d["id"]) not in per_doc]
    return gekoppeld_samen, niet


def ontbrekende_dekking(
    gekoppelde_docs: list[dict[str, Any]],
    miro_notities: list[dict[str, Any]],
    clause_map: dict[str, Any],
) -> list[dict[str, Any]]:
    """Bepaal welke clausules geen enkel document of notitie hebben.

    Retourneert lijst van dicts met `clausule`, `titel` en `reden` voor het
    validatierapport.
    """
    clausules: dict[str, Any] = clause_map.get("clausules", {})

    gedekte_ids: set[str] = set()
    for doc in gekoppelde_docs:
        gedekte_ids.update(doc.get("clausules", []))
    for notitie in miro_notities:
        if notitie.get("clausule"):
            gedekte_ids.add(notitie["clausule"])

    ontbrekend: list[dict[str, Any]] = []
    for clausule_id, data in clausules.items():
        if clausule_id not in gedekte_ids:
            ontbrekend.append(
                {
                    "clausule": clausule_id,
                    "titel": data.get("titel", ""),
                    "reden": "Geen gedocumenteerd bewijs gevonden",
                }
            )
            logger.warning(
                "Ontbrekende dekking voor clausule %s: %s",
                clausule_id,
                data.get("titel", ""),
            )

    logger.info(
        "Clausule-dekking: %d gedekt, %d ontbrekend",
        len(clausules) - len(ontbrekend),
        len(ontbrekend),
    )
    return ontbrekend
