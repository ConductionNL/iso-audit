"""Lokale rapportage — schrijft het auditrapport als Markdown naar disk.

Wordt altijd uitgevoerd naast de Google Docs output.

Gemigreerd uit `Ops_to_Biz/audit/local_report.py` per milestone B §2.5.1 (deels).
Wijziging: lazy import van `bepaal_thema` naar
`iso_audit.classification.thema` (al gemigreerd in §2.2.6). Path-resolution
naar repo-root via `Path(__file__).resolve().parent.parent.parent.parent`.

Override via env-vars:
- `LOCAL_REPORT_DIR` — volledig pad voor de output-dir
- `AUDIT_RUN_ID` — sub-dir-naam onder `output/audit_reports/`
- `MIRO_BOARD_ID` — voor het bouwen van clickable links naar Miro-items
"""

from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# src/iso_audit/reporting/local_report.py → parent x 4 = repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BASE_OUTPUT_DIR = _REPO_ROOT / "output" / "audit_reports"

# Backwards-compat alias.
DEFAULT_OUTPUT_DIR = str(_BASE_OUTPUT_DIR)

VOLGORDE: dict[str, int] = {"NC": 0, "OFI": 1, "positief": 2}
BADGES: dict[str, str] = {"NC": "🔴 NC", "OFI": "🟠 OFI", "positief": "🟢 Positief"}


def _audit_run_dir() -> str:
    """Per-run subfolder onder `output/audit_reports/`, default `audit_<datum>`."""
    explicit = os.environ.get("LOCAL_REPORT_DIR")
    if explicit:
        return explicit
    run_id = os.environ.get("AUDIT_RUN_ID") or f"audit_{date.today().isoformat()}"
    return str(_BASE_OUTPUT_DIR / run_id)


def _norm_label(norm: str) -> str:
    return {
        "9001": "ISO 9001:2015",
        "27001": "ISO 27001:2022",
        "beide": "ISO 9001:2015 + ISO 27001:2022",
    }.get(norm, norm)


