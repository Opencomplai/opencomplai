"""Tests for the Merkle-linked event ledger (REQ-EV-001)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from opencomplai_evidence_vault.ledger import (
    _canonical,
    _sha256,
    append_event,
    verify_chain,
)
from opencomplai_evidence_vault.models import Base, LedgerEventDB
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


def test_sha256_format():
    result = _sha256("test")
    assert result.startswith("sha256:")
    assert len(result) == 71


def test_sha256_deterministic():
    assert _sha256("hello") == _sha256("hello")


def test_sha256_collision_resistant():
    assert _sha256("hello") != _sha256("world")


def test_canonical_is_deterministic():
    c1 = _canonical("id1", "2024-01-01T00:00:00+00:00", "test_event", "sha256:abc")
    c2 = _canonical("id1", "2024-01-01T00:00:00+00:00", "test_event", "sha256:abc")
    assert c1 == c2


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as s:
        yield s

    await engine.dispose()


@pytest.mark.asyncio
async def test_append_event_creates_chained_events(session: AsyncSession):
    e1 = await append_event(session, event_type="test", payload={"n": 1})
    await session.commit()
    e2 = await append_event(session, event_type="test", payload={"n": 2})
    await session.commit()

    assert e1.prev_hash == _sha256("")
    assert e2.prev_hash != _sha256("")

    assert await verify_chain(session) is True


@pytest.mark.asyncio
async def test_verify_chain_detects_tamper(session: AsyncSession):
    await append_event(session, event_type="test", payload={"n": 1})
    await (
        session.commit()
    )  # commit before next append so get_chain_tip sees a stable chain tip
    await append_event(session, event_type="test", payload={"n": 2})
    await session.commit()

    assert await verify_chain(session) is True

    stmt = (
        select(LedgerEventDB)
        .order_by(LedgerEventDB.ts.asc(), LedgerEventDB.seq.asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    first = result.scalar_one()

    first.payload_hash = _sha256("tampered")
    await session.commit()

    assert await verify_chain(session) is False
