"""Integration tests for the risk engine service."""

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_risk_engine.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_classify_minimal_risk():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/risk/classify",
            json={
                "system_id": "test",
                "intended_purpose": "customer support chatbot",
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["risk_class"] == "minimal"
    assert data["profiling_detected"] is False
    assert data["trap_detected"] is False


@pytest.mark.asyncio
async def test_classify_high_risk_employment():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/risk/classify",
            json={
                "system_id": "test",
                "intended_purpose": "employment screening",
            },
        )
    assert r.status_code == 200
    assert r.json()["risk_class"] == "high"


@pytest.mark.asyncio
async def test_profiling_detection():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/risk/classify",
            json={
                "system_id": "test",
                "intended_purpose": "customer support chatbot",
                "features": ["profiling"],
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["profiling_detected"] is True
    assert data["risk_class"] == "high"


@pytest.mark.asyncio
async def test_modification_trap():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/risk/classify",
            json={
                "system_id": "test",
                "intended_purpose": "customer support chatbot",
                "change_context": "model_retrain",
            },
        )
    assert r.status_code == 200
    assert r.json()["trap_detected"] is True


@pytest.mark.asyncio
async def test_hitl_override_requires_rationale():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/v1/hitl/overrides",
            json={
                "case_id": "case-1",
                "actor_id": "user-1",
                "rationale": "",
                "decision": "approved",
            },
        )
    assert r.status_code == 422
