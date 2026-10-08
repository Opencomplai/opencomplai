"""An agent_action event carrying a CAS content hash appends and verifies (SU-28a2)."""

from __future__ import annotations

import base64
import hashlib
import json
import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opencomplai_core.agent_log_verify import (
    entry_bytes,
    entry_content_hash,
    vault_event_payload,
)
from opencomplai_core.service_auth import mint_service_token
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain
from opencomplai_evidence_vault.badges import _BadgeBase
from opencomplai_evidence_vault.bias_alerts import _Base as _BiasBase
from opencomplai_evidence_vault.cas import CASStore
from opencomplai_evidence_vault.main import create_app
from opencomplai_evidence_vault.models import Base as _LedgerBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def client(tmp_path, _service_token_secret):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'agent.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(_LedgerBase.metadata.create_all)
        await conn.run_sync(_BiasBase.metadata.create_all)
        await conn.run_sync(_BadgeBase.metadata.create_all)
    (tmp_path / "cas").mkdir()

    app = create_app()
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.cas = CASStore(str(tmp_path / "cas"))

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


def _entry(tmp_path) -> dict:
    log = SignedLog(tmp_path / "agent-log.jsonl", SigningDomain.AGENT_LOG)
    return log.append(
        {
            "agent_id": "a1",
            "mandate_ref": None,
            "intent": "look up a policy",
            "tool": "search",
            "input_hash": "sha256:" + "11" * 32,
            "outcome": "success",
            "outside_mandate": False,
        },
        ts="2026-03-01T10:00:00+00:00",
    )


async def _append(client, entry: dict) -> tuple[str, dict, dict]:
    raw = entry_bytes(entry)
    stored = await client.post(
        "/v1/evidence/objects",
        json={"content_base64": base64.b64encode(raw).decode(), "source": "agent-log"},
    )
    assert stored.status_code == 201, stored.text
    content_hash = stored.json()["content_hash"]
    payload = vault_event_payload("sys-1", entry, content_hash, ())
    resp = await client.post(
        "/v1/evidence/events", json={"event_type": "agent_action", "payload": payload}
    )
    assert resp.status_code == 201, resp.text
    return content_hash, payload, resp.json()


async def test_agent_action_event_with_cas_hash_appends_and_chain_verifies(
    client, tmp_path
):
    entry = _entry(tmp_path)
    before = (await client.get("/v1/evidence/ledger-root")).json()["ledger_root_hash"]
    content_hash, _, _ = await _append(client, entry)
    assert content_hash == entry_content_hash(entry)

    after = (await client.get("/v1/evidence/ledger-root")).json()["ledger_root_hash"]
    assert after != before
    assert (await client.get("/v1/evidence/verify-chain")).json() == {"valid": True}

    got = await client.get(f"/v1/evidence/objects/{content_hash}")
    assert got.status_code == 200
    assert base64.b64decode(got.json()["content_base64"]) == entry_bytes(entry)


async def test_agent_action_payload_hash_is_stable(client, tmp_path):
    _, payload, body = await _append(client, _entry(tmp_path))
    expected = (
        "sha256:"
        + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    )
    assert body["payload_hash"] == expected