def _groepeer_per_clausule(
    bevindingen: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    per_clausule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bev in bevindingen:
        per_clausule[bev["clausule"]].append(bev)
    return {
        k: sorted(v, key=lambda b: VOLGORDE.get(b["classificatie"], 9))
        for k, v in sorted(per_clausule.items())
    }


def _doc_link(bev: dict[str, Any]) -> str:
    """Bouw een klikbare Markdown-link naar het brondocument."""
    doc_id = bev.get("doc_id", "")
    naam = bev.get("document_naam", "onbekend")
    if not doc_id:
        return f"_{naam}_"
    if bev.get("herkomst") == "Miro":
        board_id = os.environ.get("MIRO_BOARD_ID", "")
        if board_id:
            url = f"https://miro.com/app/board/{board_id}/?moveToWidget={doc_id}"
            return f"[{naam}]({url})"
        return f"_{naam}_"
    url = f"https://drive.google.com/file/d/{doc_id}/view"
    return f"[{naam}]({url})"


_THEMA_AANBEVELING: dict[str, dict[str, str]] = {
    "Memo & afwijkingsregistratie": {
        "wat": (
            "Eén centraal afwijkingenregister met vaste velden (datum, type, "
            "beschrijving, oorzaak, corrigerende maatregel, eigenaar, status); "
            "vervangt losse memo's."
        ),
        "toets": (
            "Bij volgende interne audit: 100% van afwijkingen sinds startdatum "
            "register staat met alle vereiste velden vastgelegd."
        ),
        "norm": "ISO 9001 §10.2 / ISO 27001 §10.1",
    },
    "Auditprogramma": {
        "wat": (
            "Standaard format voor opvolging interne audits, één pagina per "
            "kwartaal, gekoppeld aan directiebeoordeling."
        ),
        "toets": (
            "Vier kwartaal-pagina's per jaar beschikbaar; opvolging-acties "
            "traceerbaar tot audit-bevinding."
        ),
        "norm": "ISO 9001 §9.2 / ISO 27001 §9.2",
    },
    "Verificatie van doeltreffendheid": {
        "wat": (
            "Per corrigerende maatregel een meetbare KPI met meetmoment ná "
            "implementatie; effect-meting gedocumenteerd."
        ),
        "toets": (
            "Voor elke gesloten corrigerende maatregel: KPI gemeten en "
            "resultaat in register vastgelegd."
        ),
        "norm": "ISO 9001 §10.2.f",
    },
    "Context-analyse & belanghebbenden": {
        "wat": (
            "Contextanalyse jaarlijks bijgewerkt na organisatiewijzigingen, "
            "met expliciete koppeling aan stakeholders en hun verwachtingen."
        ),
        "toets": (
            "Datum laatste contextanalyse < 12 maanden; stakeholder-tabel "
            "sluit aan op feitelijke klant- en partner-portfolio."
        ),
        "norm": "ISO 9001 §4.1 / §4.2 / ISO 27001 §4.1 / §4.2",
    },
    "Klanttevredenheid": {
        "wat": (
            "Bij elke meting (NPS, evaluatie) verplicht een analyse-stap én "
            "vervolgactie, beide zichtbaar in MT-rapportage."
        ),
        "toets": ("Voor elk meetmoment: analyse-document + actiepunt-lijst aanwezig met eigenaar."),
        "norm": "ISO 9001 §9.1.2 / §9.1.3",
    },
    "Leveranciersbeheer": {
        "wat": (
            "Leveranciersregister met per partij: scope, SLA, jaarlijkse "
            "evaluatie, exit-procedure; minimaal voor kritieke diensten "
            "(hosting, monitoring)."
        ),
        "toets": (
            "Register dekt alle leveranciers waarvan storing direct klanten "
            "raakt; jaarlijkse evaluatie aantoonbaar uitgevoerd."
        ),
        "norm": "ISO 9001 §8.4 / ISO 27001 §5.19 / §5.20",
    },
    "Directiebeoordeling": {
        "wat": (
            "Vaste agenda directiebeoordeling met alle norm-vereiste input "
            "én output (klanttevredenheid, audits, NC's, kansen, middelen)."
        ),
        "toets": (
            "Notulen tonen behandeling van alle norm-vereiste agendapunten; "
            "besluiten met eigenaar vastgelegd."
        ),
        "norm": "ISO 9001 §9.3 / ISO 27001 §9.3",
    },
    "Logging & monitoring": {
        "wat": (
            "Logging-baseline per platform: wat wordt gelogd, hoelang "
            "bewaard, wie reviewt; review-cadans vastgelegd."
        ),
        "toets": (
            "Per kritiek platform een log-baseline document; review-uitkomsten "
            "aantoonbaar besproken."
        ),
        "norm": "ISO 27001 §8.15 / §8.16",
    },
    "Privacy & persoonsgegevens": {
        "wat": (
            "AVG-verwerkingsregister actueel houden; jaarlijkse review per "
            "verwerker; verwerkersovereenkomsten gekoppeld."
        ),
        "toets": (
            "Register-datum < 12 maanden; alle actieve verwerkers hebben getekende overeenkomst."
        ),
        "norm": "ISO 27001 §5.34 / AVG art. 30",
    },
    "Risicomanagement": {
        "wat": (
            "Risicoregister gekoppeld aan beheersmaatregelen (VvT); review-"
            "cadans vastgelegd; nieuwe risico's via vast proces toegevoegd."
        ),
        "toets": (
            "Risico's hebben elk een actieve beheersmaatregel; register-review "
            "aantoonbaar < 12 maanden."
        ),
        "norm": "ISO 27001 §6.1 / §8.2 / §8.3",
    },
    "Offboarding & activa-retournering": {
        "wat": (
            "Vaste procedure bij einde dienstverband: data-revocatie, "
            "toegangsrevocatie, BYOD-checklist; rolverdeling per stap."
        ),
        "toets": (
            "Voor elke offboarding sinds invoeringsdatum: gecompleteerde checklist aantoonbaar."
        ),
        "norm": "ISO 27001 §5.11 / §6.5",
    },
    "Overig": {
        "wat": (
            "Per item beoordelen of het een echte verbeterkans is en aan "
            "welke eigenaar/proces het hoort."
        ),
        "toets": ("Backlog-review met MT: elk item óf opgepakt, óf afgewezen met onderbouwing."),
        "norm": "n.v.t.",
    },
}

# Backwards-compat alias voor scripts die hier direct importeren.
_THEMA_AANPAK: dict[str, str] = {k: v["wat"] for k, v in _THEMA_AANBEVELING.items()}


def _render_clausules_met_themas(regels: list[str], bevindingen: list[dict[str, Any]]) -> None:
    """Render per clausule → thema-subsectie → bevindingen."""
    from iso_audit.classification.thema import bepaal_thema

    per_clausule = _groepeer_per_clausule(bevindingen)
    for clausule_id, items in per_clausule.items():
        titel = items[0].get("clausule_titel", "")
        if titel and titel != clausule_id:
            regels.append(f"### Clausule {clausule_id}: {titel}")
        else:
            regels.append(f"### Clausule {clausule_id}")
        regels.append("")

        thema_groepen: dict[str, list[dict[str, Any]]] = {}
        for bev in items:
            thema = bev.get("thema") or bepaal_thema(bev)
            thema_groepen.setdefault(thema, []).append(bev)

        def thema_key(kv: tuple[str, list[dict[str, Any]]]) -> tuple[bool, int, str]:
            thema, lijst = kv
            return (thema == "Overig", -len(lijst), thema)

        geordende_themas = sorted(thema_groepen.items(), key=thema_key)
        toon_thema_kop = len(geordende_themas) > 1

        for thema, groep in geordende_themas:
            if toon_thema_kop:
                tellers = Counter(b["classificatie"] for b in groep)
                kop_meta = " · ".join(
                    f"{tellers[c]} {c}" for c in ("NC", "OFI", "positief") if tellers.get(c)
                )
                regels.append(f"#### Thema: {thema} _({kop_meta})_")
                regels.append("")

            vol = [
                b
                for b in groep
                if (b.get("beschrijving") or "").strip() or (b.get("onderbouwing") or "").strip()
            ]
            titel_only = [b for b in groep if b not in vol]

            for bev in sorted(vol, key=lambda b: VOLGORDE.get(b["classificatie"], 9)):
                badge = BADGES.get(bev["classificatie"], bev["classificatie"])
                doc_link = _doc_link(bev)
                regels.append(f"**{badge}** — {bev['herkomst']}: {doc_link}")
                regels.append("")
                beschrijving = bev.get("beschrijving") or "_(geen beschrijving)_"
                regels.append(f"> {beschrijving}")
                regels.append("")
                if bev.get("onderbouwing"):
                    regels.append(f"_Onderbouwing: {bev['onderbouwing']}_")
                    regels.append("")

            if titel_only:
                tellers_to = Counter(b["classificatie"] for b in titel_only)
                samenvatting = " · ".join(
                    f"{tellers_to[c]} {c}" for c in ("NC", "OFI", "positief") if tellers_to.get(c)
                )
                regels.append(
                    f"_**{len(titel_only)} bevinding(en) zonder inhoudelijke "
                    f"onderbouwing** ({samenvatting}) — geclassificeerd op basis "
                    f"van documenttitel; vereist handmatige review. Bronnen:_"
                )
                regels.append("")
                for bev in sorted(titel_only, key=lambda b: VOLGORDE.get(b["classificatie"], 9)):
                    badge = BADGES.get(bev["classificatie"], bev["classificatie"])
                    regels.append(f"- {badge}: {_doc_link(bev)}")
                regels.append("")


def _render_ofi_uitleg(ofi_count: int) -> list[str]:
    """Render alleen de OFI-uitleg in §2a; de aggregatie-tabel staat in §3."""
    return [
        "## 2a. Wat zijn OFI's?",
        "",
        f"**OFI** staat voor *Opportunity For Improvement* — kans voor "
        f"verbetering. Een OFI is **geen** tekortkoming en heeft **geen** "
        f"invloed op het normoordeel. Het is een aandachtspunt waar de "
        f"organisatie iets aan kan doen om het managementsysteem te "
        f"versterken. Niet alle {ofi_count} OFI's hoeven gelijktijdig "
        f"opgepakt; zie §3 Aanbevelingen voor de geprioriteerde acties.",
        "",
        "---",
        "",
    ]


def _render_aanbevelingen(bevindingen: list[dict[str, Any]]) -> list[str]:
    """Render §3 — Aanbevelingen in 4-veld-format (Wat / Wie / Wanneer / Toets)."""
    from iso_audit.classification.thema import bepaal_thema

    nc_per_doc: dict[str, list[dict[str, Any]]] = {}
    for bev in bevindingen:
        if bev["classificatie"] != "NC":
            continue
        nc_per_doc.setdefault(bev.get("document_naam", "(onbekend)"), []).append(bev)

    ofi_thema_counter: Counter[str] = Counter()
    overig_ofi_count = 0
    for bev in bevindingen:
        if bev["classificatie"] != "OFI":
            continue
        thema = bev.get("thema") or bepaal_thema(bev)
        if thema == "Overig":
            overig_ofi_count += 1
            continue
        ofi_thema_counter[thema] += 1

    rows: list[str] = []
    nr = 1

    def _toets_kort(toets: str) -> str:
        return toets[:140] + "…" if len(toets) > 140 else toets

    nc_bronnen = sorted(nc_per_doc.items(), key=lambda kv: -len(kv[1]))
    for doc_naam, items in nc_bronnen:
        clausules_lijst = sorted({b["clausule"] for b in items})
        clausules_str = ", ".join(clausules_lijst)
        wat = (
            f"Corrigerende maatregel opstellen voor de bevindingen uit "
            f"_{doc_naam[:80]}_ (clausules {clausules_str}). "
            "Voor inhoud per NC: zie detail-secties §4/§5."
        )
        toets = (
            "Voor elke NC: oorzakenanalyse, corrigerende maatregel en "
            "effect-meting in centraal afwijkingenregister; bij volgende "
            "interne audit gesloten."
        )
        rows.append(
            f"| {nr} | **NC** — {doc_naam[:50]} ({len(items)} NC) | {wat} "
            f"<br>_Toets (ISO 9001 §10.2 / ISO 27001 §10.1):_ {toets} | "
            f"(rol in te vullen) | (deadline in te vullen) |"
        )
        nr += 1

    for thema, aantal in ofi_thema_counter.most_common(5):
        info = _THEMA_AANBEVELING.get(thema, _THEMA_AANBEVELING["Overig"])
        wat = info["wat"]
        toets = _toets_kort(info["toets"])
        norm = info.get("norm", "")
        rows.append(
            f"| {nr} | OFI — {thema} ({aantal}) | {wat} "
            f"<br>_Toets ({norm}):_ {toets} | (rol in te vullen) | "
            "(deadline in te vullen) |"
        )
        nr += 1

    if not rows:
        return [
            "## 3. Aanbevelingen",
            "",
            "_Geen openstaande aanbevelingen — geen NC's en geen OFI-thema's geclusterd._",
            "",
            "---",
            "",
        ]

    intro: list[str] = [
        "## 3. Aanbevelingen",
        "",
        "Onderstaande tabel bevat de geprioriteerde actiepunten op basis van "
        "de bevindingen. **NC-rijen** vereisen correctieve maatregelen om aan "
        "de norm te blijven voldoen. **OFI-rijen** zijn verbeterkansen die "
        "het managementsysteem versterken. De kolommen *Wie* en *Wanneer* "
        "zijn bewust open: deze worden door het MT vastgesteld tijdens de "
        "directiebeoordeling op basis van prioriteit en capaciteit.",
        "",
        "| # | Thema (aantal) | Wat (deliverable) + Toets-criterium | Wie | Wanneer |",
        "|---|---|---|---|---|",
        *rows,
        "",
    ]

    if overig_ofi_count:
        intro.append(
            f"_Daarnaast zijn {overig_ofi_count} OFI's geclassificeerd als "
            f"'Overig' (geen specifiek thema). Deze vereisen handmatige "
            "beoordeling per item — zie de detail-secties hieronder en de "
            "Excel-bevindingenlijst._"
        )
        intro.append("")

    intro.extend(["---", ""])
    return intro


def schrijf_rapport(
    bevindingen: list[dict[str, Any]],
    ontbrekende_clausules: list[dict[str, Any]],
    handmatige_review: list[dict[str, Any]],
    management_summary: str,
    norm: str,
    output_dir: str | None = None,
    gearchiveerd: list[dict[str, Any]] | None = None,
    scherpte: float = 1.0,
) -> str:
    """Schrijf het volledige auditrapport als Markdown naar disk."""
    output_dir = output_dir or _audit_run_dir()
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    norm_bestand = norm.replace(" ", "").replace("+", "-")
    scherpte_label = f"_s{str(scherpte).replace('.', '')}" if scherpte != 1.0 else ""
    bestandsnaam = f"Auditrapport_{norm_bestand}_{date.today()}{scherpte_label}.md"
    pad = out_path / bestandsnaam

    nc_count = sum(1 for b in bevindingen if b["classificatie"] == "NC")
    ofi_count = sum(1 for b in bevindingen if b["classificatie"] == "OFI")
    pos_count = sum(1 for b in bevindingen if b["classificatie"] == "positief")
    geen_count = sum(1 for b in bevindingen if b["classificatie"] == "geen bevinding")
    oordeel = "**onvoldoende**" if nc_count > 0 else "**voldoende**"

    titel_only_ofi = sum(
        1
        for b in bevindingen
        if b["classificatie"] == "OFI"
        and not (b.get("beschrijving") or "").strip()
        and not (b.get("onderbouwing") or "").strip()
    )
    data_kwaliteit_regel = ""
    if ofi_count and titel_only_ofi:
        pct = round(titel_only_ofi * 100 / ofi_count)
        data_kwaliteit_regel = (
            f"\n\n_Data-kwaliteit: {titel_only_ofi} van de {ofi_count} OFI's "
            f"({pct}%) zijn geclassificeerd op basis van documenttitel "
            "zonder inhoudelijke analyse. Deze vereisen handmatige review "
            "voordat ze in een actieplan worden opgenomen. Zie de "
            "detail-secties hieronder en de Excel-bevindingenlijst._"
        )

    regels: list[str] = [
        f"# Auditrapport {_norm_label(norm)}",
        "",
        "| | |",
        "|---|---|",
        f"| Datum | {date.today()} |",
        f"| Norm | {_norm_label(norm)} |",
        "| Template versie | v1.0 |",
        f"| Overall oordeel | {oordeel} |",
        "",
        "---",
        "",
        "## 1. Management Summary",
        "",
        management_summary + data_kwaliteit_regel,
        "",
        "---",
        "",
        "## 2. Resultaatoverzicht",
        "",
        "| Classificatie | Aantal |",
        "|---|---|",
        f"| Non-conformiteiten (NC) | {nc_count} |",
        f"| Kansen voor verbetering (OFI) | {ofi_count} |",
        f"| Positieve bevindingen | {pos_count} |",
    ]
    if geen_count:
        regels.append(f"| Geen bevinding (uit data, niet geclassificeerd) | {geen_count} |")
    totaal = nc_count + ofi_count + pos_count + geen_count
    regels.extend(
        [
            f"| **Totaal** | **{totaal}** |",
            "",
            "---",
            "",
        ]
    )

    if ofi_count > 0:
        regels.extend(_render_ofi_uitleg(ofi_count))

    regels.extend(_render_aanbevelingen(bevindingen))

    normen_secties: list[tuple[str, str]] = []
    if norm in ("9001", "beide"):
        normen_secties.append(("4. Bevindingen ISO 9001:2015", "9001"))
    if norm in ("27001", "beide"):
        normen_secties.append(
            (
                "5. Bevindingen ISO 27001:2022 (Addendum)"
                if norm == "beide"
                else "4. Bevindingen ISO 27001:2022",
                "27001",
            )
        )

    for sectie_titel, norm_filter in normen_secties:
        regels.append(f"## {sectie_titel}")
        regels.append("")
        gefilterd = [
            b
            for b in bevindingen
            if (
                norm_filter == "9001"
                and any(b["clausule"].startswith(str(c)) for c in range(4, 11))
            )
            or (
                norm_filter == "27001"
                and not any(b["clausule"].startswith(str(c)) for c in range(4, 11))
            )
        ]
        if not gefilterd:
            regels.append("_(geen bevindingen)_")
            regels.append("")
        else:
            _render_clausules_met_themas(regels, gefilterd)
        regels.append("---")
        regels.append("")

    regels.append("## 6. Ontbrekende bewijsstukken")
    regels.append("")
    if ontbrekende_clausules:
        for o in ontbrekende_clausules:
            regels.append(f"- Clausule {o['clausule']}: {o['titel']}")
    else:
        regels.append("_Geen ontbrekende clausules gedetecteerd._")
    regels.append("")

    if handmatige_review:
        regels.append("### Items voor handmatige review")
        regels.append("")
        for h in handmatige_review:
            regels.append(f"- {h['naam']}: {h['reden']}")
        regels.append("")

    if gearchiveerd:
        regels.append("## 7. Gearchiveerde documenten (>2 jaar oud)")
        regels.append("")
        regels.append(
            "_Onderstaande documenten zijn ouder dan 2 jaar en zijn niet "
            "meegenomen in de classificatie. Ze worden als OFI beschouwd: de "
            "organisatie is sindsdien dermate gewijzigd dat deze documenten "
            "dienen te worden herzien of ingetrokken._"
        )
        regels.append("")
        for doc in sorted(gearchiveerd, key=lambda d: d.get("modified_at", "")):
            datum = (doc.get("modified_at") or "")[:10]
            url = f"https://drive.google.com/file/d/{doc['id']}/view"
            regels.append(f"- [{doc['naam']}]({url}) _(laatst gewijzigd: {datum})_")
        regels.append("")

    regels.append("---")
    regels.append("")
    regels.append("## 8. Handtekeningblok")
    regels.append("")
    regels.append("| Rol | Naam | Datum |")
    regels.append("|---|---|---|")
    regels.append(f"| Lead-auditor | | {date.today()} |")
    regels.append("| Verantwoordelijk manager | | |")
    regels.append("")
    regels.append("---")
    regels.append(f"_Gegenereerd door geautomatiseerd audit-systeem op {date.today()}_")

    pad.write_text("\n".join(regels), encoding="utf-8")
    logger.info("Lokaal rapport geschreven: %s", pad)
    return str(pad)
