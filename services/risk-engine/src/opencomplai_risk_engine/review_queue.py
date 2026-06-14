"""
HITL reviewer queue — enqueue, route, and list review items (Workstream B).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta

from opencomplai_core.models import (
    RedactedReviewContext,
    ReviewItem,
    ReviewItemState,
    ReviewReason,
)

TENANT_ID = os.environ.get("TENANT_ID", "default")
REVIEWER_GROUPS: dict[str, str] = json.loads(
    os.environ.get(
        "REVIEWER_GROUP_MAP",
        '{"default": "compliance-reviewers"}',
    )
)
_GROUP_ASSIGN_INDEX: dict[str, int] = {}

# In-process store; evidence-vault persistence mirrors bias_alerts pattern in production.
_REVIEW_ITEMS: dict[str, ReviewItem] = {}
_REVIEW_CONTEXTS: dict[str, RedactedReviewContext] = {}


def derive_review_id(
    tenant_id: str,
    system_id: str,
    commit_ref: str,
    reason: ReviewReason,
    payload_ref: str,
) -> str:
    raw = "|".join([tenant_id, system_id, commit_ref, reason.value, payload_ref])
    return f"rev_sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def build_redacted_context(
    review_id: str,
    reason: ReviewReason,
    detector_ids: list[str] | None = None,
    aggregate_counts: dict[str, int] | None = None,
    evidence_hashes: list[str] | None = None,
) -> RedactedReviewContext:
    return RedactedReviewContext(
        review_id=review_id,
        reason=reason,
        detector_ids=detector_ids or [],
        masked_excerpts=[],
        aggregate_counts=aggregate_counts or {},
        evidence_hashes=evidence_hashes or [],
    )


def context_ref(context: RedactedReviewContext) -> str:
    canonical = context.model_dump_json()
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def enqueue_review(
    *,
    tenant_id: str,
    system_id: str,
    commit_ref: str,
    reason: ReviewReason,
    payload_ref: str,
    context: RedactedReviewContext,
    idempotency_key: str | None = None,
    expires_in_hours: int = 72,
) -> ReviewItem:
    review_id = derive_review_id(tenant_id, system_id, commit_ref, reason, payload_ref)
    if review_id in _REVIEW_ITEMS:
        return _REVIEW_ITEMS[review_id]

    ctx_ref = context_ref(context)
    _REVIEW_CONTEXTS[ctx_ref] = context

    group = REVIEWER_GROUPS.get(system_id, REVIEWER_GROUPS.get("default", "default"))
    idx = _GROUP_ASSIGN_INDEX.get(group, 0)
    _GROUP_ASSIGN_INDEX[group] = idx + 1
    assigned_to = f"{group}:member-{idx % 3}"

    now = datetime.now(UTC)
    item = ReviewItem(
        review_id=review_id,
        tenant_id=tenant_id,
        system_id=system_id,
        commit_ref=commit_ref,
        reason=reason,
        state=ReviewItemState.ASSIGNED,
        payload_ref=payload_ref,
        context_ref=ctx_ref,
        reviewer_group=group,
        assigned_to=assigned_to,
        idempotency_key=idempotency_key or review_id,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=expires_in_hours)).isoformat(),
    )
    _REVIEW_ITEMS[review_id] = item
    return item


def list_review_items(
    tenant_id: str,
    *,
    state: ReviewItemState | None = None,
    assigned_to: str | None = None,
) -> list[ReviewItem]:
    items = [i for i in _REVIEW_ITEMS.values() if i.tenant_id == tenant_id]
    if state is not None:
        items = [i for i in items if i.state == state]
    if assigned_to is not None:
        items = [i for i in items if i.assigned_to == assigned_to]
    return sorted(items, key=lambda x: x.created_at)


def get_review_item(tenant_id: str, review_id: str) -> ReviewItem | None:
    item = _REVIEW_ITEMS.get(review_id)
    if item is None or item.tenant_id != tenant_id:
        return None
    return item


def get_review_context(context_ref_value: str) -> RedactedReviewContext | None:
    return _REVIEW_CONTEXTS.get(context_ref_value)


def assign_review(tenant_id: str, review_id: str, reviewer_id: str) -> ReviewItem:
    item = get_review_item(tenant_id, review_id)
    if item is None:
        raise KeyError(review_id)
    updated = item.model_copy(
        update={
            "state": ReviewItemState.ASSIGNED,
            "assigned_to": reviewer_id,
        }
    )
    _REVIEW_ITEMS[review_id] = updated
    return updated


def mark_decided(tenant_id: str, review_id: str, override_id: str) -> ReviewItem:
    item = get_review_item(tenant_id, review_id)
    if item is None:
        raise KeyError(review_id)
    updated = item.model_copy(
        update={
            "state": ReviewItemState.DECIDED,
            "decided_at": datetime.now(UTC).isoformat(),
            "linked_override_id": override_id,
        }
    )
    _REVIEW_ITEMS[review_id] = updated
    return updated


def enqueue_manifest_discrepancy(
    *,
    tenant_id: str,
    system_id: str,
    commit_ref: str,
    payload_ref: str,
    discrepancies: list[str],
    severity: str,
    locations: list[str],
    detector_ids: list[str] | None = None,
) -> ReviewItem:
    """Enqueue a manifest/code declaration discrepancy for human reconciliation."""
    context = build_redacted_context(
        review_id="pending",
        reason=ReviewReason.MANIFEST_DISCREPANCY,
        detector_ids=detector_ids or [],
        aggregate_counts={
            "discrepancy_count": len(discrepancies),
            "location_count": len(locations),
            "severity_rank": 2 if severity == "major" else 3,
        },
        evidence_hashes=[payload_ref],
    )
    context = context.model_copy(update={"review_id": payload_ref[:32]})
    return enqueue_review(
        tenant_id=tenant_id,
        system_id=system_id,
        commit_ref=commit_ref,
        reason=ReviewReason.MANIFEST_DISCREPANCY,
        payload_ref=payload_ref,
        context=context,
    )
