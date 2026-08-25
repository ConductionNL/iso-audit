"""Thema-toekenning voor audit-bevindingen — hybride (keywords + LLM).

Twee routes:

1. **Route A — `bepaal_thema()`**: heuristische keyword-match over
   beschrijving + onderbouwing + document_naam. First-match-wins. Geen
   externe afhankelijkheden. Bron-of-truth voor de taxonomie (`THEMA_LIJST`).
2. **Route B — `classificeer_themas()`**: LLM-batch-classificatie via
   Anthropic API. Bedoeld voor verfijning van bevindingen waar route A
   `"Overig"` teruggeeft.

`verfijn_overig()` combineert beide routes: heuristiek eerst, LLM alleen
voor de rest.

Gemigreerd uit `Ops_to_Biz/audit/thema_classifier.py` + de gedeelde
`THEMA_LIJST`/`THEMA_REGELS`/`bepaal_thema()` uit `audit/tabular_report.py`
per milestone B §2.2.6. Deze module is nu de bron-of-truth — de
tabular_report-migratie in §2.5 zal hieruit importeren.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic
from dotenv import load_dotenv

from iso_audit import modellen
from iso_audit.classification.respons import tekst_uit

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = modellen.STANDAARD
"""Thema-bepaling leunt op al-geclassificeerde bevindingen en velt zelf geen oordeel over
bewijs; vandaar het standaardmodel en niet de auditor-keuze."""
BATCH_GROOTTE = 50
MAX_BESCHRIJVING_CHARS = 500
MAX_ONDERBOUWING_CHARS = 250

# Vaste taxonomie — bron-of-truth voor het hele audit-systeem.
# `"Overig"` is de fallback-categorie en moet als laatste staan.
THEMA_LIJST: list[str] = [
    "Offboarding & activa-retournering",
    "Informatieclassificatie",
    "Cryptografie & encryptie",
    "Back-up & continuïteit",
    "Screening & HR",
    "Fysieke beveiliging",
    "Leveranciersbeheer",
    "Memo & afwijkingsregistratie",
    "Template zonder toepassing",
    "Verificatie van doeltreffendheid",
    "Klanttevredenheid",
    "Documentatie-actualiteit",
    "Rollen & verantwoordelijkheden",
    "Beleid",
    "Risicomanagement",
    "Auditprogramma",
    "Directiebeoordeling",
    "Training & competenties",
    "Toegangsbeheer",
    "Logging & monitoring",
    "Incident response",
    "Ontwikkeling & wijzigingsbeheer",
    "Wettelijke & contractuele eisen",
    "Privacy & persoonsgegevens",
    "Context-analyse & belanghebbenden",
    "Overig",
]

# Keyword-gedreven thema-regels (route A). First-match-wins — specifieker eerst.
# Geen match → `"Overig"`.
THEMA_REGELS: list[tuple[str, list[str]]] = [
    (
        "Offboarding & activa-retournering",
        ["retournering", "offboarding", "beëindiging dienst", "teruggave activa"],
    ),
    (
        "Informatieclassificatie",
        ["informatieclassificatie", "classificatie van informatie", "label"],
    ),
    ("Cryptografie & encryptie", ["cryptograf", "encryptie", "versleuteling"]),
    ("Back-up & continuïteit", ["back-up", "backup", "continuïteit", "disaster recovery", "bcm"]),
    ("Screening & HR", ["screening", "achtergrondcontrole", "arbeidsvoorwaarden"]),
    ("Fysieke beveiliging", ["perimeter", "fysieke beveilig", "kantoorbeveilig"]),
    ("Leveranciersbeheer", ["leverancier", "supplier", "derde partij", "uitbesteding"]),
    (
        # §8.9 configuratiebeheer, §8.25 veilige ontwikkeling en §8.33 testinformatie horen bij
        # elkaar en nergens anders; zonder dit thema vielen ze los in `Overig` (run 2026-08-26).
        # Vóór "Template zonder toepassing" omdat die op het generieke woord `template` matcht.
        "Ontwikkeling & wijzigingsbeheer",
        [
            "configuratiebeheer",
            "wijzigingsbeheer",
            "veilige ontwikkeling",
            "ontwikkelingspijplijn",
            "ontwikkelstraat",
            "ontwikkelomgeving",
            "testinformatie",
            "testgegevens",
            "productiegegevens",
            "broncode",
            "ci/cd",
        ],
    ),
    (
        "Memo & afwijkingsregistratie",
        ["memo afwijk", "memo nc", "afwijkingsprocedure", "afwijkingsmemo", "nc-memo"],
    ),
    (
        "Template zonder toepassing",
        ["template", "ongevuld", "niet ingevuld", "geen concrete", "lege procedure"],
    ),
    (
        "Verificatie van doeltreffendheid",
        ["verificatie", "effectiviteit", "doeltreffendheid", "follow-up"],
    ),
    ("Klanttevredenheid", ["klanttevredenheid", "nps ", "klantbeoordeling", "klantreview"]),
    (
        "Documentatie-actualiteit",
        [
            "verouderd",
            "niet meer actueel",
            "ouder dan 2 jaar",
            "> 2 jaar",
            "niet geactualiseerd",
            "reeds geactualiseerd",
            "herziening nodig",
        ],
    ),
    ("Rollen & verantwoordelijkheden", ["rollen", "verantwoordelijkheden", "bevoegdheden"]),
    (
        "Beleid",
        [
            "kwaliteitsbeleid",
            "informatiebeveiligingsbeleid",
            "beleidsdocument",
            "beleidsverklaring",
        ],
    ),
    ("Risicomanagement", ["risicobeoordeling", "risicoanalyse", "risicoregister"]),
    (
        "Wettelijke & contractuele eisen",
        [
            "wet en regelgeving",
            "wettelijke eis",
            "contractuele eis",
            "compliance",
            "regelgeving",
            "iso-704",
        ],
    ),
    ("Privacy & persoonsgegevens", ["privacy", "avg", "gdpr", "persoonsgegevens", "pii"]),
    (
        "Context-analyse & belanghebbenden",
        [
            "contextanalyse",
            "context analyse",
            "belanghebbenden",
            "stakeholder",
            "swot",
            "interne en externe context",
        ],
    ),
    ("Auditprogramma", ["interne audit", "auditprogramma", "auditplan"]),
    ("Directiebeoordeling", ["directiebeoordeling", "management review"]),
    ("Training & competenties", ["training", "competenties", "opleiding"]),
    (
        "Toegangsbeheer",
        [
            "toegangsbeheer",
            "toegangsrechten",
            "autorisatie",
            "authenticatie",
            "mfa",
            "multi-factor",
            "wachtwoord",
            "inloggegevens",
        ],
    ),
    ("Logging & monitoring", ["logging", "monitoring", "audit-trail", "audit trail"]),
    ("Incident response", ["incident response", "incidentmanagement", "incidentprocedure"]),
]

SYSTEM_PROMPT = (
    "Je bent een ISO 9001:2015 + ISO 27001:2022 auditor bij Conduction, een "
    "Nederlands softwarebedrijf (open-source, publieke sector).\n\n"
    "Jouw taak: wijs elke aangeboden audit-bevinding toe aan precies één thema "
    "uit de onderstaande vaste taxonomie. Kies het thema dat het KERNPROBLEEM "
    "van de bevinding beschrijft, niet een bijkomstig detail.\n\n"
    "Taxonomie (kies één):\n" + "\n".join(f"- {t}" for t in THEMA_LIJST) + "\n\nRegels:\n"
    "- Gebruik exact de thema-naam zoals hierboven geschreven.\n"
    "- Gebruik 'Overig' uitsluitend als geen ander thema passend is.\n"
    "- Baseer je keuze op de bevindingsbeschrijving + onderbouwing.\n"
    "- Retourneer uitsluitend geldig JSON:\n"
    '  {"toewijzingen": [{"id": "<id>", "thema": "<thema>"}]}\n'
    "Geen uitleg buiten de JSON."
)


def bepaal_thema(bevinding: dict[str, Any]) -> str:
    """Route A: keyword-match over beschrijving + onderbouwing + documentnaam + clausuletitel.

    First-match-wins. Lege/missende velden tellen niet mee. Geen externe
    afhankelijkheden — pure functie.

    `clausule_titel` is optioneel en kwam er later bij: §5.29 heet "Informatiebeveiliging en
    continuïteit tijdens verstoring" en viel toch in `Overig`, omdat de duidelijkste samenvatting
    van de bevinding niet werd gelezen. Aanroepers die het veld niet meegeven, werken ongewijzigd.

    Het is nadrukkelijk een **terugval** en geen gelijkwaardige input. Bij de eerste poging
    (2026-08-26) telde de titel gewoon mee, en verschoven 8 NC's die al onder "Memo &
    afwijkingsregistratie" hoorden naar "Rollen & verantwoordelijkheden" — de generieke normtaal
    van een clausuletitel matcht nu eenmaal eerder dan de specifieke bevindingstekst. Dus eerst
    de eigen tekst van de bevinding; alleen als die niets oplevert, de titel erbij.
    """
    eigen = " ".join(
        [
            bevinding.get("beschrijving") or "",
            bevinding.get("onderbouwing") or "",
            bevinding.get("document_naam") or "",
        ]
    )
    thema = _match(eigen)
    if thema != "Overig":
        return thema
    return _match(f"{eigen} {bevinding.get('clausule_titel') or ''}")


def _match(tekst: str) -> str:
    """First-match-wins over `THEMA_REGELS`. Lege tekst → `Overig`."""
    laag = tekst.lower()
    if not laag.strip():
        return "Overig"
    for thema, keywords in THEMA_REGELS:
        for kw in keywords:
            if kw.lower() in laag:
                return thema
    return "Overig"


def _bouw_batch_input(batch: list[dict[str, Any]]) -> str:
    regels: list[str] = []
    for b in batch:
        bid = str(b["_bev_id"])
        cl = b.get("clausule") or b.get("clausule_id", "")
        cls = b.get("classificatie", "")
        besc = (b.get("beschrijving") or "")[:MAX_BESCHRIJVING_CHARS]
        ond = (b.get("onderbouwing") or "")[:MAX_ONDERBOUWING_CHARS]
        regels.append(
            f"ID: {bid}\nCLAUSULE: {cl} ({cls})\nBESCHRIJVING: {besc}\nONDERBOUWING: {ond}"
        )
    return "\n\n---\n\n".join(regels)


def _verwerk_batch(client: anthropic.Anthropic, batch: list[dict[str, Any]]) -> dict[str, str]:
    invoer = _bouw_batch_input(batch)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": invoer}],
    )
    tekst: str = tekst_uit(resp)
    start = tekst.find("{")
    eind = tekst.rfind("}") + 1
    if start == -1 or eind <= start:
        logger.warning("Geen JSON in respons — batch overgeslagen")
        return {}
    try:
        data = json.loads(tekst[start:eind])
        return {
            str(t["id"]): t["thema"]
            for t in data.get("toewijzingen", [])
            if "id" in t and "thema" in t
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("JSON parse fout: %s", e)
        return {}


def _valideer(toewijzingen: dict[str, str]) -> dict[str, str]:
    """Vervang thema's die niet in de taxonomie staan door 'Overig'."""
    geldig = set(THEMA_LIJST)
    resultaat: dict[str, str] = {}
    onbekend = 0
    for bid, thema in toewijzingen.items():
        if thema in geldig:
            resultaat[bid] = thema
        else:
            resultaat[bid] = "Overig"
            onbekend += 1
    if onbekend:
        logger.warning("%d toewijzingen met onbekend thema — vervangen door 'Overig'", onbekend)
    return resultaat


