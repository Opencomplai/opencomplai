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
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from opencomplai_core.signing import (
    SigningDomain,
    canonical_json_bytes,
    verify_bundle_bytes,
)
from sqlalchemy import String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from opencomplai_evidence_vault.models import OSS_DEFAULT_TENANT_ID


class _BadgeBase(DeclarativeBase):
    pass


class BadgeDB(_BadgeBase):
    __tablename__ = "compliance_badges"
    __table_args__ = (
        # Mirrors migration 0004's ix_compliance_badges_tenant_badge. Declared
        # here too (not just in the migration) so SQLite unit tests using
        # create_all() — and any other non-Alembic dev/OSS deployment — also
        # get real DB-level enforcement, not just the app-level pre-insert
        # check issue_badge() does. Without this, the race issue_badge's
        # IntegrityError handling exists to catch could never actually be
        # reproduced or enforced outside a migrated Postgres deployment.
        UniqueConstraint(
            "tenant_id", "badge_id", name="ux_compliance_badges_tenant_badge"
        ),
    )

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default=OSS_DEFAULT_TENANT_ID, index=True
    )
    # badge_id = sha256(system_id + bundle_checksum) is no longer globally
    # unique once tenants share a schema — two tenants can each issue a
    # badge for their own system_id "foo" and collide on the same digest.
    # Uniqueness (and idempotency) is now scoped to (tenant_id, badge_id).
    badge_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    system_id: Mapped[str] = mapped_column(String, nullable=False)
    bundle_checksum: Mapped[str] = mapped_column(String, nullable=False)
    issued_at: Mapped[str] = mapped_column(String, nullable=False)
    status_artifact_hash: Mapped[str] = mapped_column(String, nullable=False)
    signature: Mapped[str | None] = mapped_column(String, nullable=True)


def _make_badge_id(system_id: str, bundle_checksum: str) -> str:
    raw = f"{system_id}:{bundle_checksum}"
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def _make_artifact_hash(artifact: dict) -> str:
    # Same serialiser as the signature path, so the bytes that get hashed and
    # the bytes that get signed cannot drift apart.
    serialized = canonical_json_bytes(artifact)
    return f"sha256:{hashlib.sha256(serialized).hexdigest()}"


class InvalidBadgeSignatureError(ValueError):
    """Raised when a badge-issue request carries a signature that fails verification."""


def _oss_badge_public_key_path() -> Path | None:
    """
    Path to the single well-known Ed25519 public key badge signatures are
    verified against (SEC-SERVICE-AUTH). Optional: unset means signatures are
    accepted but not verified, preserving OSS unsigned mode — the same
    posture `opencomplai_core.signing.verify_artifact` already documents for
    an absent signature.
    """
    raw = os.environ.get("OSS_BADGE_PUBLIC_KEY_PATH", "").strip()
    return Path(raw) if raw else None


def _verify_badge_signature(artifact: dict, signature: str) -> bool:
    pub_key_path = _oss_badge_public_key_path()
    if pub_key_path is None:
        return True
    # Shared with the artifact signer rather than re-implemented here. The
    # inline `json.dumps(artifact, sort_keys=True)` this replaces was that same
    # call minus `default=str`; the two agreed byte-for-byte only by luck of
    # badge artifacts containing JSON-native scalars.
    serialized = canonical_json_bytes(artifact)
    # Hard cutover to the tagged form, with no `accept_untagged` window.
    # Untagged bytes here are byte-identical to a signed ScanStatusArtifact's
    # canonical payload, so a signature from `opencomplai check --sign` used to
    # verify unmodified as a badge signature. Accepting untagged signatures
    # during a migration window would mean keeping exactly that confusion alive
    # under a flag, and nothing in this repo legitimately produced a badge
    # signature for such a window to protect.
    return verify_bundle_bytes(serialized, signature, pub_key_path, SigningDomain.BADGE)


async def issue_badge(
    session: AsyncSession,
    system_id: str,
    bundle_checksum: str,
    artifact: dict,
    signature: str | None = None,
    tenant_id: str = OSS_DEFAULT_TENANT_ID,
) -> tuple[BadgeDB, bool]:
    """
    Issue a compliance badge for the given artifact.

    Returns (badge, created) where created=False means the badge already existed
    (idempotent — same (tenant_id, system_id, bundle_checksum) always returns
    the same badge).

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
    # Configuring OSS_BADGE_PUBLIC_KEY_PATH is the opt-in to signed badges, so
    # it has to mean signatures are *required*. Previously an unsigned request
    # skipped verification entirely even with the key set, so anyone who could
    # not forge a signature simply omitted it — which left the verification
    # path, and the domain separation protecting it, guarding a door that was
    # already open. With no key configured, unsigned issuance stays supported:
    # that is OSS unsigned mode, and it is deliberate.
    if _oss_badge_public_key_path() is not None and signature is None:
        raise InvalidBadgeSignatureError(
            "Badge issuance requires a signature when OSS_BADGE_PUBLIC_KEY_PATH is configured"
        )
    if signature is not None and not _verify_badge_signature(artifact, signature):
        raise InvalidBadgeSignatureError(
            "Badge issuance signature failed verification against the configured public key"
        )

    badge_id = _make_badge_id(system_id, bundle_checksum)

    # Idempotency check — scoped to tenant, since badge_id alone is no longer
    # globally unique once multiple tenants can issue badges for the same
    # (system_id, bundle_checksum) pair.
    stmt = select(BadgeDB).where(
        BadgeDB.badge_id == badge_id, BadgeDB.tenant_id == tenant_id
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False

    badge = BadgeDB(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        badge_id=badge_id,
        system_id=system_id,
        bundle_checksum=bundle_checksum,
        issued_at=datetime.now(UTC).isoformat(),
        status_artifact_hash=_make_artifact_hash(artifact),
        signature=signature,
    )
    try:
        async with session.begin_nested():
            session.add(badge)
            await session.flush()
    except IntegrityError:
        # A concurrent issuer won the race on the (tenant_id, badge_id)
        # unique index between our existence check and this insert.
        # `ix_compliance_badges_tenant_badge` (migration 0004) guarantees
        # that row now exists — re-reading it turns the documented
        # idempotent-success contract into the actual behavior instead of
        # a bare 500.
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            raise
        return existing, False
    return badge, True


async def get_badge(
    session: AsyncSession, badge_id: str, tenant_id: str = OSS_DEFAULT_TENANT_ID
) -> BadgeDB | None:
    stmt = select(BadgeDB).where(
        BadgeDB.badge_id == badge_id, BadgeDB.tenant_id == tenant_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_badges_table(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(_BadgeBase.metadata.create_all)
