"""
Durable storage for risk-engine's HITL review queue, override idempotency
cache, and eval-run cache (PERSIST-RISK).

risk-engine previously held these as process-local dicts (_REVIEW_ITEMS,
_REVIEW_CONTEXTS, _ACCEPTED_OVERRIDES, _COMPLETED_EVALS) — a restart or a
second replica silently dropped in-flight review items and broke idempotency
guarantees. evidence-vault already has the only real Postgres+RLS deployment
in this stack (TEN-VAULT), so these tables live here rather than standing up
a second migration/RLS chain in risk-engine; risk-engine keeps its business
logic (round-robin assignment, dual-approval, idempotency-conflict checks)
and calls these DAOs over HTTP instead of touching dicts directly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from opencomplai_evidence_vault.models import OSS_DEFAULT_TENANT_ID


class _Base(DeclarativeBase):
    pass


class ReviewItemDB(_Base):
    __tablename__ = "review_items"

    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default=OSS_DEFAULT_TENANT_ID, index=True
    )
    system_id: Mapped[str] = mapped_column(String, nullable=False)
    commit_ref: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, index=True)
    payload_ref: Mapped[str] = mapped_column(String, nullable=False)
    context_ref: Mapped[str] = mapped_column(String, nullable=False)
    reviewer_group: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[str | None] = mapped_column(String, nullable=True)
    linked_override_id: Mapped[str | None] = mapped_column(String, nullable=True)


class ReviewContextDB(_Base):
    __tablename__ = "review_contexts"

    context_ref: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default=OSS_DEFAULT_TENANT_ID, index=True
    )
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class AcceptedOverrideDB(_Base):
    __tablename__ = "accepted_overrides"

    idempotency_key: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default=OSS_DEFAULT_TENANT_ID, index=True
    )
    payload_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class CompletedEvalDB(_Base):
    __tablename__ = "completed_evals"

    eval_run_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default=OSS_DEFAULT_TENANT_ID, index=True
    )
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


def _row_to_item(row: ReviewItemDB) -> dict:
    return {
        "review_id": row.review_id,
        "tenant_id": row.tenant_id,
        "system_id": row.system_id,
        "commit_ref": row.commit_ref,
        "reason": row.reason,
        "state": row.state,
        "payload_ref": row.payload_ref,
        "context_ref": row.context_ref,
        "reviewer_group": row.reviewer_group,
        "assigned_to": row.assigned_to,
        "idempotency_key": row.idempotency_key,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
        "decided_at": row.decided_at,
        "linked_override_id": row.linked_override_id,
    }


async def get_review_item(
    session: AsyncSession, review_id: str, tenant_id: str = OSS_DEFAULT_TENANT_ID
) -> dict | None:
    stmt = select(ReviewItemDB).where(
        ReviewItemDB.review_id == review_id, ReviewItemDB.tenant_id == tenant_id
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return _row_to_item(row) if row is not None else None


async def upsert_review_item(
    session: AsyncSession, item: dict, tenant_id: str = OSS_DEFAULT_TENANT_ID
) -> dict:
    """
    Insert a new review item, or overwrite an existing one with the same
    review_id (used for state transitions: assign, decide). Scoped to
    tenant_id so a caller can never overwrite another tenant's row.
    """
    existing = await session.get(ReviewItemDB, item["review_id"])
    if existing is not None and existing.tenant_id != tenant_id:
        raise PermissionError(
            f"review_id {item['review_id']} belongs to another tenant"
        )

    if existing is None:
        row = ReviewItemDB(tenant_id=tenant_id, **item)
        session.add(row)
    else:
        for key, value in item.items():
            if key == "review_id":
                continue
            setattr(existing, key, value)
        row = existing

    await session.flush()
    return _row_to_item(row)


async def list_review_items(
    session: AsyncSession,
    tenant_id: str = OSS_DEFAULT_TENANT_ID,
    state: str | None = None,
    assigned_to: str | None = None,
) -> list[dict]:
    stmt = select(ReviewItemDB).where(ReviewItemDB.tenant_id == tenant_id)
    if state is not None:
        stmt = stmt.where(ReviewItemDB.state == state)
    if assigned_to is not None:
        stmt = stmt.where(ReviewItemDB.assigned_to == assigned_to)
    stmt = stmt.order_by(ReviewItemDB.created_at.asc())
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_item(row) for row in rows]


#: States a review item can be in while it still awaits a human decision.
#: ``expired`` is deliberately excluded — an expired item is no longer
#: actionable, and counting it as pending would make a dashboard's "work
#: outstanding" figure grow forever.
PENDING_REVIEW_STATES = ("queued", "assigned")


async def summarize_review_items(
    session: AsyncSession, tenant_id: str = OSS_DEFAULT_TENANT_ID
) -> dict:
    """
    Aggregate one tenant's review queue into the four figures the dashboard
    review-queue widget renders (DASH-SUMMARY).

    Aggregating here rather than in the caller is deliberate: the alternative
    is shipping every row of the queue over HTTP on each dashboard poll so the
    caller can count them, which gets monotonically slower as decided items
    accumulate and burns the caller's rate-limit budget to compute four
    numbers that live one ``GROUP BY`` away from the data.

    Field semantics, chosen so ``assigned_count`` is a strict subset of
    ``pending_count`` rather than a disjoint bucket:

    - ``pending_count`` — items awaiting a decision (``queued`` + ``assigned``)
    - ``assigned_count`` — the subset of those already assigned to a reviewer
    - ``by_reason`` — the pending items broken down by ``ReviewReason``, i.e.
      the actionable backlog, not lifetime history
    - ``mean_time_to_decision_hours`` — mean ``decided_at - created_at`` over
      decided items, or ``None`` when nothing has been decided yet

    Note that the mean is computed over every decided item for the tenant.
    Only the two timestamp columns are selected rather than whole rows, but it
    is still an unbounded scan; windowing it belongs with the same Phase 3
    pagination tail as ``verify-chain``/``history-tips``, not here.
    """
    pending_stmt = (
        select(ReviewItemDB.state, ReviewItemDB.reason, func.count())
        .where(
            ReviewItemDB.tenant_id == tenant_id,
            ReviewItemDB.state.in_(PENDING_REVIEW_STATES),
        )
        .group_by(ReviewItemDB.state, ReviewItemDB.reason)
    )
    pending_count = 0
    assigned_count = 0
    by_reason: dict[str, int] = {}
    for state, reason, count in (await session.execute(pending_stmt)).all():
        pending_count += count
        if state == "assigned":
            assigned_count += count
        by_reason[reason] = by_reason.get(reason, 0) + count

    decided_stmt = select(ReviewItemDB.created_at, ReviewItemDB.decided_at).where(
        ReviewItemDB.tenant_id == tenant_id,
        ReviewItemDB.state == "decided",
        ReviewItemDB.decided_at.is_not(None),
    )
    durations = []
    for created_at, decided_at in (await session.execute(decided_stmt)).all():
        seconds = _decision_seconds(created_at, decided_at)
        if seconds is not None:
            durations.append(seconds)

    mean_hours = round(sum(durations) / len(durations) / 3600, 4) if durations else None

    return {
        "pending_count": pending_count,
        "assigned_count": assigned_count,
        "mean_time_to_decision_hours": mean_hours,
        "by_reason": by_reason,
    }


def _decision_seconds(created_at: str, decided_at: str | None) -> float | None:
    """
    Elapsed seconds between two stored ISO-8601 timestamps.

    Timestamps are stored as strings (``datetime.isoformat()`` from
    risk-engine), so a row written by an older or hand-edited client can be
    unparseable, or can mix a naive timestamp with an aware one — subtracting
    those raises ``TypeError`` rather than ``ValueError``. Either way the row
    is skipped rather than failing the whole summary; one bad timestamp should
    not take the widget down. A negative result is skipped too, since a
    decision cannot precede its own creation.
    """
    if decided_at is None:
        return None
    try:
        started = datetime.fromisoformat(created_at)
        finished = datetime.fromisoformat(decided_at)
        elapsed = (finished - started).total_seconds()
    except (ValueError, TypeError):
        return None
    return elapsed if elapsed >= 0 else None


async def store_review_context(
    session: AsyncSession,
    context_ref: str,
    context_json: dict,
    tenant_id: str = OSS_DEFAULT_TENANT_ID,
) -> None:
    existing = await session.get(ReviewContextDB, context_ref)
    if existing is not None:
        return
    session.add(
        ReviewContextDB(
            context_ref=context_ref, tenant_id=tenant_id, context_json=context_json
        )
    )
    await session.flush()


async def get_review_context(
    session: AsyncSession, context_ref: str, tenant_id: str = OSS_DEFAULT_TENANT_ID
) -> dict | None:
    stmt = select(ReviewContextDB).where(
        ReviewContextDB.context_ref == context_ref,
        ReviewContextDB.tenant_id == tenant_id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return row.context_json if row is not None else None


async def get_accepted_override(
    session: AsyncSession, idempotency_key: str, tenant_id: str = OSS_DEFAULT_TENANT_ID
) -> tuple[str, dict] | None:
    stmt = select(AcceptedOverrideDB).where(
        AcceptedOverrideDB.idempotency_key == idempotency_key,
        AcceptedOverrideDB.tenant_id == tenant_id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return row.payload_fingerprint, row.response_json


async def store_accepted_override(
    session: AsyncSession,
    idempotency_key: str,
    payload_fingerprint: str,
    response_json: dict,
    tenant_id: str = OSS_DEFAULT_TENANT_ID,
) -> None:
    existing = await session.get(AcceptedOverrideDB, idempotency_key)
    if existing is not None:
        return
    session.add(
        AcceptedOverrideDB(
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            payload_fingerprint=payload_fingerprint,
            response_json=response_json,
        )
    )
    await session.flush()


async def get_completed_eval(
    session: AsyncSession, eval_run_id: str, tenant_id: str = OSS_DEFAULT_TENANT_ID
) -> dict | None:
    stmt = select(CompletedEvalDB).where(
        CompletedEvalDB.eval_run_id == eval_run_id,
        CompletedEvalDB.tenant_id == tenant_id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return row.result_json if row is not None else None


async def store_completed_eval(
    session: AsyncSession,
    eval_run_id: str,
    result_json: dict,
    tenant_id: str = OSS_DEFAULT_TENANT_ID,
) -> None:
    existing = await session.get(CompletedEvalDB, eval_run_id)
    if existing is not None:
        return
    session.add(
        CompletedEvalDB(
            eval_run_id=eval_run_id, tenant_id=tenant_id, result_json=result_json
        )
    )
    await session.flush()


async def create_hitl_tables(engine) -> None:
    """Create HITL persistence tables (used in tests; production uses Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