def classificeer_themas(bevindingen: list[dict[str, Any]]) -> dict[str, str]:
    """Route B: wijs thema's toe aan alle bevindingen via batch LLM-calls.

    `bevindingen` krijgt een interne `_bev_id`-key gezet (afgeleid van
    bestaande `id` of de index). Output: `{bev_id: thema}`. Lege dict bij
    volledige fout — de heuristiek behoudt dan zijn waarde.
    """
    if not bevindingen:
        return {}
    try:
        client = anthropic.Anthropic()
    except Exception as e:
        logger.warning("Anthropic client init mislukt: %s — LLM-thema overgeslagen", e)
        return {}

    for i, b in enumerate(bevindingen):
        b["_bev_id"] = str(b.get("id") or b.get("_bev_id") or i)

    aantal_batches = (len(bevindingen) + BATCH_GROOTTE - 1) // BATCH_GROOTTE
    logger.info(
        "LLM thema-toekenning: %d bevindingen in %d batch(es) (model=%s)",
        len(bevindingen),
        aantal_batches,
        MODEL,
    )

    resultaat: dict[str, str] = {}
    for i in range(0, len(bevindingen), BATCH_GROOTTE):
        batch = bevindingen[i : i + BATCH_GROOTTE]
        batch_num = i // BATCH_GROOTTE + 1
        try:
            resultaat.update(_verwerk_batch(client, batch))
            logger.info(
                "Batch %d/%d klaar (%d cumulatief)",
                batch_num,
                aantal_batches,
                len(resultaat),
            )
        except Exception as e:
            logger.warning("Batch %d mislukt: %s", batch_num, e)

    resultaat = _valideer(resultaat)
    logger.info(
        "LLM thema-toekenning klaar: %d/%d toegewezen",
        len(resultaat),
        len(bevindingen),
    )
    return resultaat


def verfijn_overig(bevindingen: list[dict[str, Any]]) -> dict[str, str]:
    """Hybride: alleen heuristisch-`Overig`-bevindingen via LLM verfijnen.

    Kosten- en tijds-efficiënt: route A handelt het overgrote deel af;
    route B (LLM) zit alleen op de rest.
    """
    overig = [b for b in bevindingen if bepaal_thema(b) == "Overig"]
    if not overig:
        logger.info("Geen 'Overig'-bevindingen om via LLM te verfijnen")
        return {}
    logger.info(
        "Verfijn %d/%d 'Overig'-bevindingen via LLM",
        len(overig),
        len(bevindingen),
    )
    return classificeer_themas(overig)
