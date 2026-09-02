"""POST /v1/evals/run endpoint tests."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_core.service_auth import mint_service_token
from opencomplai_risk_engine.main import app


@pytest.fixture(autouse=True)
def _vault_and_cache(fake_vault):
    with patch(
        "opencomplai_risk_engine.main._record_hitl_event",
        new_callable=AsyncMock,
        return_value="evt_eval",
    ):
        yield
    fake_vault.clear()


@pytest.mark.asyncio
async def test_evals_run_happy_path():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {mint_service_token('test-caller', os.environ['INTERNAL_SERVICE_TOKEN_SECRET'])}"
        },
    ) as client:
        r = await client.post(
            "/v1/evals/run",
            json={
                "system_id": "sys-1",
                "commit_ref": "HEAD",
                "sample_set": {
                    "eval_set_id": "set-1",
                    "system_id": "sys-1",
                    "commit_ref": "HEAD",
                    "outputs": ["A safe response."],
                },
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["overall_outcome"] == "pass"
    assert "eval_run_id" in data


@pytest.mark.asyncio
async def test_evals_run_422_on_mismatched_system_id():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {mint_service_token('test-caller', os.environ['INTERNAL_SERVICE_TOKEN_SECRET'])}"
        },
    ) as client:
        r = await client.post(
            "/v1/evals/run",
            json={
                "system_id": "sys-1",
                "commit_ref": "HEAD",
                "sample_set": {
                    "eval_set_id": "set-1",
                    "system_id": "other",
                    "commit_ref": "HEAD",
                    "outputs": ["x"],
                },
            },
        )
    assert r.status_code == 422
