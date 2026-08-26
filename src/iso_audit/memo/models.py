"""Pydantic v2 models voor de auditmemo.

Splitst input-modellen (Finding, HistoricalNC) van de samengestelde
render-modellen (NCBlock, ImprovementBlock, AuditMemo). Boring & auditable:
strikte velden, geen impliciete defaults waar een keuze betekenis heeft.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field

Severity = Literal["NC", "OFI", "POSITIVE", "UNCLASSIFIED"]
HistoricalStatus = Literal["open", "in_progress", "closed"]
# Auditor-triage van een kandidaat-NC:
# `open` = nog te beoordelen (default); `valide` = bevestigde NC (→ memo);
# `niet_valide` = geen NC (bewijs bestaat, false positive); `follow_up` = bewijs
# buiten tool-scope → afspraak nodig, tool stelt uitsluiting voor (verify_with).
TriageStatus = Literal["open", "valide", "niet_valide", "follow_up"]


# --- Input-modellen ---------------------------------------------------------


class BronRef(BaseModel):
    """Eén brondocument onder een bevinding — klikbare link + waarom het bijdraagt.

    Maakt de keten ``bevinding → brondocument`` zichtbaar in de UI: de auditor
    kan een kop-NC uitklappen en doorklikken naar het echte Drive-document /
    Jira-issue, met per bron de reden waarom het een (kandidaat-)NC-signaal is.
    """

    herkomst: str = ""  # Drive / Jira / Miro / …
    doc_id: str = ""
    doc_naam: str = ""
    url: str | None = None  # link naar het brondocument (indien af te leiden uit herkomst+id)
    beschrijving: str = ""  # waarom dit document bijdraagt aan de (kandidaat-)NC


class Finding(BaseModel):
    """Eén bevinding uit de findings-dataset (input-contract)."""

    id: str
    severity: Severity
    standard: str  # norm-DB slug, bv. "iso-27001-2022"
    clause: str  # primaire clausule, bv. "10.2"
    title: str
    description: str
    evidence: list[str] = Field(default_factory=list)
    extra_clauses: list[str] = Field(default_factory=list)  # extra geciteerde clausules
    source: str | None = None  # herkomst-bron: bevinding berust op bron Y (Drive/Miro/…)
    source_memo: str | None = None
    promote_to_improvement: bool = False
    # Optionele, auditor-geleverde redactie voor de memo. Afwezig → builder
    # gebruikt `description` als afwijking en toont placeholders.
    deviation: str | None = None
    corrective_measure: str | None = None
    actions: list[ActionRow] = Field(default_factory=list)
    classification_rationale: str | None = None  # voor verbeterpunten
    suggestion: str | None = None
    # Triage-checklist: redenatie (wat de tool aantrof) + auditor-status.
    reasoning: list[str] = Field(default_factory=list)
    # Brondocumenten onder deze bevinding (uitklapbaar in de UI, met links).
    bronnen: list[BronRef] = Field(default_factory=list)
    # Thema (vaste taxonomie) — groepeert OFI's: één thema aanpakken tilt de
    # organisatie breed op. Keyword-bepaald (bepaal_thema), geen LLM nodig.
    thema: str | None = None
    # NC: concrete voorbeelden van hoe de tool het bewijs idealiter had gezien —
    # helpt de auditor bij de triage (LLM-gedraft, auditor-spiegel).
    examples: list[str] = Field(default_factory=list)
    kern: str = ""
    """Synthese-zin uit de autonome review; zie `NCBlock.kern`."""
    triage_status: TriageStatus = "open"
    # Bij follow_up: LLM-suggestie met wie het bewijs te verifiëren (voorstel
    # tot uitsluiting). Auditor maakt de afspraak.
    verify_with: str | None = None


class HistoricalNC(BaseModel):
    """Entry uit het doorlopende historical-NCs-register."""

    id: str
    source_audit: str
    source_document: str
    finding_summary: str
    status: HistoricalStatus
    closed_date: str | None = None
    closed_evidence: str | None = None


# --- Render-modellen (samengesteld) -----------------------------------------


class ClauseCitation(BaseModel):
    """Genormeerd citaat zoals het in een NC/verbeterpunt-blok verschijnt."""

    standard: str
    clause: str
    title: str
    text: str


class ActionRow(BaseModel):
    """Rij in een action-table. Lege wie/waar/uiterlijk = placeholder."""

    wat: str
    wie: str | None = None
    waar: str | None = None
    uiterlijk: str | None = None


class NCBlock(BaseModel):
    """Eén NC-blok: kan meerdere clausules citeren en meerdere evidence-items bundelen."""

    code: str = ""
    """"NC 1", "NC 2", … — zodat een blok in een vergadering aan te wijzen is en in het
    detailrapport terug te vinden. Zo deed het handgemaakte Q2-memo het ook."""
    title: str
    citations: list[ClauseCitation]
    kern: str = ""
    """Eén zin: wat is hier het gemeenschappelijke gebrek.

    Dit is wat het handgemaakte Q2-memo leesbaar maakt — "Drie clausules, één hoofdgebrek: er is
    geen gedocumenteerd en getest continuïteitsbeheer." Zonder die zin is een NC-blok een
    opsomming van citaten, en dan leest een memo van drie A4 als een korte bijlage.

    Komt uit de autonome review, die per clausule zo'n zin produceert. Leeg als er geen review
    heeft gedraaid: een verzonnen synthese is erger dan geen synthese."""
    deviation: str  # "waar de praktijk afwijkt"
    pattern_note: str | None = None  # cross-clause patroon (auto)
    corrective_measure: str  # dwingende taal, geen "aanbeveling"
    actions: list[ActionRow] = Field(default_factory=list)
    bronnen: list[BronRef] = Field(default_factory=list)  # brondocumenten met links
    # Triage-checklist (auditor-spiegel): redenatie + status. Bij `valide` toont
    # de render geen checklist (bevestigde NC); anders wel.
    reasoning: list[str] = Field(default_factory=list)
    triage_status: TriageStatus = "open"


class ImprovementBlock(BaseModel):
    """Verbeterpunt met verplichte classificatie-rationale."""

    code: str = ""  # "OFI 1", "OFI 2", … — zie NCBlock.code
    title: str
    citations: list[ClauseCitation]
    kern: str = ""  # synthese-zin uit de review; zie NCBlock.kern
    deviation: str
    classification_rationale: str  # "waarom verbeterpunt en geen NC?"
    suggestion: str | None = None
    bronnen: list[BronRef] = Field(default_factory=list)  # brondocumenten met links


class Bronaanduiding(BaseModel):
    """Eén geraadpleegde bron, met de aanduiding waarmee je hem terugvindt.

    "Google Drive" zegt niets — wélke map? Zonder identificatie kan een externe auditor de scope
    van de audit niet natrekken en is de regel decoratie. `identificatie` is de map-id, het
    projectsleutelwoord of het pad; `url` is de klikbare vorm als die bestaat.
    """

    naam: str
    identificatie: str = ""
    url: str | None = None


def _als_bronaanduiding(waarde: object) -> object:
    """Een kale string blijft werken: bestaande `memo-input.yaml` heeft `sources: [str]`."""
    if isinstance(waarde, str):
        return {"naam": waarde}
    return waarde


class MemoContext(BaseModel):
    """Context-sectie: data-gedreven, niet hardcoded."""

    audit_cycle: str
    scope: dict[str, str]  # norm-slug -> geauditeerde hoofdstukken
    sources: list[Annotated[Bronaanduiding, BeforeValidator(_als_bronaanduiding)]]
    dataset_counts: dict[str, int]  # totaal + per severity
    scope_caveat: str
    independence_caveat: str | None = None
    discussion: str | None = None  # datum + met wie; None = placeholder


class MemoInput(BaseModel):
    """Auditor-geleverde memo-koptekst + context (los van de findings-dataset)."""

    title: str
    cycle: str  # bv. "Q2 2026" — verschijnt in subtitle
    date: str
    version: str
    lead_summary: str
    detail_report_ref: str
    context: MemoContext


class AuditMemo(BaseModel):
    """Top-level render-model: alles wat de template nodig heeft."""

    title: str
    subtitle: str  # auditor | rol · cyclus
    date: str
    version: str
    lead_summary: str
    context: MemoContext
    nc_blocks: list[NCBlock]
    improvements: list[ImprovementBlock]
    historical_ncs: list[HistoricalNC]
    detail_report_ref: str
    # Audit-trail: profile-slug/-versie, tool-versie, render-timestamp,
    # findings-dataset-hash. Onzichtbaar als HTML-comment in de output.
    metadata: dict[str, str] = Field(default_factory=dict)


# Finding verwijst vooruit naar ActionRow (hierboven gedefinieerd) → resolve.
Finding.model_rebuild()
