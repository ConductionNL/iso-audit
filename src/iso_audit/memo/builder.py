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
    groepeer_positief,
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
    PositiveBlock,
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
    code: str,
) -> NCBlock:
    """Eén blok per thema. De titel is het thema; bij `Overig` is dat er niet, dus de bevinding."""
    eerste = groep.bevindingen[0]
    titel = eerste.title if groep.thema == GEEN_THEMA else groep.thema
    acties = [a for f in groep.bevindingen for a in f.actions]
    maatregelen = [f.corrective_measure for f in groep.bevindingen if f.corrective_measure]
    return NCBlock(
        code=code,
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


def _improvement_block(
    groep: Themagroep, norm_db: NormDatabase, language: str, code: str
) -> ImprovementBlock:
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
        code=code,
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


def _positieve_zin(groep: Themagroep) -> str:
    """De ene zin onder een positief thema.

    De kernzin van de review als die er is; dat is een oordeel dat gewogen is. Anders een
    feitelijke zin uit wat er telbaar is — hoeveel waarnemingen, over hoeveel clausules. Een
    lovende zin verzinnen zou hier het makkelijkst zijn en het minst waard: "de organisatie
    beheerst dit uitstekend" is niet na te rekenen, "14 waarnemingen op 6 clausules, geen
    afwijkingen" wel.
    """
    if groep.kern:
        return groep.kern
    n = len(groep.bevindingen)
    c = len(groep.clausules)
    waarnemingen = "waarneming" if n == 1 else "waarnemingen"
    clausules = "clausule" if c == 1 else "clausules"
    return (
        f"{n} bevestigde {waarnemingen} op {c} {clausules}; geen afwijkingen aangetroffen. "
        f"De onderbouwing per waarneming staat in de bewijslast."
    )


def _positive_block(
    groep: Themagroep, norm_db: NormDatabase, language: str, code: str
) -> PositiveBlock:
    """Eén positief thema, één zin. Geen afwijking, geen aanbeveling, geen bijlage-verwijzing."""
    return PositiveBlock(
        code=code,
        title=groep.thema,
        citations=_groep_citations(groep, norm_db, language),
        kern=_positieve_zin(groep),
        aantal=len(groep.bevindingen),
    )


MAX_VERBETERBLOKKEN = 3
"""Hoeveel verbeterthema's er ten hoogste in de memo komen.

Drie per kwartaal, want een memo is een agenda en geen inventaris. Wat afvalt staat compleet in
het detailrapport, en de memo zegt hoeveel het er zijn — een cap zonder melding leest als "dit
was alles".

Los van `THEMA_DREMPEL`: die bepaalt of een thema meetelt, deze hoeveel er getoond worden."""


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


def _positieve_notitie(findings: list[Finding], groepen: list[Themagroep]) -> str:
    """Wat er buiten de positieve blokken viel, in getallen.

    Twee groepen vallen weg: waarnemingen zonder thema (die clusteren niet) en waarnemingen die
    nog niet bevestigd zijn. Allebei benoemen, want een sectie die zwijgt over wat er niet in
    staat, leest als "dit was alles" — dezelfde regel als bij `improvements_note`.
    """
    alle = [f for f in findings if f.severity == "POSITIVE"]
    if not alle:
        return ""
    in_blokken = sum(len(g.bevindingen) for g in groepen)
    open_nog = sum(1 for f in alle if f.triage_status != "valide")
    delen = []
    if open_nog:
        delen.append(
            f"{open_nog} positieve waarneming(en) zijn nog niet bevestigd in de triage en "
            f"staan daarom niet hierboven"
        )
    zonder_thema = len(alle) - open_nog - in_blokken
    if zonder_thema > 0:
        delen.append(f"{zonder_thema} bevestigde waarneming(en) vielen buiten een thema")
    if not delen:
        return (
            f"Alle {len(alle)} positieve waarnemingen staan met hun onderbouwing in de bewijslast."
        )
    # Geen `.capitalize()`: die verlaagt de rest van de zin, en de zin begint hier met een getal.
    return "; ".join(delen) + ". Alle waarnemingen staan in de bewijslast."


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
    # Geen bovengrens op het aantal NC-blokken, en dat is een bewuste keuze. Zo'n grens laat
    # NC's buiten de memo vallen op omvang, zonder dat een mens erover besliste en zonder
    # vastgelegde reden — precies andersom dan het hoort. Wat niet in de memo thuishoort, wordt
    # in de **triage** uitgesloten, en dáár legt de trail vast wie dat besloot en waarom.
    #
    # De memo blijft daarmee een gevolg van auditor-beslissingen in plaats van een selectie die
    # het tool zelf maakt. Dat is de auditor-spiegel, en die weegt zwaarder dan een paginatelling.
    nc_blocks = [
        _nc_block(groep, findings, norm_db, detector, lang, f"NC {i}")
        for i, groep in enumerate(groepeer_ncs(findings), start=1)
    ]
    nc_note = ""
    # Verbeterpunten bundelen op thema en niet op clausule: op de werkset van 2026-08-25 haalde
    # geen enkele clausule de drempel, terwijl de 53 OFI's zich over 16 thema's verdeelden.
    # Daar zitten de patronen, en een verbeteradvies gaat over een patroon.
    # Twee losse knoppen, en dat onderscheid is het punt: `THEMA_DREMPEL` bepaalt hoe groot een
    # thema moet zijn om te tellen, `MAX_VERBETERBLOKKEN` hoeveel er in de memo komen. Op de
    # werkset van 2026-08-25 haalden zeven thema's de drempel, en zeven verbeterrichtingen in
    # één kwartaal is geen agenda maar een lijst.
    ofi_groepen = groepeer_ofis(findings, threshold)
    getoond = ofi_groepen[:MAX_VERBETERBLOKKEN]
    improvements = [
        _improvement_block(groep, norm_db, lang, f"OFI {i}")
        for i, groep in enumerate(getoond, start=1)
    ]
    rest = len(ofi_groepen) - len(getoond)
    improvements_note = (
        f"Nog {rest} andere thema('s) haalden de drempel voor een verbeterpunt; die staan met "
        f"hun waarnemingen in het detailrapport."
        if rest
        else ""
    )

    # Positieve waarnemingen ook benoemen: een memo die alleen gebreken opsomt, geeft een
    # scheef beeld van een organisatie en is voor een externe auditor minder bruikbaar — die wil
    # zien wát werkt, niet alleen wat niet werkt. Eén zin per thema is genoeg; wie meer wil
    # weten, heeft de bewijslast. Geen bovengrens: dezelfde reden als bij de NC-blokken —
    # afkappen op omvang laat iets uit de memo vallen zonder dat een mens erover besliste.
    positief_groepen = groepeer_positief(findings)
    positives = [
        _positive_block(groep, norm_db, lang, f"POS {i}")
        for i, groep in enumerate(positief_groepen, start=1)
    ]
    positives_note = _positieve_notitie(findings, positief_groepen)

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
        nc_note=nc_note,
        improvements=improvements,
        improvements_note=improvements_note,
        positives=positives,
        positives_note=positives_note,
        historical_ncs=historical_ncs,
        detail_report_ref=memo_input.detail_report_ref,
        metadata=metadata,
    )
