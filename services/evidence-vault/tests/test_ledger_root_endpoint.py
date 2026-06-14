"""Tests for the ledger-root endpoint (closes Gap #4 from the self-audit)."""

from __future__ import annotations

import hashlib

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opencomplai_evidence_vault.badges import _BadgeBase
from opencomplai_evidence_vault.bias_alerts import _Base as _BiasBase
from opencomplai_evidence_vault.cas import CASStore
from opencomplai_evidence_vault.main import create_app
from opencomplai_evidence_vault.models import Base as _LedgerBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def client(tmp_path):
    db_path = tmp_path / "test-ledger-root.db"
    cas_path = tmp_path / "cas"
    cas_path.mkdir()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_LedgerBase.metadata.create_all)
        await conn.run_sync(_BiasBase.metadata.create_all)
        await conn.run_sync(_BadgeBase.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()
    app.state.engine = engine
    app.state.sessionmaker = session_factory
    app.state.cas = CASStore(str(cas_path))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    await engine.dispose()


async def test_ledger_root_for_empty_chain_is_genesis(client):
    """An empty ledger anchors to the genesis hash (sha256 of empty string)."""
    expected = f"sha256:{hashlib.sha256(b'').hexdigest()}"
    resp = await client.get("/v1/evidence/ledger-root")
    assert resp.status_code == 200
    assert resp.json() == {"ledger_root_hash": expected}


async def test_ledger_root_advances_when_event_is_appended(client):
    """Appending an event must change the reported root hash."""
    before = (await client.get("/v1/evidence/ledger-root")).json()["ledger_root_hash"]

    resp = await client.post(
        "/v1/evidence/events",
        json={"event_type": "test_event", "payload": {"n": 1}},
    )
    assert resp.status_code == 201

    after = (await client.get("/v1/evidence/ledger-root")).json()["ledger_root_hash"]
    assert after != before
    assert after.startswith("sha256:")
