"""
Tests for durable HITL/override/eval-cache persistence routes (PERSIST-RISK).

Exercises the same route-level pattern as test_tenant_isolation.py: a real
ASGI client against create_app(), SQLite-backed, confirming both the basic
persistence contract and tenant scoping.
"""

from __future__ import annotations

import os

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
    db_path = tmp_path / "test-hitl-persistence.db"
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


def _item(review_id: str = "rev_sha256:abc") -> dict:
    return {
        "review_id": review_id,
        "system_id": "sys-1",
        "commit_ref": "HEAD",
        "reason": "evaluator_fail",
        "state": "assigned",
        "payload_ref": "sha256:deadbeef",
        "context_ref": "sha256:ctxref",
        "reviewer_group": "compliance-reviewers",
        "assigned_to": "compliance-reviewers:member-0",
        "idempotency_key": review_id,
        "created_at": "2026-07-24T00:00:00+00:00",
        "expires_at": None,
        "decided_at": None,
        "linked_override_id": None,
    }


# ---------------------------------------------------------------------------
# Review items
# ---------------------------------------------------------------------------


async def test_upsert_and_get_review_item(client):
    resp = await client.put(
        "/v1/hitl/review-items", json=_item(), headers=_headers("tenant-a")
    )
    assert resp.status_code == 200
    assert resp.json()["item"]["review_id"] == "rev_sha256:abc"

    resp = await client.get(
        "/v1/hitl/review-items/rev_sha256:abc", headers=_headers("tenant-a")
    )
    assert resp.status_code == 200
    assert resp.json()["item"]["state"] == "assigned"


async def test_get_review_item_missing_returns_404(client):
    resp = await client.get(
        "/v1/hitl/review-items/does-not-exist", headers=_headers("tenant-a")
    )
    assert resp.status_code == 404


async def test_upsert_review_item_overwrites_existing_row(client):
    await client.put(
        "/v1/hitl/review-items", json=_item(), headers=_headers("tenant-a")
    )
    decided = _item()
    decided["state"] = "decided"
    decided["decided_at"] = "2026-07-24T01:00:00+00:00"
    decided["linked_override_id"] = "ovr_sha256:xyz"

    resp = await client.put(
        "/v1/hitl/review-items", json=decided, headers=_headers("tenant-a")
    )
    assert resp.status_code == 200

    resp = await client.get(
        "/v1/hitl/review-items/rev_sha256:abc", headers=_headers("tenant-a")
    )
    body = resp.json()["item"]
    assert body["state"] == "decided"
    assert body["linked_override_id"] == "ovr_sha256:xyz"


async def test_review_item_not_visible_cross_tenant(client):
    await client.put(
        "/v1/hitl/review-items", json=_item(), headers=_headers("tenant-a")
    )

    resp = await client.get(
        "/v1/hitl/review-items/rev_sha256:abc", headers=_headers("tenant-b")
    )
    assert resp.status_code == 404


async def test_cross_tenant_upsert_of_same_review_id_is_rejected(client):
    await client.put(
        "/v1/hitl/review-items", json=_item(), headers=_headers("tenant-a")
    )

    resp = await client.put(
        "/v1/hitl/review-items", json=_item(), headers=_headers("tenant-b")
    )
    assert resp.status_code == 404


async def test_list_review_items_scoped_to_tenant(client):
    await client.put(
        "/v1/hitl/review-items",
        json=_item("rev_sha256:one"),
        headers=_headers("tenant-a"),
    )
    await client.put(
        "/v1/hitl/review-items",
        json=_item("rev_sha256:two"),
        headers=_headers("tenant-b"),
    )

    resp = await client.get("/v1/hitl/review-items", headers=_headers("tenant-a"))
    ids = [i["review_id"] for i in resp.json()["items"]]
    assert ids == ["rev_sha256:one"]


async def test_list_review_items_filters_by_state(client):
    queued = _item("rev_sha256:queued")
    queued["state"] = "queued"
    decided = _item("rev_sha256:decided")
    decided["state"] = "decided"
    await client.put("/v1/hitl/review-items", json=queued, headers=_headers("tenant-a"))
    await client.put(
        "/v1/hitl/review-items", json=decided, headers=_headers("tenant-a")
    )

    resp = await client.get(
        "/v1/hitl/review-items",
        params={"state": "decided"},
        headers=_headers("tenant-a"),
    )
    ids = [i["review_id"] for i in resp.json()["items"]]
    assert ids == ["rev_sha256:decided"]


