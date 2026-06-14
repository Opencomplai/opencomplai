"""Fail-closed HITL ledger writes (Workstream B.4)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_risk_engine import main as risk_main
from opencomplai_risk_engine.main import app


@pytest.fixture(autouse=True)
def _clear_idempotency_cache():
    risk_main._ACCEPTED_OVERRIDES.clear()
    yield
    risk_main._ACCEPTED_OVERRIDES.clear()


@pytest.mark.asyncio
async def test_override_vault_failure_returns_503_not_201():
    """When the vault is unavailable, submit_override must not return 201."""
    with patch(
        "opencomplai_risk_engine.main._record_hitl_event",
        new_callable=AsyncMock,
        return_value=None,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/v1/hitl/overrides",
                json={
                    "case_id": "c1",
                    "actor_id": "u1",
                    "rationale": "Reviewed and approved.",
                    "decision": "approved",
                },
            )
    assert r.status_code == 503
    assert r.json()["detail"]["error_code"] == "AUDIT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_override_succeeds_only_when_vault_writes():
    with patch(
        "opencomplai_risk_engine.main._record_hitl_event",
        new_callable=AsyncMock,
        return_value="evt_test_001",
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/v1/hitl/overrides",
                json={
                    "case_id": "c1",
                    "actor_id": "u1",
                    "rationale": "Reviewed and approved.",
                    "decision": "approved",
                },
            )
    assert r.status_code == 201
    assert r.json()["vault_event_id"] == "evt_test_001"


@pytest.mark.asyncio
async def test_override_idempotency_retry_returns_same_response():
    payload = {
        "case_id": "c1",
        "actor_id": "u1",
        "rationale": "Same rationale.",
        "decision": "approved",
        "idempotency_key": "idem-abc",
    }
    with patch(
        "opencomplai_risk_engine.main._record_hitl_event",
        new_callable=AsyncMock,
        return_value="evt_idem",
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = await client.post("/v1/hitl/overrides", json=payload)
            r2 = await client.post("/v1/hitl/overrides", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["override_id"] == r2.json()["override_id"]


@pytest.mark.asyncio
async def test_override_idempotency_conflict_returns_409():
    with patch(
        "opencomplai_risk_engine.main._record_hitl_event",
        new_callable=AsyncMock,
        return_value="evt_conflict",
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/v1/hitl/overrides",
                json={
                    "case_id": "c1",
                    "actor_id": "u1",
                    "rationale": "First rationale.",
                    "decision": "approved",
                    "idempotency_key": "shared-key",
                },
            )
            r = await client.post(
                "/v1/hitl/overrides",
                json={
                    "case_id": "c1",
                    "actor_id": "u1",
                    "rationale": "Different rationale.",
                    "decision": "rejected",
                    "idempotency_key": "shared-key",
                },
            )
    assert r.status_code == 409
    assert r.json()["detail"]["error_code"] == "IDEMPOTENCY_CONFLICT"
