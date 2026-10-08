"""Merge per-role checker results into one (repeatable ``--entity-type``).

Not vendored: the dashboard drift check does not compare this module. The engine
is evaluated once per role; this module only combines what it already returned.
Rationale lines are generated from result fields only, no legal wording.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from opencomplai_core.compliance_checker.models import ComplianceCheckerResult


@dataclass(frozen=True)
class MergedCheckerResult:
    result: ComplianceCheckerResult
    roles: list[str]
    obligation_ids: list[str]
    rationale: list[str]


def _status(result: ComplianceCheckerResult) -> str:
    if result.is_prohibited:
        return "prohibited"
    if result.is_high_risk:
        return "high risk"
    return "in scope" if result.in_scope else "out of scope"


def _rationale_line(role: str, result: ComplianceCheckerResult) -> str:
    entity = result.effective_entity.value if result.effective_entity else "unknown"
    ids = ", ".join(o.id for o in result.obligations) or "none"
    return f"{role} (effective {entity}): {_status(result)}; obligations: {ids}"


def _union_by_id(lists: Sequence[Sequence]) -> list:
    seen: dict[str, object] = {}
    for items in lists:
        for item in items:
            seen.setdefault(item.id, item)
    return list(seen.values())


def merge_role_results(
    items: Sequence[tuple[str, ComplianceCheckerResult]],
) -> MergedCheckerResult:
    """Combine one checker result per role; a single role is returned unchanged."""
    if not items:
        raise ValueError("merge_role_results needs at least one (role, result) pair")

    per_role: dict[str, ComplianceCheckerResult] = {}
    for role, result in items:
        per_role.setdefault(role, result)
    roles = list(per_role)
    results = list(per_role.values())
    rationale = [_rationale_line(r, res) for r, res in per_role.items()]

    if len(results) == 1:
        merged = results[0]
    else:
        first = results[0]
        path: list[str] = []
        for role, res in per_role.items():
            path.append(f"role:{role}")
            path.extend(res.determination_path)
        merged = ComplianceCheckerResult(
            checker_version=first.checker_version,
            in_scope=any(r.in_scope for r in results),
            status_changes=_union_by_id([r.status_changes for r in results]),
            obligations=_union_by_id([r.obligations for r in results]),
            determination_path=path,
            is_high_risk=any(r.is_high_risk for r in results),
            is_prohibited=any(r.is_prohibited for r in results),
            effective_entity=first.effective_entity,
            answers=dict(first.answers),
            session_id=None,
        )
    return MergedCheckerResult(
        result=merged,
        roles=roles,
        obligation_ids=[o.id for o in merged.obligations],
        rationale=rationale,
    )
