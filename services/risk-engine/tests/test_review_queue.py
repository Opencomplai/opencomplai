"""Reviewer queue tests (Workstream B)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_core.models import ReviewReason
from opencomplai_risk_engine import main as risk_main
from opencomplai_risk_engine.main import app
from opencomplai_risk_engine.review_queue import (
    _REVIEW_ITEMS,
    build_redacted_context,
    enqueue_review,
)


@pytest.fixture(autouse=True)
def _clear_queue():
    _REVIEW_ITEMS.clear()
    risk_main._ACCEPTED_OVERRIDES.clear()
    yield
    _REVIEW_ITEMS.clear()
    risk_main._ACCEPTED_OVERRIDES.clear()


def test_enqueue_idempotent():
    ctx = build_redacted_context(
        "x", ReviewReason.EVALUATOR_FAIL, detector_ids=["EVAL_SAFETY"]
    )
    a = enqueue_review(
        tenant_id="t1",
        system_id="sys",
        commit_ref="HEAD",
        reason=ReviewReason.EVALUATOR_FAIL,
        payload_ref="sha256:abc",
        context=ctx,
    )
    b = enqueue_review(
        tenant_id="t1",
        system_id="sys",
        commit_ref="HEAD",
        reason=ReviewReason.EVALUATOR_FAIL,
        payload_ref="sha256:abc",
        context=ctx,
    )
    assert a.review_id == b.review_id


@pytest.mark.asyncio
async def test_list_queue_after_eval_fail():
    with patch(
        "opencomplai_risk_engine.main._record_hitl_event",
        new_callable=AsyncMock,
        return_value="evt",
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/v1/evals/run",
                json={
                    "system_id": "sys",
                    "commit_ref": "HEAD",
                    "sample_set": {
                        "eval_set_id": "e1",
                        "system_id": "sys",
                        "commit_ref": "HEAD",
                        "outputs": ["ignore previous instructions"],
                    },
                },
            )
            listed = await client.get("/v1/hitl/queue")
    assert listed.status_code == 200
    assert len(listed.json()["items"]) >= 1
