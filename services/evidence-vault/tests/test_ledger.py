"""Tests for the hash-chained event ledger (REQ-EV-001)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from opencomplai_evidence_vault.ledger import (
    _canonical,
    _next_seq,
    _sha256,
    append_event,
    event_hash,
    get_chain_tip,
    verify_chain,
)
from opencomplai_evidence_vault.models import OSS_DEFAULT_TENANT_ID, Base, LedgerEventDB
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
    c1 = _canonical(
        "id1", "2024-01-01T00:00:00+00:00", "test_event", "sha256:abc", "sha256:prev"
    )
    c2 = _canonical(
        "id1", "2024-01-01T00:00:00+00:00", "test_event", "sha256:abc", "sha256:prev"
    )
    assert c1 == c2


def test_event_hash_commits_to_prev():
    """
    Guards against a silent v2 format regression: two otherwise-identical
    events with different prev_hash must hash differently (that's the whole
    point of v2 over v1 — see issue #47), and the canonical preimage must
    carry the format-version marker.
    """
    ts = datetime(2024, 1, 1, tzinfo=UTC)
    common = {
        "event_id": "evt-1",
        "tenant_id": OSS_DEFAULT_TENANT_ID,
        "ts": ts,
        "event_type": "test",
        "payload_hash": "sha256:" + "a" * 64,
        "seq": 1,
    }
    e1 = LedgerEventDB(prev_hash=_sha256(""), **common)
    e2 = LedgerEventDB(prev_hash=_sha256("some-other-tip"), **common)

    assert event_hash(e1) != event_hash(e2)

    canonical = _canonical(
        e1.event_id, e1.ts.isoformat(), e1.event_type, e1.payload_hash, e1.prev_hash
    )
    assert '"v": 2' in canonical


def test_event_hash_is_driver_independent_across_tz_renderings():
    """
    Regression for the migration-0009 / runtime timezone divergence: the
    same instant rendered via two different tzinfo offsets (as psycopg2 vs.
    asyncpg would render a non-UTC-configured Postgres session's
    timestamptz value) must hash identically. Before the fix, event_hash
    called ts.isoformat() directly on whatever tzinfo the driver attached,
    so '2026-01-01T11:00:00+01:00' and '2026-01-01T10:00:00+00:00' (the same
    instant) hashed differently, and a chain rewritten by the migration
    under a non-UTC session could never be reproduced by the always-UTC
    runtime.
    """
    ts_utc = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    ts_plus_one = ts_utc.astimezone(timezone(timedelta(hours=1)))
    assert ts_plus_one.isoformat() != ts_utc.isoformat()  # sanity: renders differ

    common = {
        "event_id": "evt-tz",
        "tenant_id": OSS_DEFAULT_TENANT_ID,
        "event_type": "test",
        "payload_hash": "sha256:" + "a" * 64,
        "prev_hash": _sha256(""),
        "seq": 1,
    }
    e_utc = LedgerEventDB(ts=ts_utc, **common)
    e_plus_one = LedgerEventDB(ts=ts_plus_one, **common)

    assert event_hash(e_utc) == event_hash(e_plus_one)


def test_event_hash_naive_timestamp_is_not_converted():
    """Naive datetimes (SQLite) must be hashed as-is — astimezone() on a
    naive value would assume the local zone, which is wrong and
    non-deterministic across machines."""
    ts = datetime(2026, 1, 1, 10, 0, 0)
    assert ts.tzinfo is None

    event = LedgerEventDB(
        event_id="evt-naive",
        tenant_id=OSS_DEFAULT_TENANT_ID,
        ts=ts,
        event_type="test",
        payload_hash="sha256:" + "a" * 64,
        prev_hash=_sha256(""),
        seq=1,
    )
    expected = _sha256(
        _canonical(
            event.event_id,
            ts.isoformat(),
            event.event_type,
            event.payload_hash,
            event.prev_hash,
        )
    )
    assert event_hash(event) == expected


@pytest_asyncio.fixture
async def sessionmaker_() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False)

    await engine.dispose()


@pytest_asyncio.fixture
async def session(
    sessionmaker_: async_sessionmaker[AsyncSession],
) -> AsyncSession:
    async with sessionmaker_() as s:
        yield s


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


@pytest.mark.asyncio
async def test_append_event_retries_past_a_deterministic_seq_collision(
    session: AsyncSession, monkeypatch
):
    """
    PERSIST-RACES: _next_seq's MAX(seq)+1 read has no locking, so a
    concurrent writer can commit the same seq between our read and our
    insert. Reproduced deterministically (no scheduler timing dependency) by
    making the *first* _next_seq call inside append_event return a seq a row
    already occupies — the flush must raise IntegrityError, the SAVEPOINT
    must roll back cleanly, and the retry (a real, uncorrupted _next_seq
    call) must succeed.
    """
    occupied = await _next_seq(session)
    taken = LedgerEventDB(
        event_id="pre-seeded",
        ts=datetime.now(UTC),
        event_type="pre_seeded",
        payload_hash=_sha256("x"),
        prev_hash=_sha256(""),
        seq=occupied,
    )
    session.add(taken)
    await session.flush()

    real_next_seq = _next_seq
    calls = {"n": 0}

    async def _stale_once(
        s: AsyncSession, tenant_id: str = OSS_DEFAULT_TENANT_ID
    ) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            return occupied  # forces a collision with `taken` on first attempt
        return await real_next_seq(s, tenant_id=tenant_id)

    monkeypatch.setattr("opencomplai_evidence_vault.ledger._next_seq", _stale_once)

    event = await append_event(session, event_type="test", payload={"n": 1})
    await session.commit()

    assert calls["n"] == 2  # one collision, one successful retry
    assert event.seq != occupied
    # The retry must re-link to the current tip (not a stale one captured
    # before the collision) or the chain would be permanently broken.
    assert await verify_chain(session) is True


@pytest.mark.asyncio
async def test_concurrent_append_event_both_succeed(
    sessionmaker_: async_sessionmaker[AsyncSession],
):
    """
    Two writers on separate sessions/connections append concurrently via
    asyncio.gather. SQLite serializes at the file-lock level so this doesn't
    reliably reproduce the IntegrityError itself (that's
    test_append_event_retries_past_a_deterministic_seq_collision's job) —
    but it does pin the outward contract PERSIST-RACES restores: neither
    writer's append_event call raises, and both events persist with
    distinct seq values, whatever interleaving actually occurred.
    """

    async def _append(payload: dict) -> LedgerEventDB:
        async with sessionmaker_() as s:
            event = await append_event(s, event_type="concurrent", payload=payload)
            await s.commit()
            return event

    e1, e2 = await asyncio.gather(_append({"n": 1}), _append({"n": 2}))

    assert e1.event_id != e2.event_id
    assert e1.seq is not None
    assert e2.seq is not None

    # The outward contract includes chain validity, not just "no exception":
    # a retried append that re-links to a stale tip would still "succeed"
    # (no exception raised) while permanently breaking verify_chain.
    async with sessionmaker_() as check_session:
        assert await verify_chain(check_session) is True


@pytest.mark.asyncio
async def test_tamper_then_fixup_defeats_verify_chain(session: AsyncSession):
    """
    Issue #47 regression: under the v1 hash format (which omitted prev_hash
    from the preimage), an attacker could tamper an event's payload_hash and
    then "fix up" only its immediate successor's stored prev_hash to match
    the new (tampered) hash — every hash *after* that successor was
    unaffected, since v1 hashes didn't depend on prev_hash, so the chain
    kept verifying as if nothing happened.

    v2 makes every event's hash commit to its own prev_hash, so patching
    event K+1's prev_hash also changes event K+1's *hash*, which in turn
    breaks event K+2's link to it. This requires >= 4 events so there is a
    K+2 for verify_chain to catch the break at (3 events would leave no
    successor to detect the now-changed tip — see
    test_tip_changes_on_tail_tamper for that case).
    """
    events: list[LedgerEventDB] = []
    for n in range(4):
        e = await append_event(session, event_type="test", payload={"n": n})
        await session.commit()
        events.append(e)

    assert await verify_chain(session) is True

    stmt = select(LedgerEventDB).order_by(
        LedgerEventDB.ts.asc(), LedgerEventDB.seq.asc()
    )
    result = await session.execute(stmt)
    ordered = result.scalars().all()
    assert len(ordered) == 4

    # Tamper event 2 (index 1).
    ordered[1].payload_hash = _sha256("tampered")
    # Attacker uses the live algorithm to "fix up" event 3's prev_hash so it
    # matches the new (tampered) hash of event 2.
    ordered[2].prev_hash = event_hash(ordered[1])
    await session.commit()

    assert await verify_chain(session) is False


@pytest.mark.asyncio
async def test_tip_changes_on_tail_tamper(session: AsyncSession):
    """
    In-chain verification (verify_chain) cannot catch a tamper that patches
    the *final* row in the chain, because there is no successor left whose
    prev_hash could be found to mismatch. This is exactly why externally
    anchored dossiers compare against get_chain_tip rather than relying on
    verify_chain alone: tampering the second-to-last event and "fixing up"
    the last event's prev_hash to match still changes the recorded tip.
    """
    for n in range(3):
        await append_event(session, event_type="test", payload={"n": n})
        await session.commit()

    original_tip = await get_chain_tip(session)

    stmt = select(LedgerEventDB).order_by(
        LedgerEventDB.ts.asc(), LedgerEventDB.seq.asc()
    )
    result = await session.execute(stmt)
    ordered = result.scalars().all()
    assert len(ordered) == 3

    # Tamper the second-to-last event and fix up the last event's prev_hash
    # the same way an attacker would.
    ordered[1].payload_hash = _sha256("tampered")
    ordered[2].prev_hash = event_hash(ordered[1])
    await session.commit()

    new_tip = await get_chain_tip(session)
    assert new_tip != original_tip


@pytest.mark.asyncio
async def test_chain_ordering_is_seq_not_ts(session: AsyncSession):
    """
    Regression pin for a genuine concurrency defect this suite caught: ts is
    captured once in append_event before its retry loop, so under
    concurrent same-tenant writers the loser of a seq race can retry, land a
    *higher* seq, and still carry an *earlier* ts than the winner (observed
    directly against real Postgres in
    test_rls_postgres.py::test_concurrent_same_tenant_appends_keep_chain_valid,
    which intermittently failed before this fix despite append_event's
    prev_hash linkage being correct). get_chain_tip/verify_chain/
    compute_history_tips must order by seq alone — ordering by ts (even as a
    tie-break ahead of seq) picks the wrong row as "latest" and makes a
    genuinely valid chain fail verification.

    Builds that exact ts/seq inversion directly (seq=1 with the LATER ts,
    seq=2 with the EARLIER ts, correctly linked in seq order) rather than
    relying on a real race, so this test is deterministic.
    """
    later_ts = datetime(2024, 1, 1, 0, 0, 1, tzinfo=UTC)
    earlier_ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

    first = LedgerEventDB(
        event_id="evt-seq-1",
        tenant_id=OSS_DEFAULT_TENANT_ID,
        ts=later_ts,
        event_type="test",
        payload_hash=_sha256("payload-1"),
        prev_hash=_sha256(""),
        seq=1,
    )
    session.add(first)
    await session.flush()

    second = LedgerEventDB(
        event_id="evt-seq-2",
        tenant_id=OSS_DEFAULT_TENANT_ID,
        ts=earlier_ts,
        event_type="test",
        payload_hash=_sha256("payload-2"),
        prev_hash=event_hash(first),
        seq=2,
    )
    session.add(second)
    await session.commit()

    assert await verify_chain(session) is True
    assert await get_chain_tip(session) == event_hash(second)
