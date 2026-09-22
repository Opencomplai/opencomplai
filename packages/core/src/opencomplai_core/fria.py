"""Art. 27 Fundamental Rights Impact Assessment draft generator (D-1, CP-14).

CP-6 wired the checker's 'fria' obligation and a provider_fria artifact probe
into the gap/recommend pipeline but stopped at a fill-in-only template — the
same state QMS was in before CP-15. This module is the actual generator
consumed by `opencomplai fria generate`: it populates Art. 27(1)(a)-(f) from
real data (the system manifest, the checker's persisted session/obligations
when one exists, and the Art. 27 control-register row CP-6 already computes)
instead of leaving every cell "_fill in_".

Honesty rule, same as every other generator in this codebase (dossier.py,
gap_probes.py): a point with no real data backing it is labelled
"not captured", never fabricated.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from opencomplai_core.compliance_checker.models import ComplianceCheckerResult
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapStatus,
    SystemManifest,
)

_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "recommend" / "fria_template.md"
)

FRIA_DISCLAIMER = (
    "Informational draft only — not legal advice. Supports but does not "
    "replace the deployer's own fundamental rights impact assessment and "
    "market-surveillance-authority notification under Art. 27."
)

#: Art. 27(1)(a)-(f), in order — (point letter, element description).
FRIA_POINTS: tuple[tuple[str, str], ...] = (
    (
        "a",
        "Deployer's processes in which the system will be used, in line with "
        "its intended purpose",
    ),
    (
        "b",
        "Period of time, and frequency, each system is intended to be used",
    ),
    (
        "c",
        "Categories of natural persons and groups likely to be affected by "
        "its use in this specific context",
    ),
    (
        "d",
        "Specific risks of harm likely to affect the persons/groups identified in (c)",
    ),
    (
        "e",
        "Implementation of human oversight measures, per the instructions for use",
    ),
    (
        "f",
        "Measures to be taken if those risks materialise, including internal "
        "governance and complaint-handling arrangements",
    ),
)

_NOT_CAPTURED = (
    "Not captured by the system manifest or checker session — deployer must "
    "supply this before the assessment can be considered complete."
)


class FRIAPointAssessment(BaseModel):
    """One row of the Art. 27(1)(a)-(f) outline."""

    point: str = Field(..., description="Art. 27(1) point letter, e.g. 'a'")
    element: str = Field(..., description="What this point requires")
    assessment: str
    source: str = Field(
        ..., description="Where `assessment` came from, or 'not_captured'"
    )
    populated: bool = Field(
        ..., description="True when `assessment` is real data, not a placeholder"
    )


class FRIADocument(BaseModel):
    """Structured Art. 27 fundamental rights impact assessment draft.

    Mirrors `AnnexIVDossier`'s shape (an id, generation metadata, then
    structured content) so JSON consumers see a familiar pattern — see
    `opencomplai_core.dossier.AnnexIVDossier`.
    """

    fria_id: str = Field(..., description="UUID identifying this draft")
    system_id: str
    commit_ref: str
    generated_at: str = Field(..., description="ISO 8601 timestamp")
    entity_role: str | None = Field(
        None, description="Operator role (e.g. 'deployer') if known"
    )
    is_high_risk: bool = False
    trigger_obligation_ids: list[str] = Field(
        default_factory=list,
        description="Checker obligation ids present in the loaded session, if any",
    )
    gap_status: GapStatus | None = None
    gap_source: ArticleGapSource | None = None
    gap_evidence_ref: str | None = None
    gap_rationale: str | None = None
    points: list[FRIAPointAssessment] = Field(default_factory=list)
    populated_point_count: int = 0
    total_points: int = len(FRIA_POINTS)
    disclaimer: str = FRIA_DISCLAIMER


def _point_a(manifest: SystemManifest) -> tuple[str, str, bool]:
    purpose = (manifest.intended_purpose or "").strip()
    if purpose:
        return (
            f"System '{manifest.system_id}': {purpose}",
            "manifest.intended_purpose",
            True,
        )
    return (_NOT_CAPTURED, "not_captured", False)


def _point_b() -> tuple[str, str, bool]:
    # No manifest or checker field captures deployment period/frequency today.
    return (_NOT_CAPTURED, "not_captured", False)


def _point_c(
    checker_result: ComplianceCheckerResult | None,
) -> tuple[str, str, bool]:
    if checker_result is not None and checker_result.answers.get("hr2_annex_iii"):
        role = (
            checker_result.effective_entity.value
            if checker_result.effective_entity is not None
            else "deployer"
        )
        return (
            f"Checker session classified this use as Annex III high-risk "
            f"(role={role}); affected categories are the natural persons or "
            "groups subject to that use case — deployer must confirm the "
            "specific categories.",
            "checker_session.answers",
            True,
        )
    return (_NOT_CAPTURED, "not_captured", False)


def _point_d(manifest: SystemManifest) -> tuple[str, str, bool]:
    if manifest.known_limitations:
        return (
            "; ".join(manifest.known_limitations),
            "manifest.known_limitations",
            True,
        )
    return (_NOT_CAPTURED, "not_captured", False)


def _point_e(manifest: SystemManifest) -> tuple[str, str, bool]:
    if manifest.human_oversight_measures:
        return (
            "; ".join(manifest.human_oversight_measures),
            "manifest.human_oversight_measures",
            True,
        )
    return (_NOT_CAPTURED, "not_captured", False)


def _point_f(manifest: SystemManifest) -> tuple[str, str, bool]:
    procedure = (manifest.incident_response_procedure or "").strip()
    if procedure:
        return (procedure, "manifest.incident_response_procedure", True)
    return (_NOT_CAPTURED, "not_captured", False)


def generate_fria(
    manifest: SystemManifest,
    gap_row: ArticleGapStatus | None = None,
    checker_result: ComplianceCheckerResult | None = None,
) -> FRIADocument:
    """Build a populated Art. 27(1)(a)-(f) draft from real inputs.

    `gap_row` is the Art. 27 row from `build_gap_report()` (CP-6's
    control-register wiring); `checker_result` is the checker's own
    persisted `ComplianceCheckerResult` (see `CheckerSessionRef.report_json_path`
    on the manifest) when a checker session was run. Both are optional —
    absence degrades individual points to "not captured", never a fabricated
    claim.
    """
    assessments = (
        _point_a(manifest),
        _point_b(),
        _point_c(checker_result),
        _point_d(manifest),
        _point_e(manifest),
        _point_f(manifest),
    )
    points = [
        FRIAPointAssessment(
            point=letter,
            element=element,
            assessment=assessment,
            source=source,
            populated=populated,
        )
        for (letter, element), (assessment, source, populated) in zip(
            FRIA_POINTS, assessments, strict=True
        )
    ]

    entity_role = manifest.operator_role or (
        checker_result.effective_entity.value
        if checker_result is not None and checker_result.effective_entity is not None
        else None
    )
    is_high_risk = manifest.high_risk_presumption or (
        checker_result.is_high_risk if checker_result is not None else False
    )
    trigger_obligation_ids = (
        [item.id for item in checker_result.obligations]
        if checker_result is not None
        else []
    )

    return FRIADocument(
        fria_id=str(uuid.uuid4()),
        system_id=manifest.system_id,
        commit_ref=manifest.commit_ref,
        generated_at=datetime.now(UTC).isoformat(),
        entity_role=entity_role,
        is_high_risk=is_high_risk,
        trigger_obligation_ids=trigger_obligation_ids,
        gap_status=gap_row.status if gap_row is not None else None,
        gap_source=gap_row.source if gap_row is not None else None,
        gap_evidence_ref=gap_row.evidence_ref if gap_row is not None else None,
        gap_rationale=gap_row.rationale if gap_row is not None else None,
        points=points,
        populated_point_count=sum(1 for p in points if p.populated),
        total_points=len(FRIA_POINTS),
    )


def render_fria_markdown(document: FRIADocument) -> str:
    """Render a `FRIADocument` into CP-6's fria_template.md, placeholders filled.

    Reuses the same template file `opencomplai recommend` renders (fill-in
    only, via `recommend_engine._render_fria_fill_in`) — this is the
    data-populated consumer CP-14 adds.
    """
    content = _TEMPLATE_PATH.read_text(encoding="utf-8")
    status = document.gap_status.value.upper() if document.gap_status else "UNVERIFIED"
    source = document.gap_source.value if document.gap_source else "generator"
    evidence_ref = document.gap_evidence_ref or "opencomplai fria generate"
    rationale = document.gap_rationale or (
        "Generated directly by `opencomplai fria generate` (no prior "
        "`opencomplai gaps` run supplied)."
    )
    content = (
        content.replace("{{article}}", "Art. 27")
        .replace("{{status}}", status)
        .replace("{{source}}", source)
        .replace("{{evidence_ref}}", evidence_ref)
        .replace("{{rationale}}", rationale)
        .replace(
            "{{fria_prefilled_notice}}",
            "Populated from the system manifest and checker session below, "
            "where real data existed. Cells still marked `_fill in_` (the "
            "Owner column, always, plus any Assessment cell that stayed "
            "unpopulated) require deployer input — this draft is not a "
            "substitute for a completed assessment.",
        )
    )
    for point in document.points:
        content = content.replace(
            f"{{{{fria_1{point.point}_assessment}}}}", point.assessment
        )
    return content
