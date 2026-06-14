"""Tests for BiasAlert persistence and purge (REQ-GTVG-002)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from opencomplai_evidence_vault.bias_alerts import (
    BiasAlertDB,
    _Base,
    count_bias_alerts,
    purge_expired_bias_data,
    store_bias_alert,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _store(
    session: AsyncSession, days_old: int, alert_id: str | None = None
) -> BiasAlertDB:
    """Helper: store an alert and backdate created_at."""
    import uuid

    aid = alert_id or str(uuid.uuid4())
    record = await store_bias_alert(
        session=session,
        alert_id=aid,
        severity="high",
        metric="accuracy",
        threshold=0.95,
        linked_event_id=str(uuid.uuid4()),
    )
    await session.flush()
    # Backdate to simulate old record
    record.created_at = datetime.now(UTC) - timedelta(days=days_old)
    await session.flush()
    return record


# ---------------------------------------------------------------------------
# store_bias_alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_bias_alert_creates_record(session: AsyncSession) -> None:
    record = await _store(session, days_old=0)
    await session.commit()
    count = await count_bias_alerts(session)
    assert count == 1
    assert record.alert_id is not None


# ---------------------------------------------------------------------------
# purge_expired_bias_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_deletes_only_expired_records(session: AsyncSession) -> None:
    # 2 old records (> 90 days), 1 fresh record
    await _store(session, days_old=91)
    await _store(session, days_old=95)
    await _store(session, days_old=0)
    await session.commit()

    deleted = await purge_expired_bias_data(session, retention_days=90)
    await session.commit()

    assert deleted == 2
    remaining = await count_bias_alerts(session)
    assert remaining == 1


@pytest.mark.asyncio
async def test_purge_returns_zero_when_nothing_expired(session: AsyncSession) -> None:
    await _store(session, days_old=10)
    await session.commit()

    deleted = await purge_expired_bias_data(session, retention_days=90)
    await session.commit()

    assert deleted == 0
    assert await count_bias_alerts(session) == 1


@pytest.mark.asyncio
async def test_purge_empty_table_returns_zero(session: AsyncSession) -> None:
    deleted = await purge_expired_bias_data(session, retention_days=90)
    assert deleted == 0


@pytest.mark.asyncio
async def test_purge_all_records_leaves_zero(session: AsyncSession) -> None:
    await _store(session, days_old=200)
    await _store(session, days_old=200)
    await session.commit()

    deleted = await purge_expired_bias_data(session, retention_days=90)
    await session.commit()

    assert deleted == 2
    assert await count_bias_alerts(session) == 0


@pytest.mark.asyncio
async def test_post_purge_query_returns_zero_for_expired(session: AsyncSession) -> None:
    """REQ-GTVG-002: expired-record query returns zero post-purge."""
    await _store(session, days_old=100)
    await session.commit()

    await purge_expired_bias_data(session, retention_days=90)
    await session.commit()

    count = await count_bias_alerts(session)
    assert count == 0
