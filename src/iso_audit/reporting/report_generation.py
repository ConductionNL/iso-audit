"""Rapportgeneratie — Google Docs template kopiëren en placeholders vullen.

Genereert het volledige auditrapport op basis van bevestigde bevindingen.
Alleen uitgevoerd als `AUDIT_TEMPLATE_DOC_ID` geconfigureerd is.

Gemigreerd uit `Ops_to_Biz/audit/report_generation.py` per milestone B §2.5.1.
`gws_client._gws` → `iso_audit.clients.gws._gws`; type-hints aangevuld.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import anthropic

from iso_audit import modellen
from iso_audit.clients.gws import _gws

logger = logging.getLogger(__name__)

VOLGORDE: dict[str, int] = {"NC": 0, "OFI": 1, "positief": 2}
CLAUDE_MODEL = modellen.STANDAARD
"""Rapporttekst, geen classificatie — dus het standaardmodel."""

# Near-idempotentie: lage temperatuur → stabiele, reproduceerbare output bij
# herdraaien (bv. via --report-only). Zie memory "architectuur-harness-fundament".
CLAUDE_TEMPERATUUR = 0.0

# Redactionele LLM-regels staan versiegestuurd in prompts/<naam>_v<n>.md,
# niet hardcoded in code. Zie memory "prompts-versiegestuurd-niet-hardcoded".
_PROMPT_DIR = Path(__file__).parent / "prompts"

# Deterministische gate: deze NC-woorden mogen niet in de aanbevelingen-sectie.
# De LLM-prompt vraagt het; _check_verboden_woorden bevestigt het op de output.
_VERBODEN_WOORDEN: tuple[str, ...] = (
    "onvoldoende",
    "ontoereikend",
    "risico",
    "lacune",
    "gebrek",
    "ontbreekt",
)


def _laad_prompt(naam: str, vervangingen: dict[str, str]) -> str:
    """Laad een versie-prompt uit ``prompts/`` en vul ``{{placeholders}}`` in.

    Code levert alleen de feiten (cijfers/clusters) via ``vervangingen``; de
    redactie staat in het ``.md``-bestand. Faalt luid bij een niet-ingevulde
    placeholder — een stille gap in een auditrapport is erger dan een crash.
    """
    tekst = (_PROMPT_DIR / f"{naam}.md").read_text(encoding="utf-8")
    # Strip HTML-commentaar (de redacteur-notitie bovenaan het bestand).
    tekst = re.sub(r"<!--.*?-->\n?", "", tekst, flags=re.DOTALL)
    for sleutel, waarde in vervangingen.items():
        tekst = tekst.replace(f"{{{{{sleutel}}}}}", waarde)
    overgebleven = re.findall(r"\{\{(\w+)\}\}", tekst)
    if overgebleven:
        raise ValueError(
            f"Prompt {naam!r}: niet-ingevulde placeholder(s) {sorted(set(overgebleven))}"
        )
    return tekst.strip()


def _check_verboden_woorden(tekst: str, sectie: str = "aanbevelingen") -> list[str]:
    """Deterministische gate: zoek verboden NC-woorden in een gegenereerde sectie.

    Returnt de gevonden woorden (leeg = schoon) en logt één waarschuwing als er
    hits zijn. Dit is de auditeerbare garantie achter de aanbevelingen-prompt —
    zie spec report-generation, requirement 'Aanbevelingen-template zonder
    NC-woorden'. Matcht op woordgrens, dus legitieme samenstellingen als
    'risicobeoordeling' worden niet gevlagd; losse 'risico'('s) wel.
    """
    laag = tekst.lower()
    gevonden = sorted({w for w in _VERBODEN_WOORDEN if re.search(rf"\b{re.escape(w)}\b", laag)})
    if gevonden:
        logger.warning(
            "Verboden woord(en) in %s-sectie: %s — herformuleer naar de gewenste "
            "eindsituatie (actie → resultaat), niet de tekortkoming.",
            sectie,
            ", ".join(gevonden),
        )
    return gevonden


def _format_top(bevindingen: list[dict[str, Any]], teller: Counter[str], n: int = 5) -> str:
    """Top-N clusters per clausule met tot 3 voorbeelddocumenten."""
    regels: list[str] = []
    for clausule, aantal in teller.most_common(n):
        voorbeelden = [
            b["document_naam"]
            for b in bevindingen
            if b["clausule"] == clausule and b["classificatie"] in ("NC", "OFI")
        ][:3]
        voorbeeld_tekst = "; ".join(v[:60] for v in voorbeelden) if voorbeelden else "(geen)"
        regels.append(f"- {clausule} ({aantal}x): voorbeelddocs: {voorbeeld_tekst}")
    return "\n".join(regels) if regels else "(geen)"


_MANAGEMENT_CONTEXT = """\
Organisatiecontext Conduction:
- Nederlands softwarebedrijf (open-source, publieke sector).
- BYOD: laptops eigendom medewerker. Formele activa-retournering (5.11/6.5)
  beperkt tot klein materiaal; data/toegangsrevocatie is het relevante punt.
- Interne documenten zijn vertrouwelijkheid-geindexeerd in de handleidingen
  (5.12 intern = positief). NC op 5.12 betreft uitsluitend externe
  documenten/communicatie.
- Afwijkingsprocedure is gedocumenteerd via memo's (10.2/8.7 vaak positief).
"""


def _oordeel_zin(nc_count: int) -> str:
    """Strikt sjabloon voor het oordeel — voorkomt LLM-hedging."""
    if nc_count:
        return (
            f"De organisatie voldoet niet aan de norm vanwege {nc_count} "
            "geconstateerde non-conformiteiten; correctieve maatregelen "
            "vereist (zie §3)."
        )
    return "De organisatie voldoet aan de norm."


def _oordeel_instructie(nc_count: int) -> str:
    """Instructie-zin voor revisie-prompt: hoe om te gaan met het oordeel."""
    if nc_count:
        return f"Vervang het oordeel door precies deze zin: '{_oordeel_zin(nc_count)}'"
    return "Behoud het positieve oordeel — er zijn geen NC's."


def _management_summary_prompt(bevindingen: list[dict[str, Any]]) -> str:
    """Bouw de management-summary-prompt: feiten in code, redactie uit versie-prompt."""
    nc_count = sum(1 for b in bevindingen if b["classificatie"] == "NC")
    ofi_count = sum(1 for b in bevindingen if b["classificatie"] == "OFI")
    pos_count = sum(1 for b in bevindingen if b["classificatie"] == "positief")

    nc_per_clausule = Counter(b["clausule"] for b in bevindingen if b["classificatie"] == "NC")
    ofi_per_clausule = Counter(b["clausule"] for b in bevindingen if b["classificatie"] == "OFI")
    pos_per_clausule = Counter(
        b["clausule"] for b in bevindingen if b["classificatie"] == "positief"
    )

    gemengd = sorted(
        c
        for c in set(ofi_per_clausule) & set(pos_per_clausule)
        if ofi_per_clausule[c] > 5 and pos_per_clausule[c] > 5
    )
    bridging_eis = (
        f"BRIDGING VERPLICHT: clausule(s) {', '.join(gemengd)} staan zowel hoog "
        "in de OFI's als in de positieve bevindingen. Voeg één korte zin toe "
        "die uitlegt dat dit niet tegenstrijdig is — bv. dat de uitvoering "
        "werkt maar de vastlegging gefragmenteerd is. Geen verzonnen oorzaak; "
        "alleen wat uit de cijfers volgt.\n\n"
        if gemengd
        else ""
    )

    return _laad_prompt(
        "management_summary_v1",
        {
            "management_context": _MANAGEMENT_CONTEXT,
            "nc_count": str(nc_count),
            "ofi_count": str(ofi_count),
            "pos_count": str(pos_count),
            "top_nc_tekst": _format_top(bevindingen, nc_per_clausule, n=8),
            "top_ofi_tekst": _format_top(bevindingen, ofi_per_clausule, n=5),
            "top_pos_tekst": _format_top(bevindingen, pos_per_clausule, n=5),
            "bridging_eis": bridging_eis,
            "oordeel_zin": _oordeel_zin(nc_count),
        },
    )


def _lees_basis_summary(pad: str) -> str:
    """Extraheer de 'Management Summary'-sectie uit een bestaand auditrapport."""
    with open(pad, encoding="utf-8") as f:
        inhoud = f.read()
    match = re.search(
        r"##\s*1\.\s*Management Summary\s*\n(.*?)(?=\n##\s*2\.|\Z)",
        inhoud,
        re.DOTALL,
    )
    if not match:
        raise ValueError(f"Kon 'Management Summary'-sectie niet vinden in {pad}")
    return match.group(1).strip()


def _actuele_cijfers_blok(bevindingen: list[dict[str, Any]]) -> str:
    """Feiten-blok met actuele DB-cijfers voor revisie-prompt."""
    nc = sum(1 for b in bevindingen if b["classificatie"] == "NC")
    ofi = sum(1 for b in bevindingen if b["classificatie"] == "OFI")
    pos = sum(1 for b in bevindingen if b["classificatie"] == "positief")

    nc_per_clausule = Counter(b["clausule"] for b in bevindingen if b["classificatie"] == "NC")
    ofi_per_clausule = Counter(b["clausule"] for b in bevindingen if b["classificatie"] == "OFI")
    pos_per_clausule = Counter(
        b["clausule"] for b in bevindingen if b["classificatie"] == "positief"
    )

    def _top(c: Counter[str], n: int = 8) -> str:
        return ", ".join(f"clausule {k}: {v}" for k, v in c.most_common(n))

    return (
        f"- Totaal: NC={nc}, OFI={ofi}, positief={pos}\n"
        f"- NC-clusters (top 8): {_top(nc_per_clausule, 8) or '(geen)'}\n"
        f"- OFI-clusters (top 8): {_top(ofi_per_clausule, 8)}\n"
        f"- Positieve clusters (top 8): {_top(pos_per_clausule, 8)}\n"
    )


def _revise_summary_prompt(basis: str, bevindingen: list[dict[str, Any]]) -> str:
    """Prompt voor tekstuele revisie van een bestaande summary."""
    nc = sum(1 for b in bevindingen if b["classificatie"] == "NC")
    return (
        "Je herschrijft een management summary van een ISO-auditrapport.\n\n"
        "STRIKT VERBODEN:\n"
        "- Documentnamen veranderen (laat staan zoals in basis-tekst)\n"
        "- Nieuwe acties, eigenaars, deadlines, uren, weken, RACI toevoegen\n"
        "- Voorbeeldrijen voor registers/matrices toevoegen\n"
        "- Concrete leveranciersnamen, tools of personen toevoegen\n"
        "- Implementatieplanning of fasering toevoegen\n\n"
        "VERPLICHT — STRUCTUUR INKORTEN:\n"
        "De basis-tekst heeft mogelijk meerdere verbetergebied-paragrafen. "
        "Vervang die door ÉÉN alinea: 'De auditor heeft N thema's "
        "vastgesteld waar verbetering nodig is — voor de geprioriteerde acties "
        "zie §3 Aanbevelingen.'\n\n"
        "VERPLICHT — CIJFERS UPDATEN naar actuele waardes hieronder.\n\n"
        "VERPLICHT — OORDEEL ACTUALISEREN:\n"
        f"De ACTUELE situatie is: {nc} non-conformiteiten. "
        f"{_oordeel_instructie(nc)}\n\n"
        f"ACTUELE CIJFERS:\n{_actuele_cijfers_blok(bevindingen)}\n"
        "ORIGINELE TEKST:\n===\n"
        f"{basis}\n===\n\n"
        "Geef ALLEEN de gereviseerde tekst."
    )


def _genereer_management_summary(bevindingen: list[dict[str, Any]]) -> str:
    """Genereer de management summary via Anthropic — data- of revisie-modus."""
    client = anthropic.Anthropic()

    basis_pad = os.environ.get("AUDIT_BASIS_SUMMARY")
    if basis_pad:
        if not os.path.exists(basis_pad):
            logger.warning(
                "AUDIT_BASIS_SUMMARY=%s bestaat niet — fallback data-gedreven.",
                basis_pad,
            )
        else:
            try:
                basis = _lees_basis_summary(basis_pad)
            except ValueError as e:
                logger.warning("Basis-summary niet leesbaar (%s) — fallback data-gedreven.", e)
            else:
                logger.info(
                    "Revisie-modus: basis-summary uit %s (%d karakters)",
                    basis_pad,
                    len(basis),
                )
                message = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=2000,
                    temperature=CLAUDE_TEMPERATUUR,
                    messages=[
                        {
                            "role": "user",
                            "content": _revise_summary_prompt(basis, bevindingen),
                        }
                    ],
                )
                tekst: str = message.content[0].text  # type: ignore[union-attr]
                return tekst.strip()

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        temperature=CLAUDE_TEMPERATUUR,
        messages=[{"role": "user", "content": _management_summary_prompt(bevindingen)}],
    )
    tekst2: str = message.content[0].text  # type: ignore[union-attr]
    return tekst2.strip()


def _groepeer_bevindingen(bevindingen: list[dict[str, Any]], norm_filter: str | None = None) -> str:
    """Groepeer bevindingen per clausule, gefilterd op norm-hoofdstuk-range."""
    per_clausule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bev in bevindingen:
        clausule = bev["clausule"]
        if norm_filter == "9001" and not any(clausule.startswith(str(c)) for c in range(4, 11)):
            continue
        if norm_filter == "27001" and any(clausule.startswith(str(c)) for c in range(4, 11)):
            continue
        per_clausule[clausule].append(bev)

    regels: list[str] = []
    for clausule_id in sorted(per_clausule):
        items = sorted(
            per_clausule[clausule_id],
            key=lambda b: VOLGORDE.get(b["classificatie"], 9),
        )
        regels.append(f"\nClausule {clausule_id}: {items[0]['clausule_titel']}\n")
        for bev in items:
            regels.append(
                f"  [{bev['classificatie']}] {bev['herkomst']} — "
                f"{bev['document_naam']}\n"
                f"  {bev['beschrijving']}\n"
            )
    return "".join(regels) if regels else "(Geen bevindingen voor deze norm)"


def _overall_oordeel(bevindingen: list[dict[str, Any]]) -> str:
    return "onvoldoende" if any(b["classificatie"] == "NC" for b in bevindingen) else "voldoende"


def _top3_aanbevelingen(bevindingen: list[dict[str, Any]]) -> str:
    """Deterministische input voor de aanbevelingen-prompt: top-3 NC's, dan OFI's.

    Levert alleen de feiten (clausule, classificatie, beschrijving, brondoc);
    de redactie naar SMART/positieve aanbevelingen gebeurt in
    :func:`_genereer_aanbevelingen` via de versie-prompt + LLM.
    """
    nc_items = [b for b in bevindingen if b["classificatie"] == "NC"]
    ofi_items = [b for b in bevindingen if b["classificatie"] == "OFI"]
    top3 = (nc_items + ofi_items)[:3]
    if not top3:
        return "Geen openstaande aanbevelingen."
    return "\n".join(
        f"{i + 1}. Clausule {b['clausule']} ({b['classificatie']}): "
        f"{b['beschrijving'][:200]} [doc: {b.get('document_naam', '?')[:60]}]"
        for i, b in enumerate(top3)
    )


def _genereer_aanbevelingen(bevindingen: list[dict[str, Any]]) -> str:
    """Genereer §3 Aanbevelingen via Anthropic (SMART, positief) + verboden-woorden-gate.

    De redactie-regels staan in ``prompts/aanbevelingen_v1.md``; deze functie
    levert de feiten, draait de LLM op lage temperatuur (near-idempotent) en
    controleert de output deterministisch op verboden NC-woorden.
    """
    invoer = _top3_aanbevelingen(bevindingen)
    if invoer == "Geen openstaande aanbevelingen.":
        return invoer

    prompt = _laad_prompt(
        "aanbevelingen_v1",
        {"management_context": _MANAGEMENT_CONTEXT, "aanbevelingen_input": invoer},
    )
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1200,
        temperature=CLAUDE_TEMPERATUUR,
        messages=[{"role": "user", "content": prompt}],
    )
    tekst: str = message.content[0].text  # type: ignore[union-attr]
    tekst = tekst.strip()
    _check_verboden_woorden(tekst, "aanbevelingen")
    return tekst


def _bouw_placeholders(
    bevindingen: list[dict[str, Any]],
    ontbrekende_clausules: list[dict[str, Any]],
    handmatige_review: list[dict[str, Any]],
    norm: str,
    management_summary: str,
    aanbevelingen: str | None = None,
) -> dict[str, str]:
    nc_count = sum(1 for b in bevindingen if b["classificatie"] == "NC")
    ofi_count = sum(1 for b in bevindingen if b["classificatie"] == "OFI")
    pos_count = sum(1 for b in bevindingen if b["classificatie"] == "positief")
    norm_labels = {
        "9001": "ISO 9001:2015",
        "27001": "ISO 27001:2022",
        "beide": "ISO 9001:2015 + ISO 27001:2022",
    }
    norm_label = norm_labels.get(norm, norm)
    ontbrekend_tekst = (
        "\n".join(f"- Clausule {o['clausule']}: {o['titel']}" for o in ontbrekende_clausules)
        or "Geen ontbrekende clausules gedetecteerd."
    )
    handmatige_tekst = (
        "\n".join(f"- {h['naam']}: {h['reden']}" for h in handmatige_review)
        or "Geen items voor handmatige review."
    )
    return {
        "rapport_titel": f"Auditrapport {norm_label} — {date.today()}",
        "norm": norm_label,
        "template_versie": "v1.0",
        "aanmaakdatum": str(date.today()),
        "auditdoel": f"Interne audit conform {norm_label}",
        "auditscope": "(in te vullen door auditor)",
        "uitvoeringsperiode": str(date.today()),
        "auditteam": "(in te vullen door auditor)",
        "referentienorm": norm_label,
        "vorige_audit_datum": "(onbekend)",
        "management_summary": management_summary,
        "totaal_nc": str(nc_count),
        "totaal_ofi": str(ofi_count),
        "totaal_positief": str(pos_count),
        "overall_oordeel": _overall_oordeel(bevindingen),
        "bevindingen_9001": _groepeer_bevindingen(bevindingen, "9001"),
        "bevindingen_27001": _groepeer_bevindingen(bevindingen, "27001"),
        "ontbrekende_clausules": ontbrekend_tekst,
        "handmatige_review_items": handmatige_tekst,
        "conclusie": management_summary[:300],
        "top3_aanbevelingen": (
            aanbevelingen if aanbevelingen is not None else _top3_aanbevelingen(bevindingen)
        ),
        "auditor_naam": "(in te vullen)",
        "auditor_handtekening_datum": str(date.today()),
        "management_naam": "(in te vullen)",
        "management_handtekening_datum": "",
    }


def genereer_rapport(
    bevindingen: list[dict[str, Any]],
    ontbrekende_clausules: list[dict[str, Any]],
    handmatige_review: list[dict[str, Any]],
    norm: str,
    template_doc_id: str | None = None,
    folder_id: str | None = None,
) -> str:
    """Kopieer template, vul placeholders. Returnt Doc-ID van het rapport."""
    template_doc_id = template_doc_id or os.environ.get("AUDIT_TEMPLATE_DOC_ID")
    folder_id = folder_id or os.environ.get("AUDIT_DRIVE_FOLDER_ID")
    if not template_doc_id:
        raise OSError(
            "AUDIT_TEMPLATE_DOC_ID niet ingesteld. "
            "Voer eerst `python -m iso_audit.reporting.template_setup` uit."
        )

    norm_labels = {"9001": "ISO9001", "27001": "ISO27001", "beide": "ISO9001-27001"}
    bestandsnaam = f"Auditrapport_{norm_labels.get(norm, norm)}_{date.today()}"

    kopie = _gws(
        "drive",
        "files",
        "copy",
        params={"fileId": template_doc_id},
        body={"name": bestandsnaam},
    )
    doc_id: str = kopie["id"]

    if folder_id:
        _gws(
            "drive",
            "files",
            "update",
            params={
                "fileId": doc_id,
                "addParents": folder_id,
                "removeParents": "root",
                "fields": "id,parents",
            },
            body={},
        )

    logger.info("Management summary genereren via Claude...")
    management_summary = _genereer_management_summary(bevindingen)
    logger.info("§3 Aanbevelingen genereren via Claude...")
    aanbevelingen = _genereer_aanbevelingen(bevindingen)
    placeholders = _bouw_placeholders(
        bevindingen,
        ontbrekende_clausules,
        handmatige_review,
        norm,
        management_summary,
        aanbevelingen=aanbevelingen,
    )
    requests = [
        {
            "replaceAllText": {
                "containsText": {"text": f"{{{{{naam}}}}}", "matchCase": True},
                "replaceText": waarde,
            }
        }
        for naam, waarde in placeholders.items()
    ]
    _gws(
        "docs",
        "documents",
        "batchUpdate",
        params={"documentId": doc_id},
        body={"requests": requests},
    )

    doc_inhoud = _gws("docs", "documents", "get", params={"documentId": doc_id})
    volledige_tekst = ""
    for elem in doc_inhoud.get("body", {}).get("content", []):
        for item in elem.get("paragraph", {}).get("elements", []):
            volledige_tekst += item.get("textRun", {}).get("content", "")

    resterende = re.findall(r"\{\{([^}]+)\}\}", volledige_tekst)
    if resterende:
        logger.warning("%d placeholder(s) niet ingevuld: %s", len(resterende), resterende)
    logger.info("Rapport aangemaakt: %s (ID: %s)", bestandsnaam, doc_id)
    return doc_id
