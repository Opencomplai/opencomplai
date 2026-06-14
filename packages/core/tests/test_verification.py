"""Tests for the Ground Truth Verification Graph (REQ-GTVG-001)."""

import pytest
from opencomplai_core.adapters.offline import OfflineAdapter
from opencomplai_core.models import VerificationOutcome
from opencomplai_core.verification import _values_match, resolve_claim

# ---------------------------------------------------------------------------
# _values_match unit tests
# ---------------------------------------------------------------------------


def test_values_match_equal_strings() -> None:
    assert _values_match("foo", "foo") is True


def test_values_match_type_coercion() -> None:
    # str("42") == str(42)
    assert _values_match("42", 42) is True


def test_values_match_mismatch() -> None:
    assert _values_match("foo", "bar") is False


def test_values_match_none_expected_always_verified() -> None:
    # No assertion → treat as verified (adapter ran; no mismatch to report)
    assert _values_match(None, "anything") is True
    assert _values_match(None, None) is True


# ---------------------------------------------------------------------------
# resolve_claim — happy path (VERIFIED)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_claim_verified() -> None:
    claim = {
        "claim_ref": "test-claim-1",
        "source_ref": "offline://test",
        "expected_value": "customer support chatbot",
    }
    adapter = OfflineAdapter()
    task, proof, alert = await resolve_claim(claim, adapter)

    assert task.outcome == VerificationOutcome.VERIFIED
    assert proof is not None
    assert alert is None
    assert task.claim_ref == "test-claim-1"
    assert task.request_hash.startswith("sha256:")
    assert task.response_hash.startswith("sha256:")


@pytest.mark.asyncio
async def test_resolve_claim_no_expected_value_verifies() -> None:
    """Claim with no expected_value resolves VERIFIED (no assertion to fail)."""
    claim = {"claim_ref": "open-claim", "source_ref": "offline://test"}
    task, proof, alert = await resolve_claim(claim, OfflineAdapter())

    assert task.outcome == VerificationOutcome.VERIFIED
    assert proof is not None
    assert alert is None


# ---------------------------------------------------------------------------
# resolve_claim — mismatch path (ALERTED)
# ---------------------------------------------------------------------------


class _MismatchAdapter:
    """Always returns a value different from expected_value."""

    async def lookup(self, claim: dict) -> dict:
        return {"value": "WRONG_VALUE", "source": "test"}


@pytest.mark.asyncio
async def test_resolve_claim_alerted() -> None:
    claim = {
        "claim_ref": "test-claim-2",
        "source_ref": "offline://test",
        "expected_value": "correct-value",
        "metric": "accuracy",
        "threshold": 0.95,
        "severity": "high",
    }
    task, proof, alert = await resolve_claim(claim, _MismatchAdapter())

    assert task.outcome == VerificationOutcome.ALERTED
    assert proof is None
    assert alert is not None
    assert alert.metric == "accuracy"
    assert alert.linked_event_id == task.task_id


# ---------------------------------------------------------------------------
# Exactly-one-terminal-state invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exactly_one_terminal_state_verified() -> None:
    claim = {
        "claim_ref": "inv-1",
        "source_ref": "offline://test",
        "expected_value": "x",
    }
    task, proof, alert = await resolve_claim(claim, OfflineAdapter())

    # Exactly one of (proof, alert) is non-None
    assert (proof is None) != (alert is None)
    assert task.outcome in (VerificationOutcome.VERIFIED, VerificationOutcome.ALERTED)
    assert task.outcome != VerificationOutcome.PENDING


@pytest.mark.asyncio
async def test_exactly_one_terminal_state_alerted() -> None:
    claim = {
        "claim_ref": "inv-2",
        "source_ref": "offline://test",
        "expected_value": "x",
    }
    task, proof, alert = await resolve_claim(claim, _MismatchAdapter())

    assert (proof is None) != (alert is None)
    assert task.outcome != VerificationOutcome.PENDING


# ---------------------------------------------------------------------------
# Graph invariant: zero orphan claims (all submitted claims have terminal outcome)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_invariant_no_orphan_claims() -> None:
    """Submit N claims; all must have a terminal outcome (not PENDING)."""
    claims = [
        {
            "claim_ref": f"claim-{i}",
            "source_ref": "offline://test",
            "expected_value": str(i),
        }
        for i in range(10)
    ]
    adapter = OfflineAdapter()
    results = [await resolve_claim(c, adapter) for c in claims]

    for task, proof, alert in results:
        assert task.outcome != VerificationOutcome.PENDING, (
            f"Orphan claim: {task.claim_ref}"
        )
        assert (proof is None) != (alert is None), (
            "Both proof and alert are None or both set"
        )


# ---------------------------------------------------------------------------
# DEPENDENCY_UNAVAILABLE propagation
# ---------------------------------------------------------------------------


class _FailingAdapter:
    async def lookup(self, claim: dict) -> dict:
        raise RuntimeError("DEPENDENCY_UNAVAILABLE: external source offline")


@pytest.mark.asyncio
async def test_adapter_failure_raises_runtime_error() -> None:
    claim = {"claim_ref": "fail-claim", "source_ref": "http://external.example.com/api"}
    with pytest.raises(RuntimeError, match="DEPENDENCY_UNAVAILABLE"):
        await resolve_claim(claim, _FailingAdapter())
