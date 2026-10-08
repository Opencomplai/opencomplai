"""
Durable storage for the control instance registry (CTRL-STORE).

Persistence home per D1 — evidence-vault is the only service in this stack
with a real Postgres+RLS deployment (TEN-VAULT), so the control registry
lives here rather than standing up a second migration/RLS chain elsewhere.

`ControlInstance` identity is deterministic (D2):
`control_id = sha256(f"{tenant_id}|{system_id}|{obligation_id}")[:32]`, via
`opencomplai_core.control_identity.make_control_id`. This makes repeated
upserts for the same {tenant, system, obligation} triple idempotent instead
of creating duplicate rows, and lets `upsert_controls` accept partial
patches (owner-only, state-only, ...): a field's *presence* in the incoming
dict is what decides whether it overwrites the stored value, so callers
must build that dict with "key present" semantics (e.g.
`model_dump(exclude_unset=True)`) rather than always including every field.

`manifest_fingerprints` (D5) tracks the last-seen fingerprint of the
compliance-relevant subset of a system's manifest per (tenant_id,
system_id), so a caller can detect when the manifest changed and the
system's controls need reassessment.
"""

from __future__ import annotations

from datetime import UTC, datetime

from opencomplai_core.control_identity import make_control_id
from opencomplai_core.models import ControlInstance
from sqlalchemy import JSON, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from opencomplai_evidence_vault.models import OSS_DEFAULT_TENANT_ID


class _Base(DeclarativeBase):
    pass


