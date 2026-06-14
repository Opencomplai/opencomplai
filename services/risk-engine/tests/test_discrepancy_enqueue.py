"""Manifest discrepancy HITL enqueue tests."""

from opencomplai_core.models import ReviewReason
from opencomplai_risk_engine.review_queue import (
    _REVIEW_CONTEXTS,
    _REVIEW_ITEMS,
    enqueue_manifest_discrepancy,
    get_review_context,
)


def setup_function():
    _REVIEW_ITEMS.clear()
    _REVIEW_CONTEXTS.clear()


def test_major_discrepancy_enqueues_manifest_discrepancy():
    item = enqueue_manifest_discrepancy(
        tenant_id="t1",
        system_id="sys-1",
        commit_ref="HEAD",
        payload_ref="sha256:report123",
        discrepancies=["biometric"],
        severity="major",
        locations=["src/face.py:42"],
        detector_ids=["DET_BIOMETRIC_V1"],
    )
    assert item.reason == ReviewReason.MANIFEST_DISCREPANCY
    ctx = get_review_context(item.context_ref)
    assert ctx is not None
    assert ctx.aggregate_counts["discrepancy_count"] == 1
    assert "import face_recognition" not in ctx.model_dump_json()


def test_enqueue_idempotent_on_retry():
    kwargs = {
        "tenant_id": "t1",
        "system_id": "sys-1",
        "commit_ref": "HEAD",
        "payload_ref": "sha256:report123",
        "discrepancies": ["biometric"],
        "severity": "critical",
        "locations": ["src/face.py:42"],
    }
    a = enqueue_manifest_discrepancy(**kwargs)
    b = enqueue_manifest_discrepancy(**kwargs)
    assert a.review_id == b.review_id
