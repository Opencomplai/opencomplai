"""
Compliance badge issuance and verification (PRD §5 — Pro features).

Badges are issued only for ScanStatusArtifacts with:
  - result == "pass"
  - pending_verifications_count == 0

Idempotent: issuing a badge for the same (system_id, bundle_checksum) pair
returns the existing badge rather than creating a duplicate.

badge_id = sha256(system_id + ":" + bundle_checksum)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class _BadgeBase(DeclarativeBase):
    pass


class BadgeDB(_BadgeBase):
    __tablename__ = "compliance_badges"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    badge_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    system_id: Mapped[str] = mapped_column(String, nullable=False)
    bundle_checksum: Mapped[str] = mapped_column(String, nullable=False)
    issued_at: Mapped[str] = mapped_column(String, nullable=False)
    status_artifact_hash: Mapped[str] = mapped_column(String, nullable=False)
    signature: Mapped[str | None] = mapped_column(String, nullable=True)


def _make_badge_id(system_id: str, bundle_checksum: str) -> str:
    raw = f"{system_id}:{bundle_checksum}"
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def _make_artifact_hash(artifact: dict) -> str:
    import json

    serialized = json.dumps(artifact, sort_keys=True).encode()
    return f"sha256:{hashlib.sha256(serialized).hexdigest()}"


async def issue_badge(
    session: AsyncSession,
    system_id: str,
    bundle_checksum: str,
    artifact: dict,
    signature: str | None = None,
) -> tuple[BadgeDB, bool]:
    """
    Issue a compliance badge for the given artifact.

    Returns (badge, created) where created=False means the badge already existed
    (idempotent — same (system_id, bundle_checksum) always returns the same badge).

    Raises ValueError if the artifact does not meet issuance criteria.
    """
    result = artifact.get("result")
    pending = artifact.get("pending_verifications_count", 1)

    if result != "pass":
        raise ValueError(f"Badge issuance requires result='pass', got '{result}'")
    if pending != 0:
        raise ValueError(
            f"Badge issuance requires pending_verifications_count=0, got {pending}"
        )

    badge_id = _make_badge_id(system_id, bundle_checksum)

    # Idempotency check
    stmt = select(BadgeDB).where(BadgeDB.badge_id == badge_id)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False

    badge = BadgeDB(
        id=str(uuid.uuid4()),
        badge_id=badge_id,
        system_id=system_id,
        bundle_checksum=bundle_checksum,
        issued_at=datetime.now(UTC).isoformat(),
        status_artifact_hash=_make_artifact_hash(artifact),
        signature=signature,
    )
    session.add(badge)
    return badge, True


async def get_badge(session: AsyncSession, badge_id: str) -> BadgeDB | None:
    stmt = select(BadgeDB).where(BadgeDB.badge_id == badge_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_badges_table(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(_BadgeBase.metadata.create_all)
