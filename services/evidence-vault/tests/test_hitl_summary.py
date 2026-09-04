"""
Tests for GET /v1/hitl/review-items/summary (DASH-SUMMARY).

The summary is what render-api serves to the dashboard review-queue widget,
replacing a hardcoded all-zero stub. The tests below pin the two things a
zeroed stub would also have satisfied — that the figures move with real data,
and that they are tenant-scoped — plus the route-ordering and bad-data cases
that would silently reintroduce a zero.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opencomplai_core.service_auth import mint_service_token
from opencomplai_evidence_vault.badges import _BadgeBase
from opencomplai_evidence_vault.bias_alerts import _Base as _BiasBase
from opencomplai_evidence_vault.cas import CASStore
from opencomplai_evidence_vault.hitl import _Base as _HitlBase
from opencomplai_evidence_vault.main import create_app
from opencomplai_evidence_vault.models import Base as _LedgerBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def client(tmp_path, _service_token_secret):
    db_path = tmp_path / "test-hitl-summary.db"
    cas_path = tmp_path / "cas"
    cas_path.mkdir()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_LedgerBase.metadata.create_all)
        await conn.run_sync(_BiasBase.metadata.create_all)
        await conn.run_sync(_BadgeBase.metadata.create_all)
        await conn.run_sync(_HitlBase.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()
    app.state.engine = engine
    app.state.sessionmaker = session_factory
    app.state.cas = CASStore(str(cas_path))

    token = mint_service_token(
        "test-caller", os.environ["INTERNAL_SERVICE_TOKEN_SECRET"]
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac

    await engine.dispose()


def _headers(tenant_id: str) -> dict[str, str]:
    return {"X-Tenant-Id": tenant_id}


_CREATED = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)


def _item(
    review_id: str,
    *,
    state: str = "queued",
    reason: str = "evaluator_fail",
    assigned_to: str | None = None,
    decided_after_hours: float | None = None,
    created_at: str | None = None,
    decided_at: str | None = None,
) -> dict:
    if decided_at is None and decided_after_hours is not None:
        decided_at = (_CREATED + timedelta(hours=decided_after_hours)).isoformat()
    return {
        "review_id": review_id,
        "system_id": "sys-1",
        "commit_ref": "HEAD",
        "reason": reason,
        "state": state,
        "payload_ref": "sha256:deadbeef",
        "context_ref": "sha256:ctxref",
        "reviewer_group": "compliance-reviewers",
        "assigned_to": assigned_to,
        "idempotency_key": f"idem-{review_id}",
        "created_at": created_at if created_at is not None else _CREATED.isoformat(),
        "expires_at": None,
        "decided_at": decided_at,
        "linked_override_id": None,
    }


async def _put(client: AsyncClient, tenant_id: str, item: dict) -> None:
    resp = await client.put(
        "/v1/hitl/review-items", json=item, headers=_headers(tenant_id)
    )
    assert resp.status_code == 200, resp.text


async def _summary(client: AsyncClient, tenant_id: str) -> dict:
    resp = await client.get(
        "/v1/hitl/review-items/summary", headers=_headers(tenant_id)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_empty_queue_summarises_to_zero(client):
    assert await _summary(client, "tenant-a") == {
        "pending_count": 0,
        "assigned_count": 0,
        "mean_time_to_decision_hours": None,
        "by_reason": {},
    }


async def test_counts_and_reasons_reflect_real_items(client):
    await _put(
        client, "tenant-a", _item("rev-1", state="queued", reason="evaluator_fail")
    )
    await _put(
        client, "tenant-a", _item("rev-2", state="queued", reason="policy_block")
    )
    await _put(
        client,
        "tenant-a",
        _item("rev-3", state="assigned", reason="policy_block", assigned_to="alice"),
    )

    summary = await _summary(client, "tenant-a")

    assert summary["pending_count"] == 3
    assert summary["assigned_count"] == 1
    assert summary["by_reason"] == {"evaluator_fail": 1, "policy_block": 2}


async def test_assigned_is_a_subset_of_pending_not_a_disjoint_bucket(client):
    await _put(
        client,
        "tenant-a",
        _item("rev-1", state="assigned", assigned_to="alice"),
    )

    summary = await _summary(client, "tenant-a")

    # An assigned item is still awaiting a decision, so it counts in both.
    assert summary["pending_count"] == 1
    assert summary["assigned_count"] == 1


async def test_decided_and_expired_items_are_not_pending(client):
    await _put(
        client, "tenant-a", _item("rev-1", state="decided", decided_after_hours=2)
    )
    await _put(client, "tenant-a", _item("rev-2", state="expired"))
    await _put(client, "tenant-a", _item("rev-3", state="queued"))

    summary = await _summary(client, "tenant-a")

    assert summary["pending_count"] == 1
    assert summary["by_reason"] == {"evaluator_fail": 1}


async def test_mean_time_to_decision_averages_decided_items(client):
    await _put(
        client, "tenant-a", _item("rev-1", state="decided", decided_after_hours=2)
    )
    await _put(
        client, "tenant-a", _item("rev-2", state="decided", decided_after_hours=4)
    )
    # A still-pending item must not drag the mean toward zero.
    await _put(client, "tenant-a", _item("rev-3", state="queued"))

    summary = await _summary(client, "tenant-a")

    assert summary["mean_time_to_decision_hours"] == 3.0


async def test_mean_time_is_none_when_nothing_has_been_decided(client):
    await _put(client, "tenant-a", _item("rev-1", state="queued"))

    assert (await _summary(client, "tenant-a"))["mean_time_to_decision_hours"] is None


async def test_unparseable_or_inverted_timestamps_are_skipped_not_fatal(client):
    await _put(
        client, "tenant-a", _item("rev-1", state="decided", decided_after_hours=2)
    )
    await _put(
        client,
        "tenant-a",
        _item(
            "rev-2",
            state="decided",
            created_at="not-a-timestamp",
            decided_at="also-not",
        ),
    )
    await _put(
        client,
        "tenant-a",
        # decided before created — impossible, so it is discarded rather than
        # pulling the mean negative.
        _item("rev-3", state="decided", decided_after_hours=-5),
    )

    summary = await _summary(client, "tenant-a")

    assert summary["mean_time_to_decision_hours"] == 2.0


async def test_mixed_naive_and_aware_timestamps_are_skipped_not_fatal(client):
    """
    Subtracting a naive datetime from an aware one raises TypeError, not
    ValueError — a distinct escape route from the parse guard, and a 500 if
    it is not caught.
    """
    await _put(
        client, "tenant-a", _item("rev-1", state="decided", decided_after_hours=2)
    )
    await _put(
        client,
        "tenant-a",
        _item(
            "rev-2",
            state="decided",
            created_at="2026-07-01T12:00:00",  # naive
            decided_at="2026-07-01T15:00:00+00:00",  # aware
        ),
    )

    summary = await _summary(client, "tenant-a")

    assert summary["mean_time_to_decision_hours"] == 2.0


async def test_summary_is_tenant_scoped(client):
    await _put(client, "tenant-a", _item("rev-a1", state="queued"))
    await _put(
        client, "tenant-a", _item("rev-a2", state="assigned", assigned_to="alice")
    )
    await _put(
        client, "tenant-b", _item("rev-b1", state="queued", reason="policy_block")
    )

    a = await _summary(client, "tenant-a")
    b = await _summary(client, "tenant-b")

    assert a["pending_count"] == 2
    assert a["assigned_count"] == 1
    assert a["by_reason"] == {"evaluator_fail": 2}

    assert b["pending_count"] == 1
    assert b["assigned_count"] == 0
    assert b["by_reason"] == {"policy_block": 1}


async def test_summary_route_is_not_shadowed_by_the_review_id_route(client):
    """
    /v1/hitl/review-items/{review_id} is declared after /summary. If that
    order is ever reversed, "summary" is parsed as a review_id and this
    returns 404 instead of the aggregate.
    """
    resp = await client.get(
        "/v1/hitl/review-items/summary", headers=_headers("tenant-a")
    )

    assert resp.status_code == 200
    assert "pending_count" in resp.json()


async def test_summary_requires_a_service_token(client):
    resp = await client.get(
        "/v1/hitl/review-items/summary",
        headers={**_headers("tenant-a"), "Authorization": "Bearer not-a-real-token"},
    )

    assert resp.status_code == 401
