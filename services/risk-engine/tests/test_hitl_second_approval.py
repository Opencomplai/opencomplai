"""Second-approval completion of dual-control overrides (REQ-HITL-001)."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_core.service_auth import mint_service_token
from opencomplai_risk_engine.main import app

RATIONALE_2 = "second reviewer rationale"


@pytest.fixture
def record(fake_vault):
    with patch(
        "opencomplai_risk_engine.main._record_hitl_event",
        new_callable=AsyncMock,
        return_value="evt_mock_vault",
    ) as m:
        yield m
    fake_vault.clear()


def _client():
    token = mint_service_token(
        "test-caller", os.environ["INTERNAL_SERVICE_TOKEN_SECRET"]
    )
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


async def _submit(client, dual=True, actor="alice"):
    r = await client.post(
        "/v1/hitl/overrides",
        json={
            "case_id": "c1",
            "actor_id": actor,
            "rationale": "first rationale",
            "decision": "approved",
            "requires_dual_approval": dual,
        },
    )
    assert r.status_code == 201
    return r.json()


def _body(first, actor="bob", **kw):
    b = {
        "actor_id": actor,
        "rationale": RATIONALE_2,
        "rationale_hash": first["rationale_hash"],
    }
    b.update(kw)
    return b


def _url(first):
    return f"/v1/hitl/overrides/{first['override_id']}/second-approval"


@pytest.mark.asyncio
async def test_pending_record_written_only_when_dual_requested(record, fake_vault):
    async with _client() as c:
        single = await _submit(c, dual=False)
        assert f"dual:{single['override_id']}" not in fake_vault.accepted_overrides
        dual = await _submit(c, dual=True, actor="carol")
    assert dual["status"] == "pending_second_approval"
    assert f"dual:{dual['override_id']}" in fake_vault.accepted_overrides


@pytest.mark.asyncio
@pytest.mark.parametrize("actor", ["alice", "  ALICE "])
async def test_same_actor_rejected_403(record, actor):
    async with _client() as c:
        first = await _submit(c)
        record.reset_mock()
        r = await c.post(_url(first), json=_body(first, actor=actor))
    assert r.status_code == 403
    assert r.json()["detail"]["error_code"] == "POLICY_DENIED"
    record.assert_not_called()


@pytest.mark.asyncio
async def test_distinct_actor_completes_override_and_writes_event(record):
    async with _client() as c:
        first = await _submit(c)
        record.reset_mock()
        r = await c.post(_url(first), json=_body(first))
    assert r.status_code == 201
    assert r.json()["status"] == "accepted"
    record.assert_awaited_once()
    args = record.await_args
    assert args.args[0] == "override_second_approved"
    payload = args.args[1]
    assert payload["first_rationale_hash"] == first["rationale_hash"]
    assert payload["second_rationale_hash"] == r.json()["rationale_hash"]
    assert payload["first_actor_id"] == "alice"
    assert args.args[2] == "bob"
    assert RATIONALE_2 not in str(args)


@pytest.mark.asyncio
async def test_missing_or_wrong_rationale_hash_rejected(record):
    async with _client() as c:
        first = await _submit(c)
        wrong = await c.post(
            _url(first), json=_body(first, rationale_hash="sha256:bad")
        )
        b = _body(first)
        del b["rationale_hash"]
        missing = await c.post(_url(first), json=b)
    assert wrong.status_code == 409
    assert wrong.json()["detail"]["error_code"] == "RATIONALE_HASH_MISMATCH"
    assert missing.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("rationale", ["", "   "])
async def test_empty_second_rationale_422(record, rationale):
    async with _client() as c:
        first = await _submit(c)
        r = await c.post(_url(first), json=_body(first, rationale=rationale))
    assert r.status_code == 422
    assert r.json()["detail"]["error_code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_unknown_override_404(record):
    async with _client() as c:
        r = await c.post(
            "/v1/hitl/overrides/nope/second-approval",
            json={"actor_id": "bob", "rationale": "x", "rationale_hash": "sha256:x"},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_second_completion_returns_409(record):
    async with _client() as c:
        first = await _submit(c)
        assert (await c.post(_url(first), json=_body(first))).status_code == 201
        r = await c.post(_url(first), json=_body(first, actor="dave"))
    assert r.status_code == 409
    assert r.json()["detail"]["error_code"] == "ALREADY_COMPLETED"


@pytest.mark.asyncio
async def test_second_approval_ledger_failure_returns_503_and_stays_pending(
    record, fake_vault
):
    async with _client() as c:
        first = await _submit(c)
        record.return_value = None
        r = await c.post(_url(first), json=_body(first))
        assert r.status_code == 503
        assert r.json()["detail"]["error_code"] == "AUDIT_UNAVAILABLE"
        assert f"dual-done:{first['override_id']}" not in fake_vault.accepted_overrides
        record.return_value = "evt_ok"
        r = await c.post(_url(first), json=_body(first))
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_second_rejection_decision_sets_status_rejected(record):
    async with _client() as c:
        first = await _submit(c)
        r = await c.post(_url(first), json=_body(first, decision="rejected"))
    assert r.status_code == 201
    assert r.json()["status"] == "rejected"
