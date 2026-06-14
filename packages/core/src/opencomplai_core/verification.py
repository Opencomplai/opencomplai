"""
Ground Truth Verification Graph — claim resolution engine (REQ-GTVG-001).

Every claim submitted to resolve_claim reaches exactly one terminal outcome:
  VERIFIED — adapter response matches expected value
  ALERTED  — mismatch; BiasAlert emitted and linked to the task

The exactly-one-terminal-state invariant is enforced by the return type:
a VerificationTask with a non-None, non-PENDING outcome is terminal and
must never be mutated again.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from opencomplai_core.adapters.base import SourceAdapter
from opencomplai_core.models import (
    AlertSeverity,
    BiasAlert,
    VerificationOutcome,
    VerificationProof,
    VerificationTask,
)


async def resolve_claim(
    claim: dict,
    adapter: SourceAdapter,
) -> tuple[VerificationTask, VerificationProof | None, BiasAlert | None]:
    """
    Resolve a claim to exactly one terminal outcome.

    Args:
        claim: dict with keys: claim_ref, source_ref, expected_value (opt),
               metric (opt), threshold (opt).
        adapter: SourceAdapter to execute the lookup.

    Returns:
        (task, proof, alert) where:
          - task.outcome is VERIFIED or ALERTED (never PENDING)
          - proof is set when outcome == VERIFIED
          - alert is set when outcome == ALERTED
          - exactly one of (proof, alert) is non-None

    Raises:
        RuntimeError: propagated from adapter on DEPENDENCY_UNAVAILABLE.
    """
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    request_hash = _hash_dict(claim)

    # Execute adapter lookup — raises RuntimeError on connectivity failure
    response = await adapter.lookup(claim)

    response_hash = _hash_dict(response)

    expected = claim.get("expected_value")
    actual = response.get("value")

    if _values_match(expected, actual):
        outcome = VerificationOutcome.VERIFIED
        proof = VerificationProof(
            task_id=task_id,
            claim_ref=claim.get("claim_ref", ""),
            evidence_hash=response_hash,
            verified_at=now,
        )
        alert = None
    else:
        outcome = VerificationOutcome.ALERTED
        proof = None
        alert = BiasAlert(
            alert_id=str(uuid.uuid4()),
            severity=_severity_from_claim(claim),
            metric=claim.get("metric", "verification_mismatch"),
            threshold=float(claim.get("threshold", 0.0)),
            linked_event_id=task_id,
        )

    task = VerificationTask(
        task_id=task_id,
        claim_ref=claim.get("claim_ref", ""),
        source_ref=claim.get("source_ref", ""),
        request_hash=request_hash,
        response_hash=response_hash,
        outcome=outcome,
    )

    return task, proof, alert


def _hash_dict(d: dict) -> str:
    return f"sha256:{hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()}"


def _values_match(expected, actual) -> bool:
    """
    Compare expected vs actual claim values.

    When expected is None the claim has no assertion — treat as verified
    (the adapter ran successfully; no mismatch to report).
    """
    if expected is None:
        return True
    return str(actual) == str(expected)


def _severity_from_claim(claim: dict) -> AlertSeverity:
    """Derive alert severity from claim metadata; default HIGH for mismatches."""
    sev = str(claim.get("severity", "high")).lower()
    return {
        "low": AlertSeverity.LOW,
        "medium": AlertSeverity.MEDIUM,
        "high": AlertSeverity.HIGH,
        "critical": AlertSeverity.CRITICAL,
    }.get(sev, AlertSeverity.HIGH)
