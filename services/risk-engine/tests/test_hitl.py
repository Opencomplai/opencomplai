"""Tests for the HITL orchestrator (REQ-HITL-001, PRD Section 8)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_risk_engine import main as risk_main
from opencomplai_risk_engine.main import app


@pytest.fixture(autouse=True)
def _vault_ok_and_clear_cache():
    risk_main._ACCEPTED_OVERRIDES.clear()
    with patch(
        "opencomplai_risk_engine.main._record_hitl_event",
        new_callable=AsyncMock,
        return_value="evt_mock_vault",
    ):
        yield
    risk_main._ACCEPTED_OVERRIDES.clear()


@pytest.mark.asyncio
async def test_override_empty_rationale_returns_422():
    """REQ-HITL-001: override without rationale must be rejected."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/hitl/overrides",
            json={
                "case_id": "c1",
                "actor_id": "u1",
                "rationale": "",
                "decision": "approved",
            },
        )
    assert r.status_code == 422
    assert r.json()["detail"]["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_override_whitespace_only_rationale_returns_422():
    """Whitespace-only rationale must also be rejected."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/hitl/overrides",
            json={
                "case_id": "c1",
                "actor_id": "u1",
                "rationale": "   ",
                "decision": "approved",
            },
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_override_valid_rationale_returns_201():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/hitl/overrides",
            json={
                "case_id": "c1",
                "actor_id": "u1",
                "rationale": "Reviewed by compliance officer — false positive confirmed.",
                "decision": "approved",
            },
        )
    assert r.status_code == 201
    data = r.json()
    assert "override_id" in data
    assert data["rationale_hash"].startswith("sha256:")
    assert "rationale" not in data  # plaintext must not be returned
    assert data["vault_event_id"] == "evt_mock_vault"


@pytest.mark.asyncio
async def test_override_dual_approval_pending():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/hitl/overrides",
            json={
                "case_id": "biometric-case-1",
                "actor_id": "u1",
                "rationale": "First approval for biometric path.",
                "decision": "approved",
                "requires_dual_approval": True,
            },
        )
    assert r.status_code == 201
    assert r.json()["status"] == "pending_second_approval"


@pytest.mark.asyncio
async def test_override_rationale_hash_is_deterministic():
    """Same rationale must always produce the same hash."""
    payload = {
        "case_id": "c1",
        "actor_id": "u1",
        "rationale": "Consistent rationale text.",
        "decision": "approved",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r1 = await client.post("/v1/hitl/overrides", json=payload)
        r2 = await client.post("/v1/hitl/overrides", json=payload)
    assert r1.json()["rationale_hash"] == r2.json()["rationale_hash"]
