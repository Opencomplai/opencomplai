"""
Bounded-memory chain walks: verify_chain batches by keyset, and
ledger-history-tips pages with limit / after_seq.

_CHAIN_BATCH is monkeypatched down to 4 so a 25-event chain spans seven
batches and the batch boundaries (seq 4|5, 8|9, ...) are actually crossed.

Chains whose seq values have gaps are covered too: tenants written before
migration 0008 carry globally numbered seq, so a cursor must be the last seq
actually seen, never after_seq plus a count.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opencomplai_core.service_auth import mint_service_token
from opencomplai_evidence_vault import ledger
from opencomplai_evidence_vault import main as vault_main
from opencomplai_evidence_vault.ledger import (
    GENESIS_HASH,
    append_event,
    compute_history_tips,
    compute_history_tips_page,
    event_hash,
    verify_chain,
)
from opencomplai_evidence_vault.main import create_app
from opencomplai_evidence_vault.models import OSS_DEFAULT_TENANT_ID, Base, LedgerEventDB
from sqlalchemy import MetaData, event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TIPS = "/v1/evidence/ledger-history-tips"


@pytest_asyncio.fixture
async def sessionmaker_(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'paging.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def migrated_sessionmaker(tmp_path):
    """A ledger table as a database migrated through 0003 has it: seq is
    nullable there (the model, and so create_all, say NOT NULL)."""
    meta = MetaData()
    table = LedgerEventDB.__table__.to_metadata(meta)
    table.c.seq.nullable = True
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'migrated.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(meta.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(sessionmaker_, _service_token_secret):
    app = create_app()
    app.state.sessionmaker = sessionmaker_
    token = mint_service_token(
        "test-caller", os.environ["INTERNAL_SERVICE_TOKEN_SECRET"]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac


@pytest.fixture
def small_batches(monkeypatch):
    monkeypatch.setattr(ledger, "_CHAIN_BATCH", 4)


async def _append(sessionmaker_, n: int, tenant_id: str = OSS_DEFAULT_TENANT_ID):
    async with sessionmaker_() as s:
        for i in range(n):
            await append_event(
                s, event_type="test", payload={"n": i}, tenant_id=tenant_id
            )
            await s.commit()


async def _append_with_seqs(
    sessionmaker_, seqs: list[int], monkeypatch, tenant_id: str = OSS_DEFAULT_TENANT_ID
):
    """Append len(seqs) events that claim exactly these seq values, the way a
    chain with gaps in its numbering looks."""
    claimed = iter(seqs)

    async def next_seq(session, tenant_id=OSS_DEFAULT_TENANT_ID):
        return next(claimed)

    with monkeypatch.context() as m:
        m.setattr(ledger, "_next_seq", next_seq)
        await _append(sessionmaker_, len(seqs), tenant_id)


async def _insert_null_seq_event(sessionmaker_, tenant_id: str = OSS_DEFAULT_TENANT_ID):
    """Write a ledger row with seq NULL, as only an out-of-band write can."""
    async with sessionmaker_() as s:
        s.add(
            LedgerEventDB(
                event_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                ts=datetime.now(UTC),
                event_type="out-of-band",
                payload_hash=GENESIS_HASH,
                prev_hash=GENESIS_HASH,
                seq=None,
                signer_id=None,
            )
        )
        await s.commit()


async def _reference_tips(sessionmaker_, tenant_id: str = OSS_DEFAULT_TENANT_ID):
    """Genesis plus every event hash, from one unbatched read."""
    async with sessionmaker_() as s:
        rows = await s.execute(
            select(LedgerEventDB)
            .where(LedgerEventDB.tenant_id == tenant_id)
            .order_by(LedgerEventDB.seq.asc())
        )
        return [GENESIS_HASH, *(event_hash(e) for e in rows.scalars())]


async def _walk_pages(client, limit: int, headers: dict | None = None):
    """Follow next_after_seq to the end; return (genesis, tips, cursors)."""
    tips: list[str] = []
    cursors: list[int | None] = []
    after_seq = 0
    while True:
        resp = await client.get(
            TIPS, params={"limit": limit, "after_seq": after_seq}, headers=headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == len(body["tips"])
        tips.extend(body["tips"])
        cursors.append(body["next_after_seq"])
        if body["next_after_seq"] is None:
            return body["genesis"], tips, cursors
        after_seq = body["next_after_seq"]


async def _corrupt(
    sessionmaker_, seq: int, field: str, tenant_id=OSS_DEFAULT_TENANT_ID
):
    async with sessionmaker_() as s:
        row = (
            await s.execute(
                select(LedgerEventDB).where(
                    LedgerEventDB.tenant_id == tenant_id, LedgerEventDB.seq == seq
                )
            )
        ).scalar_one()
        setattr(row, field, "sha256:" + "f" * 64)
        await s.commit()


# ---------------------------------------------------------------------------
# Equivalence: batching must not change what verify_chain / the tips say
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_events", [0, 1, 4, 8, 9, 25])
async def test_batched_walk_matches_unbatched_reference(
    sessionmaker_, client, small_batches, n_events
):
    await _append(sessionmaker_, n_events)
    reference = await _reference_tips(sessionmaker_)

    async with sessionmaker_() as s:
        assert await verify_chain(s) is True
        assert await compute_history_tips(s) == reference

    genesis, tips, _ = await _walk_pages(client, limit=7)
    assert [genesis, *tips] == reference


async def test_verify_chain_reads_in_bounded_batches(
    sessionmaker_, small_batches, monkeypatch
):
    await _append(sessionmaker_, 25)
    sizes: list[int] = []
    real = ledger._events_after

    async def spy(session, tenant_id, after_seq, limit):
        rows = await real(session, tenant_id, after_seq, limit)
        sizes.append(len(rows))
        return rows

    monkeypatch.setattr(ledger, "_events_after", spy)
    async with sessionmaker_() as s:
        assert await verify_chain(s) is True

    assert sizes == [4, 4, 4, 4, 4, 4, 1]  # never more than _CHAIN_BATCH rows


async def test_tips_page_cursor_is_exact_at_the_final_page(sessionmaker_):
    await _append(sessionmaker_, 8)
    async with sessionmaker_() as s:
        first, cursor = await compute_history_tips_page(s, after_seq=0, limit=4)
        second, cursor2 = await compute_history_tips_page(s, after_seq=cursor, limit=4)
        past_end, cursor3 = await compute_history_tips_page(s, after_seq=8, limit=4)

    assert cursor == 4
    assert cursor2 is None  # exactly 8 events: no empty trailing page
    assert (len(first), len(second)) == (4, 4)
    assert (past_end, cursor3) == ([], None)


# ---------------------------------------------------------------------------
# Tamper detection must hold across batch boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seq", "field"),
    [
        (1, "prev_hash"),  # very first event
        (5, "prev_hash"),  # first row of the second batch
        (9, "prev_hash"),  # first row of the third batch
        (25, "prev_hash"),  # last event, in the short final batch
        (4, "payload_hash"),  # last row of a batch: caught on the next batch's row
        (8, "payload_hash"),
    ],
)
async def test_tamper_is_detected_across_batch_boundaries(
    sessionmaker_, small_batches, seq, field
):
    await _append(sessionmaker_, 25)
    async with sessionmaker_() as s:
        assert await verify_chain(s) is True

    await _corrupt(sessionmaker_, seq, field)

    async with sessionmaker_() as s:
        assert await verify_chain(s) is False


# ---------------------------------------------------------------------------
# Route: unpaged guard, parameter validation
# ---------------------------------------------------------------------------


async def test_unpaged_shape_is_unchanged_for_a_normal_ledger(sessionmaker_, client):
    await _append(sessionmaker_, 3)
    resp = await client.get(TIPS)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"tips", "count"}
    assert body["tips"] == await _reference_tips(sessionmaker_)
    assert body["count"] == 4  # genesis + 3 events


async def test_unpaged_request_is_refused_past_the_cap_but_paging_works(
    sessionmaker_, client, monkeypatch
):
    monkeypatch.setattr(vault_main, "LEDGER_TIPS_MAX_UNPAGED", 5)
    await _append(sessionmaker_, 6)

    resp = await client.get(TIPS)
    assert resp.status_code == 413
    detail = resp.json()["detail"]
    assert "limit" in detail
    assert "after_seq" in detail

    genesis, tips, _ = await _walk_pages(client, limit=2)
    assert [genesis, *tips] == await _reference_tips(sessionmaker_)


async def test_unpaged_request_at_exactly_the_cap_is_served(
    sessionmaker_, client, monkeypatch
):
    monkeypatch.setattr(vault_main, "LEDGER_TIPS_MAX_UNPAGED", 5)
    await _append(sessionmaker_, 5)
    resp = await client.get(TIPS)
    assert resp.status_code == 200
    assert resp.json()["count"] == 6


async def test_after_seq_without_limit_is_422(client):
    resp = await client.get(TIPS, params={"after_seq": 3})
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 5001},
        {"limit": -1},
        {"limit": "abc"},
        {"limit": 10, "after_seq": -1},
        {"limit": 10, "after_seq": 2**63},
    ],
)
async def test_out_of_range_paging_parameters_are_422(client, params):
    resp = await client.get(TIPS, params=params)
    assert resp.status_code == 422


async def test_limit_bounds_are_inclusive(sessionmaker_, client):
    await _append(sessionmaker_, 2)
    for limit in (1, 5000):
        resp = await client.get(TIPS, params={"limit": limit})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tenant isolation and the empty chain
# ---------------------------------------------------------------------------


async def test_pages_and_cursors_never_cross_tenants(sessionmaker_, client):
    await _append(sessionmaker_, 5, tenant_id="tenant-a")
    await _append(sessionmaker_, 9, tenant_id="tenant-b")
    ref_a = await _reference_tips(sessionmaker_, "tenant-a")
    ref_b = await _reference_tips(sessionmaker_, "tenant-b")

    genesis, tips_a, cursors_a = await _walk_pages(
        client, limit=2, headers={"X-Tenant-Id": "tenant-a"}
    )
    assert [genesis, *tips_a] == ref_a
    assert not set(tips_a) & set(ref_b[1:])
    # tenant-a's last event is seq 5, so its cursors never run past 5 even
    # though tenant-b's chain is longer.
    assert cursors_a == [2, 4, None]

    # The unpaged guard and body are per tenant as well: genesis + own events.
    for tenant, expected in (("tenant-a", ref_a), ("tenant-b", ref_b)):
        resp = await client.get(TIPS, headers={"X-Tenant-Id": tenant})
        assert resp.status_code == 200
        assert resp.json() == {"tips": expected, "count": len(expected)}

    # Each tenant's chain verifies on its own and a break in one is invisible
    # to the other.
    await _corrupt(sessionmaker_, 3, "prev_hash", tenant_id="tenant-b")
    async with sessionmaker_() as s:
        assert await verify_chain(s, tenant_id="tenant-a") is True
        assert await verify_chain(s, tenant_id="tenant-b") is False


async def test_empty_chain(sessionmaker_, client):
    async with sessionmaker_() as s:
        assert await verify_chain(s) is True

    resp = await client.get(TIPS, params={"limit": 10})
    assert resp.status_code == 200
    assert resp.json() == {
        "genesis": GENESIS_HASH,
        "tips": [],
        "count": 0,
        "next_after_seq": None,
    }

    unpaged = await client.get(TIPS)
    assert unpaged.json() == {"tips": [GENESIS_HASH], "count": 1}


# ---------------------------------------------------------------------------
# Gaps in seq: the cursor is the last seq seen, never after_seq + a count
# ---------------------------------------------------------------------------

# Eleven events, and exactly two batches of four. Every gap is deliberate:
# the first seq (10) is above _CHAIN_BATCH, so a cursor of "after_seq + batch"
# lands below it and re-reads the same rows.
GAPPY_SEQS = [
    [10, 13, 17, 18, 25, 26, 40, 41, 42, 77, 100],
    [10, 13, 17, 18, 25, 26, 40, 41],
]
GAPPY_IDS = ["eleven-events", "two-full-batches"]


def _expected_cursors(seqs: list[int], limit: int) -> list[int | None]:
    """next_after_seq of each page: the seq of the page's last event, or None
    on the page that reaches the end of the chain."""
    return [seqs[i] for i in range(limit - 1, len(seqs) - 1, limit)] + [None]


@pytest.mark.parametrize("seqs", GAPPY_SEQS, ids=GAPPY_IDS)
@pytest.mark.parametrize("limit", [3, 4])
async def test_gappy_chain_verifies_and_pages_match_reference(
    sessionmaker_, client, small_batches, monkeypatch, seqs, limit
):
    await _append_with_seqs(sessionmaker_, seqs, monkeypatch)
    reference = await _reference_tips(sessionmaker_)

    async with sessionmaker_() as s:
        assert await verify_chain(s) is True
        assert await compute_history_tips(s) == reference

    genesis, tips, cursors = await _walk_pages(client, limit=limit)
    assert [genesis, *tips] == reference
    assert cursors == _expected_cursors(seqs, limit)


@pytest.mark.parametrize("seqs", GAPPY_SEQS, ids=GAPPY_IDS)
async def test_verify_chain_cursor_is_the_last_seq_of_each_batch(
    sessionmaker_, small_batches, monkeypatch, seqs
):
    await _append_with_seqs(sessionmaker_, seqs, monkeypatch)
    after_seqs: list[int] = []
    real = ledger._events_after

    async def spy(session, tenant_id, after_seq, limit):
        after_seqs.append(after_seq)
        return await real(session, tenant_id, after_seq, limit)

    monkeypatch.setattr(ledger, "_events_after", spy)
    async with sessionmaker_() as s:
        assert await verify_chain(s) is True

    assert after_seqs == [0, seqs[3], seqs[7]]


async def test_a_page_may_start_inside_a_gap(sessionmaker_, monkeypatch):
    seqs = GAPPY_SEQS[0]
    await _append_with_seqs(sessionmaker_, seqs, monkeypatch)
    reference = await _reference_tips(sessionmaker_)

    async with sessionmaker_() as s:
        # 14 and 16 lie between seq 13 and seq 17: the page starts at seq 17.
        for after_seq in (14, 16):
            page, cursor = await compute_history_tips_page(
                s, after_seq=after_seq, limit=2
            )
            assert page == reference[3:5]  # the events with seq 17 and 18
            assert cursor == 18
        assert await compute_history_tips_page(s, after_seq=99, limit=2) == (
            reference[-1:],
            None,
        )  # only seq 100 is left: a short last page, no cursor
        assert await compute_history_tips_page(s, after_seq=100, limit=2) == ([], None)


@pytest.mark.parametrize("index", [0, 3, 4, 7, 8, 10])
async def test_tamper_is_detected_in_a_gappy_chain(
    sessionmaker_, small_batches, monkeypatch, index
):
    seqs = GAPPY_SEQS[0]
    await _append_with_seqs(sessionmaker_, seqs, monkeypatch)
    async with sessionmaker_() as s:
        assert await verify_chain(s) is True

    await _corrupt(sessionmaker_, seqs[index], "prev_hash")

    async with sessionmaker_() as s:
        assert await verify_chain(s) is False


# ---------------------------------------------------------------------------
# A NULL seq is invisible to the keyset walk, so verify_chain fails closed
# ---------------------------------------------------------------------------


async def test_verify_chain_fails_on_a_null_seq_event(migrated_sessionmaker):
    await _append(migrated_sessionmaker, 3)
    async with migrated_sessionmaker() as s:
        assert await verify_chain(s) is True

    await _insert_null_seq_event(migrated_sessionmaker)

    async with migrated_sessionmaker() as s:
        assert await verify_chain(s) is False


async def test_a_null_seq_event_only_fails_its_own_tenant(migrated_sessionmaker):
    await _append(migrated_sessionmaker, 3, tenant_id="tenant-a")
    await _append(migrated_sessionmaker, 3, tenant_id="tenant-b")
    await _insert_null_seq_event(migrated_sessionmaker, tenant_id="tenant-b")

    async with migrated_sessionmaker() as s:
        assert await verify_chain(s, tenant_id="tenant-a") is True
        assert await verify_chain(s, tenant_id="tenant-b") is False


async def test_nullable_seq_schema_does_not_change_a_normal_chain(
    migrated_sessionmaker, small_batches
):
    await _append(migrated_sessionmaker, 9)
    async with migrated_sessionmaker() as s:
        assert await verify_chain(s) is True


# ---------------------------------------------------------------------------
# The unpaged guard is a bounded read, not a COUNT(*) over the whole chain
# ---------------------------------------------------------------------------


async def test_unpaged_guard_reads_one_bounded_page_not_a_count(
    sessionmaker_, client, monkeypatch
):
    monkeypatch.setattr(vault_main, "LEDGER_TIPS_MAX_UNPAGED", 5)
    await _append(sessionmaker_, 9)

    statements: list[tuple[str, tuple]] = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append((statement, tuple(parameters)))

    sync_engine = sessionmaker_.kw["bind"].sync_engine
    event.listen(sync_engine, "before_cursor_execute", record)
    try:
        resp = await client.get(TIPS)
    finally:
        event.remove(sync_engine, "before_cursor_execute", record)

    assert resp.status_code == 413
    reads = [(sql, params) for sql, params in statements if "ledger_events" in sql]
    assert len(reads) == 1
    sql, params = reads[0]
    assert "count(" not in sql.lower()
    assert "LIMIT" in sql
    assert 6 in params  # the cap plus one: enough to know the chain is longer
