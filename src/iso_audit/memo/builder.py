"""Assembleer een :class:`AuditMemo` uit findings + norm-DB + profiel + input.

Bindt classifier, pattern-detector en norm-lookup samen tot het render-model,
en stempelt de audit-trail-metadata (profiel, tool-versie, timestamp,
findings-hash). Geen LLM; deterministisch op een vaste ``now``.
"""

from __future__ import annotations

import hashlib
import html
import json
from datetime import UTC, datetime

from iso_audit.memo import __version__ as memo_version
from iso_audit.memo.groepering import (
    GEEN_THEMA,
    Themagroep,
    groepeer_ncs,
    groepeer_ofis,
)
from iso_audit.memo.models import (
    ActionRow,
    AuditMemo,
    BronRef,
    ClauseCitation,
    Finding,
    HistoricalNC,
    ImprovementBlock,
    MemoInput,
    NCBlock,
)
from iso_audit.memo.norm_lookup import NormDatabase
from iso_audit.memo.pattern_detection import DefaultPatternDetector
from iso_audit.memo.theme.profile import Profile


def _citations(f: Finding, norm_db: NormDatabase, language: str) -> list[ClauseCitation]:
    return [norm_db.citation(f.standard, c, language) for c in [f.clause, *f.extra_clauses]]


def _groep_citations(
    groep: Themagroep, norm_db: NormDatabase, language: str
) -> list[ClauseCitation]:
    """Alle clausules van het blok, elk één keer, op clausulenummer gesorteerd."""
    per_clausule: dict[tuple[str, str], ClauseCitation] = {}
    for f in groep.bevindingen:
        for citation in _citations(f, norm_db, language):
            per_clausule.setdefault((f.standard, citation.clause), citation)
    return [per_clausule[k] for k in sorted(per_clausule)]


def _groep_bronnen(groep: Themagroep) -> list[BronRef]:
    """Elke bron van elke bevinding, ontdubbeld. Bundelen mag geen bewijs verstoppen.

    Met een kern blijft de documentnaam staan maar vervalt de omschrijving: die was 45% van de
    memo-tekst (4.993 van 11.028 tekens op de werkset van 2026-08-26) en staat per bevinding al
    in het detailrapport. Wat de memo natrekbaar maakt is *welk* document — dat blijft.
    """
    gezien: dict[tuple[str, str, str], BronRef] = {}
    for f in groep.bevindingen:
        for bron in f.bronnen:
            # Ook `doc_naam` in de sleutel: twee bronnen met hetzelfde id maar een andere naam
            # zijn allebei tonen beter dan er stilletjes één weglaten.
            gezien.setdefault((bron.herkomst, bron.doc_id or "", bron.doc_naam), bron)
    bronnen = list(gezien.values())
    if groep.kern:
        return [b.model_copy(update={"beschrijving": ""}) for b in bronnen]
    return bronnen


def _groep_afwijking(groep: Themagroep) -> str:
    """De afwijkingen van het blok onder elkaar, met clausule ervoor — of leeg bij een kern.

    Is er een synthesezin, dan is die de blok-tekst en verhuist de onderbouwing per clausule naar
    het detailrapport, waar ze toch al staat (de memo verwijst ernaar in de voettekst). Zonder die
    regel groeit een thema-blok mee met zijn omvang: zeven bevindingen zijn zeven volledige
    afwijkingsteksten onder elkaar, en dan levert bundelen niets op. Zo leest het handgemaakte
    Q2-memo ook — één synthese in de memo, het detail in de bijlage.

    Is er geen kern (review niet gedraaid), dan is de afwijking alles wat we hebben en blijft ze
    staan. Eén bullet per bevinding en niet één samengesmolten alinea: de lezer moet kunnen zien
    welke constatering bij welke eis hoort, anders is het blok niet meer na te trekken.
    """
    if groep.kern:
        return ""
    delen = [(f.clause, (f.deviation or f.description).strip()) for f in groep.bevindingen]
    delen = [(c, t) for c, t in delen if t]
    if not delen:
        return ""
    if len(delen) == 1:
        return delen[0][1]
    regels = "".join(
        f"<li><strong>§{html.escape(clausule)}</strong> — {tekst}</li>" for clausule, tekst in delen
    )
    return f"<ul>{regels}</ul>"


def _nc_block(
    groep: Themagroep,
    findings: list[Finding],
    norm_db: NormDatabase,
    detector: DefaultPatternDetector,
    language: str,
) -> NCBlock:
    """Eén blok per thema. De titel is het thema; bij `Overig` is dat er niet, dus de bevinding."""
    eerste = groep.bevindingen[0]
    titel = eerste.title if groep.thema == GEEN_THEMA else groep.thema
    acties = [a for f in groep.bevindingen for a in f.actions]
    maatregelen = [f.corrective_measure for f in groep.bevindingen if f.corrective_measure]
    return NCBlock(
        title=titel,
        citations=_groep_citations(groep, norm_db, language),
        kern=groep.kern,
        deviation=_groep_afwijking(groep),
        pattern_note=detector.pattern_note(eerste.clause, findings),
        corrective_measure=maatregelen[0]
        if maatregelen
        else "(corrigerende maatregel in te vullen)",
        actions=acties or [ActionRow(wat="(actie in te vullen)")],
        bronnen=_groep_bronnen(groep),
        reasoning=eerste.reasoning,
        triage_status=eerste.triage_status,
    )


