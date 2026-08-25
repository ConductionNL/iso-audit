"""Assembleer een :class:`AuditMemo` uit findings + norm-DB + profiel + input.

Bindt classifier, pattern-detector en norm-lookup samen tot het render-model,
en stempelt de audit-trail-metadata (profiel, tool-versie, timestamp,
findings-hash). Geen LLM; deterministisch op een vaste ``now``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from iso_audit.memo import __version__ as memo_version
from iso_audit.memo.classifier import DefaultClassifier
from iso_audit.memo.models import (
    ActionRow,
    AuditMemo,
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


def _nc_block(
    f: Finding,
    findings: list[Finding],
    norm_db: NormDatabase,
    detector: DefaultPatternDetector,
    language: str,
) -> NCBlock:
    return NCBlock(
        title=f.title,
        citations=_citations(f, norm_db, language),
        kern=f.kern,
        deviation=f.deviation or f.description,
        pattern_note=detector.pattern_note(f.clause, findings),
        corrective_measure=f.corrective_measure or "(corrigerende maatregel in te vullen)",
        actions=f.actions or [ActionRow(wat="(actie in te vullen)")],
        bronnen=f.bronnen,
        reasoning=f.reasoning,
        triage_status=f.triage_status,
    )


def _improvement_block(f: Finding, norm_db: NormDatabase, language: str) -> ImprovementBlock:
    return ImprovementBlock(
        title=f.title,
        citations=_citations(f, norm_db, language),
        deviation=f.deviation or f.description,
        classification_rationale=(
            f.classification_rationale or "(classificatie-rationale in te vullen)"
        ),
        suggestion=f.suggestion,
        bronnen=f.bronnen,
    )


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
    threshold: int = 10,
    now: datetime | None = None,
) -> AuditMemo:
    """Bouw het render-model. ``now`` injecteerbaar voor reproduceerbare tests."""
    classifier = DefaultClassifier()
    detector = DefaultPatternDetector()
    lang = language or profile.defaults.language

    # Alleen door de auditor bevestigde (valide) NC's in de memo; niet_valide
    # (false positive) en follow_up (afspraak nodig, voorstel tot uitsluiting)
    # vallen eruit. De memo is gated op 'geen open kandidaten' (zie API).
    nc_blocks = [
        _nc_block(f, findings, norm_db, detector, lang)
        for f in classifier.ncs(findings)
        if f.triage_status == "valide"
    ]
    improvements = [
        _improvement_block(f, norm_db, lang) for f in classifier.improvements(findings, threshold)
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