class ControlInstanceDB(_Base):
    __tablename__ = "control_instances"

    control_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, default=OSS_DEFAULT_TENANT_ID, index=True
    )
    system_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    obligation_id: Mapped[str] = mapped_column(String, nullable=False)
    article_ref: Mapped[str] = mapped_column(String, nullable=False)
    owner: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ttl_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_assessed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_evidence_at: Mapped[str | None] = mapped_column(String, nullable=True)
    due_at: Mapped[str | None] = mapped_column(String, nullable=True)
    waiver_rationale: Mapped[str | None] = mapped_column(String, nullable=True)
    waiver_source: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class ManifestFingerprintDB(_Base):
    __tablename__ = "manifest_fingerprints"

    tenant_id: Mapped[str] = mapped_column(
        String(128), primary_key=True, default=OSS_DEFAULT_TENANT_ID
    )
    system_id: Mapped[str] = mapped_column(String, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


#: Fields a caller may patch via `upsert_controls`, beyond the identity
#: triple (control_id/tenant_id never change once a row exists).
_PATCHABLE_FIELDS = (
    "system_id",
    "obligation_id",
    "article_ref",
    "owner",
    "state",
    "evidence_refs",
    "ttl_days",
    "last_assessed_at",
    "last_evidence_at",
    "due_at",
    "waiver_rationale",
    "waiver_source",
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_control(row: ControlInstanceDB) -> dict:
    """
    Row -> the D3 `ControlInstance` shape. Validated through
    `ControlInstance.model_validate` (rather than hand-assembled) so the API
    always emits the core-package shape, not an ad hoc ORM projection that
    could silently drift from it.
    """
    instance = ControlInstance.model_validate(
        {
            "control_id": row.control_id,
            "tenant_id": row.tenant_id,
            "system_id": row.system_id,
            "obligation_id": row.obligation_id,
            "article_ref": row.article_ref,
            "owner": row.owner,
            "state": row.state,
            "evidence_refs": row.evidence_refs,
            "ttl_days": row.ttl_days,
            "last_assessed_at": row.last_assessed_at,
            "last_evidence_at": row.last_evidence_at,
            "due_at": row.due_at,
            "waiver_rationale": row.waiver_rationale,
            "waiver_source": row.waiver_source,
        }
    )
    return instance.model_dump()


async def upsert_controls(
    session: AsyncSession,
    items: list[dict],
    tenant_id: str = OSS_DEFAULT_TENANT_ID,
) -> list[dict]:
    """
    Bulk upsert keyed on the deterministic `control_id` (D2).

    For each item: the caller may supply `control_id` explicitly; if absent
    it is computed from `tenant_id`/`system_id`/`obligation_id`. On INSERT,
    every field present in the item is taken (required D3 fields must be
    present — a `KeyError` on a missing required field means the caller sent
    an incomplete create, not a valid patch). On UPDATE of an existing row,
    only fields *present* in the incoming dict overwrite the stored value;
    fields absent from the dict leave the stored value untouched, so a
    caller can send an owner-only or state-only patch. A row's tenant can
    never change: attempting to upsert a `control_id` that already exists
    under a different tenant raises `PermissionError`, mirroring
    `hitl.upsert_review_item`.
    """
    now = _now_iso()
    rows: list[ControlInstanceDB] = []

    for item in items:
        control_id = item.get("control_id") or make_control_id(
            tenant_id, item["system_id"], item["obligation_id"]
        )
        existing = await session.get(ControlInstanceDB, control_id)
        if existing is not None and existing.tenant_id != tenant_id:
            raise PermissionError(f"control_id {control_id} belongs to another tenant")

        if existing is None:
            row = ControlInstanceDB(
                control_id=control_id,
                tenant_id=tenant_id,
                system_id=item["system_id"],
                obligation_id=item["obligation_id"],
                article_ref=item["article_ref"],
                owner=item.get("owner"),
                state=item["state"],
                evidence_refs=item.get("evidence_refs", []),
                ttl_days=item.get("ttl_days"),
                last_assessed_at=item.get("last_assessed_at"),
                last_evidence_at=item.get("last_evidence_at"),
                due_at=item.get("due_at"),
                waiver_rationale=item.get("waiver_rationale"),
                waiver_source=item.get("waiver_source"),
                updated_at=now,
            )
            session.add(row)
        else:
            for field in _PATCHABLE_FIELDS:
                if field in item:
                    setattr(existing, field, item[field])
            existing.updated_at = now
            row = existing

        rows.append(row)

    await session.flush()
    return [_row_to_control(row) for row in rows]


async def list_controls(
    session: AsyncSession,
    system_id: str,
    tenant_id: str = OSS_DEFAULT_TENANT_ID,
    state: str | None = None,
) -> list[dict]:
    stmt = select(ControlInstanceDB).where(
        ControlInstanceDB.tenant_id == tenant_id,
        ControlInstanceDB.system_id == system_id,
    )
    if state is not None:
        stmt = stmt.where(ControlInstanceDB.state == state)
    rows = (await session.execute(stmt)).scalars().all()
    return [_row_to_control(row) for row in rows]


async def get_fingerprint(
    session: AsyncSession, system_id: str, tenant_id: str = OSS_DEFAULT_TENANT_ID
) -> dict | None:
    stmt = select(ManifestFingerprintDB).where(
        ManifestFingerprintDB.tenant_id == tenant_id,
        ManifestFingerprintDB.system_id == system_id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return {"fingerprint": row.fingerprint, "updated_at": row.updated_at}


async def put_fingerprint(
    session: AsyncSession,
    system_id: str,
    fingerprint: str,
    tenant_id: str = OSS_DEFAULT_TENANT_ID,
) -> dict:
    now = _now_iso()
    existing = await session.get(ManifestFingerprintDB, (tenant_id, system_id))
    if existing is None:
        row = ManifestFingerprintDB(
            tenant_id=tenant_id,
            system_id=system_id,
            fingerprint=fingerprint,
            updated_at=now,
        )
        session.add(row)
    else:
        existing.fingerprint = fingerprint
        existing.updated_at = now
        row = existing

    await session.flush()
    return {"fingerprint": row.fingerprint, "updated_at": row.updated_at}


async def create_control_tables(engine) -> None:
    """Create control-registry tables (used in tests; production uses Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(_Base.metadata.create_all)
