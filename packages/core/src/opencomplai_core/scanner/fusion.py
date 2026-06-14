"""Signal fusion — dedupe, correlate, score findings."""

from __future__ import annotations

import hashlib

from opencomplai_core.models import (
    DetectionFinding,
    EvidenceItem,
    EvidenceScope,
    Reachability,
    SignalCategory,
)
from opencomplai_core.scanner.mapping import signal_category_to_taxonomy

SCOPE_WEIGHT = {
    EvidenceScope.PROD: 1.0,
    EvidenceScope.TEST: 0.3,
    EvidenceScope.DEV: 0.25,
    EvidenceScope.DOCS: 0.15,
    EvidenceScope.GENERATED: 0.1,
    EvidenceScope.VENDOR: 0.1,
    EvidenceScope.UNKNOWN: 0.2,
}

REACHABILITY_WEIGHT = {
    Reachability.REACHABLE_ENTRYPOINT: 1.0,
    Reachability.INTERNAL_CALLCHAIN: 0.85,
    Reachability.IMPORT_ONLY: 0.4,
    Reachability.MANIFEST_ONLY: 0.25,
    Reachability.UNKNOWN: 0.2,
}


def _finding_id(category: SignalCategory, token_label: str) -> str:
    raw = f"{category.value}|{token_label}"
    return f"find_sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def fuse_evidence(evidence: list[EvidenceItem]) -> list[DetectionFinding]:
    groups: dict[tuple[SignalCategory, str], list[EvidenceItem]] = {}
    for item in evidence:
        key = (item.category, item.token_label)
        groups.setdefault(key, []).append(item)

    findings: list[DetectionFinding] = []
    for (category, token_label), items in sorted(
        groups.items(), key=lambda x: (x[0][0].value, x[0][1])
    ):
        locations = sorted({loc for it in items for loc in it.locations})
        scopes = [it.scope for it in items]
        reachabilities = [it.reachability for it in items]
        best_scope = max(scopes, key=lambda s: SCOPE_WEIGHT.get(s, 0.2))
        best_reach = max(reachabilities, key=lambda r: REACHABILITY_WEIGHT.get(r, 0.2))

        avg_conf = sum(it.confidence for it in items) / len(items)
        scope_w = SCOPE_WEIGHT.get(best_scope, 0.2)
        reach_w = REACHABILITY_WEIGHT.get(best_reach, 0.2)
        strength = min(1.0, avg_conf * scope_w * reach_w * len(items) ** 0.3)

        taxonomy = signal_category_to_taxonomy(category, token_label)
        rationale: list[str] = []
        if best_scope != EvidenceScope.PROD:
            rationale.append(f"scope_reduced:{best_scope.value}")
        if best_reach in (Reachability.MANIFEST_ONLY, Reachability.IMPORT_ONLY):
            rationale.append(f"reachability_reduced:{best_reach.value}")
        if len(items) > 1:
            rationale.append("corroborated_evidence")

        findings.append(
            DetectionFinding(
                finding_id=_finding_id(category, token_label),
                signal_category=category,
                evidence_ids=sorted(it.evidence_id for it in items),
                locations=locations,
                mapped_taxonomy=taxonomy,
                strength=round(strength, 4),
                scope=best_scope,
                reachability=best_reach,
                confidence_rationale=rationale,
                reviewer_prompt=(
                    f"Verify {category.value} signal '{token_label}' in declared purpose. "
                    f"Check locations: {', '.join(locations[:5])}."
                ),
            )
        )
    return findings