# ---------------------------------------------------------------------------
# Review contexts
# ---------------------------------------------------------------------------


async def test_store_and_get_review_context(client):
    resp = await client.post(
        "/v1/hitl/review-contexts",
        json={"context_ref": "sha256:ctx1", "context_json": {"reason": "manual"}},
        headers=_headers("tenant-a"),
    )
    assert resp.status_code == 201

    resp = await client.get(
        "/v1/hitl/review-contexts/sha256:ctx1", headers=_headers("tenant-a")
    )
    assert resp.status_code == 200
    assert resp.json()["context_json"] == {"reason": "manual"}


async def test_review_context_not_visible_cross_tenant(client):
    await client.post(
        "/v1/hitl/review-contexts",
        json={"context_ref": "sha256:ctx1", "context_json": {"reason": "manual"}},
        headers=_headers("tenant-a"),
    )
    resp = await client.get(
        "/v1/hitl/review-contexts/sha256:ctx1", headers=_headers("tenant-b")
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Accepted overrides (idempotency cache)
# ---------------------------------------------------------------------------


async def test_lookup_accepted_override_miss(client):
    resp = await client.get(
        "/v1/hitl/overrides/no-such-key", headers=_headers("tenant-a")
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "found": False,
        "payload_fingerprint": None,
        "response_json": None,
    }


async def test_store_and_lookup_accepted_override(client):
    resp = await client.post(
        "/v1/hitl/overrides",
        json={
            "idempotency_key": "idem-1",
            "payload_fingerprint": "fp-1",
            "response_json": {"override_id": "ovr_sha256:abc", "status": "accepted"},
        },
        headers=_headers("tenant-a"),
    )
    assert resp.status_code == 201

    resp = await client.get("/v1/hitl/overrides/idem-1", headers=_headers("tenant-a"))
    body = resp.json()
    assert body["found"] is True
    assert body["payload_fingerprint"] == "fp-1"
    assert body["response_json"]["override_id"] == "ovr_sha256:abc"


async def test_accepted_override_not_visible_cross_tenant(client):
    await client.post(
        "/v1/hitl/overrides",
        json={
            "idempotency_key": "idem-1",
            "payload_fingerprint": "fp-1",
            "response_json": {"status": "accepted"},
        },
        headers=_headers("tenant-a"),
    )
    resp = await client.get("/v1/hitl/overrides/idem-1", headers=_headers("tenant-b"))
    assert resp.json()["found"] is False


async def test_store_accepted_override_is_idempotent_first_write_wins(client):
    await client.post(
        "/v1/hitl/overrides",
        json={
            "idempotency_key": "idem-1",
            "payload_fingerprint": "fp-1",
            "response_json": {"status": "accepted"},
        },
        headers=_headers("tenant-a"),
    )
    await client.post(
        "/v1/hitl/overrides",
        json={
            "idempotency_key": "idem-1",
            "payload_fingerprint": "fp-2",
            "response_json": {"status": "pending_second_approval"},
        },
        headers=_headers("tenant-a"),
    )

    resp = await client.get("/v1/hitl/overrides/idem-1", headers=_headers("tenant-a"))
    assert resp.json()["payload_fingerprint"] == "fp-1"


# ---------------------------------------------------------------------------
# Completed evals cache
# ---------------------------------------------------------------------------


async def test_lookup_completed_eval_miss(client):
    resp = await client.get("/v1/evals/cache/no-such-run", headers=_headers("tenant-a"))
    assert resp.json() == {"found": False, "result_json": None}


async def test_store_and_lookup_completed_eval(client):
    resp = await client.post(
        "/v1/evals/cache",
        json={"eval_run_id": "run-1", "result_json": {"overall_outcome": "pass"}},
        headers=_headers("tenant-a"),
    )
    assert resp.status_code == 201

    resp = await client.get("/v1/evals/cache/run-1", headers=_headers("tenant-a"))
    body = resp.json()
    assert body["found"] is True
    assert body["result_json"] == {"overall_outcome": "pass"}


async def test_completed_eval_not_visible_cross_tenant(client):
    await client.post(
        "/v1/evals/cache",
        json={"eval_run_id": "run-1", "result_json": {"overall_outcome": "pass"}},
        headers=_headers("tenant-a"),
    )
    resp = await client.get("/v1/evals/cache/run-1", headers=_headers("tenant-b"))
    assert resp.json()["found"] is False
