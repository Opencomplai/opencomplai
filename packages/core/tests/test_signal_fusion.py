"""Signal fusion — dedupe, correlate, scope weighting."""

from __future__ import annotations

from opencomplai_core.models import (
    EvidenceItem,
    EvidenceKind,
    EvidenceScope,
    Reachability,
    SignalCategory,
)
from opencomplai_core.scanner.fusion import fuse_evidence


def _ev(
    token: str,
    scope: EvidenceScope,
    reach: Reachability,
    kind: EvidenceKind = EvidenceKind.IMPORT,
    conf: float = 0.8,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"ev_{token}_{scope.value}",
        evidence_kind=kind,
        category=SignalCategory.AI_SDK,
        token_hash=f"sha256:{token}",
        token_label=token,
        locations=[f"src/{token}.py:1"],
        scope=scope,
        reachability=reach,
        detector_id="DET_TEST",
        detector_version="1.0.0",
        redaction_level="hash_only",
        rationale_code="test",
        confidence=conf,
    )


def test_dev_only_dependency_stays_low_strength():
    items = [
        _ev(
            "openai",
            EvidenceScope.TEST,
            Reachability.MANIFEST_ONLY,
            EvidenceKind.DEPENDENCY,
            0.5,
        )
    ]
    findings = fuse_evidence(items)
    assert len(findings) == 1
    assert findings[0].strength < 0.3


def test_prod_callsite_correlates_stronger():
    items = [
        _ev(
            "openai",
            EvidenceScope.PROD,
            Reachability.MANIFEST_ONLY,
            EvidenceKind.DEPENDENCY,
            0.7,
        ),
        _ev(
            "openai",
            EvidenceScope.PROD,
            Reachability.REACHABLE_ENTRYPOINT,
            EvidenceKind.CALLSITE,
            0.9,
        ),
    ]
    findings = fuse_evidence(items)
    assert len(findings) == 1
    assert findings[0].strength > 0.5
    assert "corroborated_evidence" in findings[0].confidence_rationale


def test_duplicate_evidence_dedupes_deterministically():
    items = [
        _ev("openai", EvidenceScope.PROD, Reachability.IMPORT_ONLY),
        _ev("openai", EvidenceScope.PROD, Reachability.IMPORT_ONLY),
    ]
    f1 = fuse_evidence(items)
    f2 = fuse_evidence(items)
    assert f1[0].finding_id == f2[0].finding_id
    assert len(f1[0].evidence_ids) == 2
