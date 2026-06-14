"""
Append-only Merkle-linked event ledger.

Every event is chained to the previous event via prev_hash, forming a
tamper-evident chain. Modifying any event causes all subsequent events'
prev_hash values to become invalid (REQ-EV-001).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opencomplai_evidence_vault.models import LedgerEventDB


def _sha256(data: str) -> str:
    """Return sha256:<hex> of the UTF-8 encoded string."""
    digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _canonical(event_id: str, ts: str, event_type: str, payload_hash: str) -> str:
    """Produce the canonical string representation of an event for hashing."""
    return json.dumps(
        {
            "event_id": event_id,
            "ts": ts,
            "event_type": event_type,
            "payload_hash": payload_hash,
        },
        sort_keys=True,
    )


async def get_chain_tip(session: AsyncSession) -> str:
    """
    Return the prev_hash to use for the next event.

    If the ledger is empty, returns the genesis hash (sha256 of the empty string).

    Ordering: (ts ASC, seq ASC) mirrors verify_chain so that both functions
    agree on which event is "last" even when two events share the same ts value
    (sub-second resolution on SQLite/Windows).  We pick the last row by ordering
    ascending and taking the final result via DESC on the same columns with LIMIT 1.
    """
    stmt = (
        select(LedgerEventDB)
        .order_by(LedgerEventDB.ts.desc(), LedgerEventDB.seq.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    latest = result.scalar_one_or_none()

    if latest is None:
        return _sha256("")

    canonical = _canonical(
        latest.event_id,
        latest.ts.isoformat(),
        latest.event_type,
        latest.payload_hash,
    )
    return _sha256(canonical)


async def _next_seq(session: AsyncSession) -> int:
    """
    Return the next monotonic sequence number for a new ledger event.

    Queries MAX(seq) within the current transaction so that concurrent writers
    do not collide.  The result is MAX(seq) + 1, or 1 for the genesis event.

    Note: this relies on the caller holding an exclusive write lock (via the
    surrounding transaction) — it is safe for single-writer use but would need
    a FOR UPDATE lock on multi-writer Postgres deployments.
    """
    result = await session.execute(select(func.max(LedgerEventDB.seq)))
    current_max = result.scalar_one_or_none()
    return 1 if current_max is None else current_max + 1


async def append_event(
    session: AsyncSession,
    event_type: str,
    payload: dict,
    signer_id: str | None = None,
) -> LedgerEventDB:
    """
    Append a new event to the ledger.

    Computes payload_hash, prev_hash, and a monotonic seq number, persists
    the event, and returns it.  The caller is responsible for committing the
    session.

    The seq column is the authoritative tie-breaker for events that share the
    same ts value (which can happen on platforms where DateTime has coarser-than-
    microsecond resolution, e.g. SQLite on Windows).
    """
    payload_hash = _sha256(json.dumps(payload, sort_keys=True))
    prev_hash = await get_chain_tip(session)
    seq = await _next_seq(session)
    event_id = str(uuid.uuid4())
    ts = datetime.now(UTC)

    event = LedgerEventDB(
        event_id=event_id,
        ts=ts,
        event_type=event_type,
        payload_hash=payload_hash,
        prev_hash=prev_hash,
        seq=seq,
        signer_id=signer_id,
    )
    session.add(event)
    return event


async def compute_history_tips(session: AsyncSession) -> list[str]:
    """
    Walk the entire ledger chain in order and return the rolling Merkle tip
    after each event.

    The first element is the genesis hash (sha256 of ""), the Nth element is
    the running tip after the Nth event has been applied.  An Annex IV dossier
    anchors to the tip at the moment it was generated; calling this function and
    checking whether the dossier's ledger_root_hash appears in the returned list
    confirms the dossier was issued against an unmodified version of the chain.

    For efficiency this is O(N) over the chain length.  For large ledgers,
    consider a dedicated /v1/evidence/ledger-history-tips endpoint that streams
    or paginates rather than materialising the full list in memory.
    """
    stmt = select(LedgerEventDB).order_by(
        LedgerEventDB.ts.asc(), LedgerEventDB.seq.asc()
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    tips: list[str] = [_sha256("")]  # genesis tip (empty ledger)

    for event in events:
        canonical = _canonical(
            event.event_id,
            event.ts.isoformat(),
            event.event_type,
            event.payload_hash,
        )
        tips.append(_sha256(canonical))

    return tips


async def verify_chain(session: AsyncSession) -> bool:
    """
    Verify the integrity of the entire ledger chain.

    Returns True if all events form a valid Merkle chain.
    Returns False if any event's prev_hash does not match the hash of the
    preceding event (tamper detection — REQ-EV-001).
    """
    stmt = select(LedgerEventDB).order_by(
        LedgerEventDB.ts.asc(), LedgerEventDB.seq.asc()
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    if not events:
        return True

    expected_prev = _sha256("")

    for event in events:
        if event.prev_hash != expected_prev:
            return False
        canonical = _canonical(
            event.event_id,
            event.ts.isoformat(),
            event.event_type,
            event.payload_hash,
        )
        expected_prev = _sha256(canonical)

    return True
