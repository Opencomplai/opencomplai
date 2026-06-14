"""Shared evidence builder for detectors."""

from __future__ import annotations

from opencomplai_core.models import (
    EvidenceItem,
    EvidenceKind,
    EvidenceScope,
    Reachability,
    SignalCategory,
)
from opencomplai_core.scanner._hashing import evidence_id, token_hash


def scope_to_reachability(scope: EvidenceScope, kind: EvidenceKind) -> Reachability:
    if kind in (EvidenceKind.DEPENDENCY, EvidenceKind.LOCKFILE_PACKAGE):
        return Reachability.MANIFEST_ONLY
    if scope == EvidenceScope.PROD:
        return Reachability.INTERNAL_CALLCHAIN
    if scope in (EvidenceScope.TEST, EvidenceScope.DEV, EvidenceScope.DOCS):
        return Reachability.IMPORT_ONLY
    return Reachability.UNKNOWN


def build_evidence(
    *,
    detector_id: str,
    detector_version: str,
    evidence_kind: EvidenceKind,
    category: SignalCategory,
    token_label: str,
    location: str,
    scope: EvidenceScope,
    rationale_code: str,
    confidence: float,
    reachability: Reachability | None = None,
) -> EvidenceItem:
    reach = reachability or scope_to_reachability(scope, evidence_kind)
    return EvidenceItem(
        evidence_id=evidence_id(
            detector_id, token_label, location, evidence_kind.value
        ),
        evidence_kind=evidence_kind,
        category=category,
        token_hash=token_hash(token_label),
        token_label=token_label,
        locations=[location],
        scope=scope,
        reachability=reach,
        detector_id=detector_id,
        detector_version=detector_version,
        redaction_level="hash_only",
        rationale_code=rationale_code,
        confidence=confidence,
    )