def _improvement_block(groep: Themagroep, norm_db: NormDatabase, language: str) -> ImprovementBlock:
    """Eén verbeterblok per thema, met alle waarnemingen erin.

    Niet één representant per cluster, zoals het was: van drie waarnemingen op hetzelfde thema
    kwam er dan één in de memo en verdwenen er twee, en dat maakt van een patroon een anekdote.

    De suggesties van álle waarnemingen blijven staan, ook als er een kern is. Bij een NC-blok
    verhuist het detail naar de bijlage, maar hier ís het verbeteradvies waar het om gaat.
    """
    eerste = groep.bevindingen[0]
    titel = eerste.title if groep.thema == GEEN_THEMA else groep.thema
    rationales = [
        f.classification_rationale for f in groep.bevindingen if f.classification_rationale
    ]
    suggesties = [f.suggestion.strip() for f in groep.bevindingen if f.suggestion]
    return ImprovementBlock(
        title=titel,
        citations=_groep_citations(groep, norm_db, language),
        kern=groep.kern,
        deviation=_groep_afwijking(groep),
        classification_rationale=(
            rationales[0] if rationales else "(classificatie-rationale in te vullen)"
        ),
        suggestion=_samengevoegde_suggestie(suggesties),
        bronnen=_groep_bronnen(groep),
    )


THEMA_DREMPEL = 3
"""Vanaf hoeveel OFI's op één thema het een verbeterpunt wordt.

Was 10, en telde toen clausules: op de werkset van 2026-08-25 haalde geen enkele clausule dat,
dus kwam er geen enkel verbeterpunt uit. Nu telt het thema's, en dan is 10 ook te hoog — 3 geeft
zeven samenhangende blokken (logging & monitoring, auditprogramma, back-up, privacy,
cryptografie, rollen, verificatie), 5 geeft er nog twee.

Drie losse waarnemingen op hetzelfde thema zijn een patroon; één is een waarneming, en die hoort
in het detailrapport."""


def _samengevoegde_suggestie(suggesties: list[str]) -> str | None:
    """De suggesties onder elkaar; ontdubbeld want dezelfde zin drie keer leest als drang."""
    uniek = list(dict.fromkeys(s for s in suggesties if s))
    if not uniek:
        return None
    if len(uniek) == 1:
        return uniek[0]
    return "<ul>" + "".join(f"<li>{s}</li>" for s in uniek) + "</ul>"


def _findings_hash(findings: list[Finding]) -> str:
    payload = json.dumps(
        [f.model_dump() for f in findings], sort_keys=True, ensure_ascii=False, default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_memo(
    *,
    findings: list[Finding],
    historical_ncs: list[HistoricalNC],
    profile: Profile,
    norm_db: NormDatabase,
    memo_input: MemoInput,
    language: str | None = None,
    threshold: int = THEMA_DREMPEL,
    now: datetime | None = None,
) -> AuditMemo:
    """Bouw het render-model. ``now`` injecteerbaar voor reproduceerbare tests."""
    detector = DefaultPatternDetector()
    lang = language or profile.defaults.language

    # Alleen door de auditor bevestigde (valide) NC's in de memo; niet_valide
    # (false positive) en follow_up (afspraak nodig, voorstel tot uitsluiting)
    # vallen eruit. De memo is gated op 'geen open kandidaten' (zie API).
    # Eén blok per thema, niet per bevinding: 47 bevestigde NC's gaven 47 blokken en 35
    # pagina's (gemeten 2026-08-26), terwijl het handgemaakte Q2-memo er twee had. Zie
    # `memo/groepering.py` voor waarom op thema en niet op clausule gebundeld wordt.
    nc_blocks = [
        _nc_block(groep, findings, norm_db, detector, lang) for groep in groepeer_ncs(findings)
    ]
    # Verbeterpunten bundelen op thema en niet op clausule: op de werkset van 2026-08-25 haalde
    # geen enkele clausule de drempel, terwijl de 53 OFI's zich over 16 thema's verdeelden.
    # Daar zitten de patronen, en een verbeteradvies gaat over een patroon.
    improvements = [
        _improvement_block(groep, norm_db, lang) for groep in groepeer_ofis(findings, threshold)
    ]

    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata = {
        "profile": profile.slug,
        "profile_schema": str(profile.schema_version),
        "tool_version": memo_version,
        "rendered_at": stamp,
        "findings_hash": _findings_hash(findings),
    }
    subtitle = f"{profile.auditor.name} | {profile.auditor.role} · {memo_input.cycle}"

    return AuditMemo(
        title=memo_input.title,
        subtitle=subtitle,
        date=memo_input.date,
        version=memo_input.version,
        lead_summary=memo_input.lead_summary,
        context=memo_input.context,
        nc_blocks=nc_blocks,
        improvements=improvements,
        historical_ncs=historical_ncs,
        detail_report_ref=memo_input.detail_report_ref,
        metadata=metadata,
    )
