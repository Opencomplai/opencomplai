"""
Evidence Vault FastAPI service.

Exposes endpoints for appending ledger events, storing and retrieving
evidence objects, and verifying ledger chain integrity.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape as _xml_escape

from alembic import command
from alembic.config import Config
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import Response
from opencomplai_core.telemetry import configure_telemetry, metrics_response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from opencomplai_evidence_vault.badges import (
    BadgeDB,
    _BadgeBase,
    get_badge,
    issue_badge,
)
from opencomplai_evidence_vault.bias_alerts import (
    count_bias_alerts,
    purge_expired_bias_data,
    store_bias_alert,
)
from opencomplai_evidence_vault.cas import CONTENT_HASH_RE, CASBackend, get_cas_backend
from opencomplai_evidence_vault.controls import (
    get_fingerprint,
    list_controls,
    put_fingerprint,
    upsert_controls,
)
from opencomplai_evidence_vault.hitl import (
    get_accepted_override,
    get_completed_eval,
    get_review_context,
    get_review_item,
    list_review_items,
    store_accepted_override,
    store_completed_eval,
    store_review_context,
    summarize_review_items,
    upsert_review_item,
)

try:
    from prometheus_client import Counter as _Counter

    _COMPLIANCE_CHECK = _Counter(
        "opencomplai_compliance_check_completed_total",
        "Compliance checks completed",
        ["status", "system_id"],
    )
    _BADGE_ISSUED = _Counter(
        "opencomplai_badge_issued_total",
        "Compliance badges issued",
        ["system_id"],
    )
    _DOSSIER_STORED = _Counter(
        "opencomplai_dossier_indexed_total",
        "Dossiers stored in index",
        ["system_id"],
    )
    _FIRST_SCAN = _Counter(
        "opencomplai_first_scan_completed_total",
        "First scans completed",
        ["system_id"],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False
from sqlalchemy import select

from opencomplai_evidence_vault.ledger import (
    GENESIS_HASH,
    LEDGER_TIPS_MAX_UNPAGED,
    append_event,
    compute_history_tips_page,
    get_chain_tip,
    verify_chain,
)
from opencomplai_evidence_vault.models import (
    OSS_DEFAULT_TENANT_ID,
    DossierIndexDB,
    EvidenceObjectDB,
)
from opencomplai_evidence_vault.models import Base as _LedgerBase
from opencomplai_evidence_vault.service_auth_dependency import require_service_principal

logger = logging.getLogger(__name__)

configure_telemetry("evidence-vault")


def _escape_xml(value: str) -> str:
    """Escape a value for safe interpolation into XML/SVG markup (incl. quotes)."""
    return _xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})


def _to_async_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("sqlite+aiosqlite://"):
        return database_url
    if database_url.startswith("sqlite://"):
        return database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return database_url


def _service_root() -> Path:
    # main.py lives at services/evidence-vault/src/opencomplai_evidence_vault/
    # main.py — parents[2] is services/evidence-vault, where alembic.ini and
    # migrations/ live (see infra/docker/evidence-vault.Dockerfile COPYs).
    # This was previously parents[3] (services/), which meant
    # _alembic_ini_path().exists() was always False and the
    # EVIDENCE_VAULT_AUTO_MIGRATE=1 path below silently never ran.
    return Path(__file__).resolve().parents[2]


def _alembic_ini_path() -> Path:
    return _service_root() / "alembic.ini"


def _run_migrations(database_url: str) -> None:
    cfg = Config(str(_alembic_ini_path()))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


def get_tenant_id(x_tenant_id: str | None = Header(default=None)) -> str:
    """
    Resolve the calling tenant from the X-Tenant-Id header, set by
    gateway-api's proxyToService (sourced from the gateway-verified JWT
    principal's tenant_id) or by a Python service forwarding its own
    incoming tenant_id when it calls evidence-vault directly.

    Defaults to OSS_DEFAULT_TENANT_ID when absent — the CLI's direct
    evidence-vault use and any other tenant-unaware caller land in a single
    shared OSS namespace rather than being rejected (TEN-VAULT is additive
    for OSS/self-hosted mode, not a breaking change).
    """
    if x_tenant_id is None or x_tenant_id.strip() == "":
        return OSS_DEFAULT_TENANT_ID
    return x_tenant_id


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async_session: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with async_session() as session:
        yield session


async def get_tenant_session(
    request: Request, tenant_id: str = Depends(get_tenant_id)
) -> AsyncGenerator[AsyncSession, None]:
    """
    Like get_session, but on Postgres also SET ROLEs to evidence_vault_app
    and sets the app.tenant_id GUC for the transaction, so RLS policies
    (migration 0004) enforce the fence even if a route forgets to filter by
    tenant_id explicitly. Mirrors dashboard_db.session.tenant_session.

    On SQLite (unit tests), the GUC set is a silent no-op — tenant isolation
    there is enforced purely by every DAO/route filtering on tenant_id, same
    as dashboard_db's tests rely on tests/test_rls_postgres.py to be the
    authoritative RLS check.
    """
    async_session: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with async_session() as session:
        is_postgres = (
            session.bind is not None and session.bind.dialect.name == "postgresql"
        )
        if is_postgres:
            await session.execute(text("SET ROLE evidence_vault_app"))
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": tenant_id},
            )
        try:
            yield session
        finally:
            if is_postgres:
                # SET ROLE (unlike the tenant GUC above, whose set_config
                # third argument scopes it to the transaction) is
                # session-level and survives COMMIT, and the pool's checkin
                # only issues a ROLLBACK — without an explicit reset the
                # restricted evidence_vault_app role leaks onto whichever
                # request next reuses this pooled physical connection,
                # including ones (plain sessionmaker() users like /ready)
                # that expect the connection's real default role.
                #
                # Roll back first: if the route raised mid-transaction,
                # Postgres rejects every statement except ROLLBACK/COMMIT
                # in the aborted-transaction state, and RESET ROLE would
                # mask the route's real exception with a new error.
                if session.in_transaction():
                    await session.rollback()
                await session.execute(text("RESET ROLE"))
                # RESET ROLE is itself transactional: executing it starts a
                # fresh (autobegin) transaction, and the session close that
                # follows this generator rolls that transaction back —
                # silently undoing the reset. Commit to make it stick on
                # the physical connection before it returns to the pool.
                await session.commit()


class AppendEventRequest(BaseModel):
    event_type: str
    payload: dict
    signer_id: str | None = None


class AppendEventResponse(BaseModel):
    event_id: str
    payload_hash: str
    prev_hash: str


# ---------------------------------------------------------------------------
# Pro Pydantic models — must be at module scope so FastAPI can resolve them
# under `from __future__ import annotations` (PEP 563 lazy evaluation).
# ---------------------------------------------------------------------------


class IssueBadgeRequest(BaseModel):
    # system_id is persisted verbatim and later interpolated into the badge
    # SVG (see badge_svg_endpoint) — constrain it to a safe charset here so
    # no future rendering surface has to remember to escape it correctly.
    system_id: str = Field(
        ..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$"
    )
    bundle_checksum: str
    artifact: dict
    signature: str | None = None


class ProIngestStatusArtifactRequest(BaseModel):
    system_id: str
    commit_ref: str | None = None
    result: str
    failed_controls: list[str] = []
    pending_verifications_count: int = 0
    rationale_hash: str | None = None
    bundle_checksum: str | None = None
    risk_class: str | None = None
    timestamp: str | None = None


class ProIngestDossierRequest(BaseModel):
    system_id: str
    policy_bundle_version: str | None = None
    bundle_checksum: str | None = None
    size_bytes: int | None = None
    signed_by: str | None = None
    timestamp: str | None = None


class ProIngestMetricsRequest(BaseModel):
    system_id: str
    pass_count: int | None = None
    fail_count: int | None = None
    control_pass_rate: float | None = None
    control_fail_rate: float | None = None
    trap_frequency: float | None = None
    override_rate: float | None = None
    timestamp: str | None = None


class StoreObjectRequest(BaseModel):
    content_base64: str
    source: str | None = None
    source_version: str | None = None
    collected_at: str | None = None
    valid_until: str | None = None


class StoreBiasAlertRequest(BaseModel):
    alert_id: str
    severity: str
    metric: str
    threshold: float = 0.0
    linked_event_id: str
    system_id: str | None = None


class PurgeBiasDataRequest(BaseModel):
    retention_days: int = 90


class ReviewItemUpsertRequest(BaseModel):
    """
    Upsert a review-item row. risk-engine keeps ownership of the business
    rules (round-robin group assignment, dual-approval gating, transition
    validity) and sends the fully-computed row here to persist — this
    endpoint is a durable dict replacement, not a second copy of the logic.
    """

    review_id: str
    system_id: str
    commit_ref: str
    reason: str
    state: str
    payload_ref: str
    context_ref: str
    reviewer_group: str | None = None
    assigned_to: str | None = None
    idempotency_key: str
    created_at: str
    expires_at: str | None = None
    decided_at: str | None = None
    linked_override_id: str | None = None


class ReviewContextStoreRequest(BaseModel):
    context_ref: str
    context_json: dict


class AcceptedOverrideLookupResponse(BaseModel):
    found: bool
    payload_fingerprint: str | None = None
    response_json: dict | None = None


class AcceptedOverrideStoreRequest(BaseModel):
    idempotency_key: str
    payload_fingerprint: str
    response_json: dict


class CompletedEvalLookupResponse(BaseModel):
    found: bool
    result_json: dict | None = None


class CompletedEvalStoreRequest(BaseModel):
    eval_run_id: str
    result_json: dict


class ControlItemRequest(BaseModel):
    """
    One `ControlInstance`-shaped item in a `PUT /v1/controls` bulk upsert.

    Every field is optional at the request-model level because this same
    shape carries both full creates and partial patches (owner-only,
    state-only, ...); `exclude_unset=True` at the call site is what turns
    "field omitted from the JSON body" into "field absent from the dict",
    which is the presence signal `controls.upsert_controls` patches on. A
    create that omits a field required by the core `ControlInstance` model
    (system_id/obligation_id/article_ref/state) fails at the DAO layer.
    """

    control_id: str | None = None
    system_id: str | None = None
    obligation_id: str | None = None
    article_ref: str | None = None
    owner: str | None = None
    state: str | None = None
    evidence_refs: list[str] | None = None
    ttl_days: int | None = None
    last_assessed_at: str | None = None
    last_evidence_at: str | None = None
    due_at: str | None = None
    waiver_rationale: str | None = None
    waiver_source: str | None = None


class ControlsUpsertRequest(BaseModel):
    items: list[ControlItemRequest]


class FingerprintPutRequest(BaseModel):
    fingerprint: str


class StoreObjectResponse(BaseModel):
    content_hash: str
    storage_uri: str
    source: str | None = None
    source_version: str | None = None
    collected_at: str | None = None
    valid_until: str | None = None


class StoreDossierIndexRequest(BaseModel):
    """
    Persist the lookup row for a dossier already written to CAS.

    The dossier JSON itself must already exist in the CAS at `content_hash`;
    this endpoint only records the metadata needed to find it again.
    """

    dossier_id: str
    system_id: str
    commit_ref: str
    content_hash: str
    bundle_checksum: str
    ledger_event_id: str


class DossierIndexEntry(BaseModel):
    dossier_id: str
    system_id: str
    commit_ref: str
    content_hash: str
    bundle_checksum: str
    ledger_event_id: str
    created_at: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./evidence-vault.db")
    evidence_data_dir = os.environ.get("EVIDENCE_DATA_DIR", "/tmp/evidence")
    auto_migrate = os.environ.get("EVIDENCE_VAULT_AUTO_MIGRATE", "0") == "1"

    if auto_migrate and _alembic_ini_path().exists():
        await asyncio.to_thread(_run_migrations, database_url)

    engine = create_async_engine(_to_async_database_url(database_url), echo=False)

    # Create bias_alerts, badges and dossier_index tables (non-Alembic path for dev/test).
    # dossier_index is also covered by migration 0002 for prod; create_all is idempotent.
    async with engine.begin() as conn:
        from opencomplai_evidence_vault.bias_alerts import _Base as _BiasBase
        from opencomplai_evidence_vault.controls import _Base as _ControlsBase
        from opencomplai_evidence_vault.hitl import _Base as _HitlBase

        await conn.run_sync(_BiasBase.metadata.create_all)
        await conn.run_sync(_BadgeBase.metadata.create_all)
        await conn.run_sync(_LedgerBase.metadata.create_all)
        await conn.run_sync(_HitlBase.metadata.create_all)
        await conn.run_sync(_ControlsBase.metadata.create_all)

    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.cas = get_cas_backend(evidence_data_dir)

    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Opencomplai Evidence Vault",
        description=(
            "Append-only Merkle-linked event ledger and content-addressable evidence store. "
            "Implements PRD requirements REQ-EV-001, REQ-EV-002, REQ-EV-003."
        ),
        version="0.9.1",
        lifespan=lifespan,
    )

    # Every /v1/* route requires a valid internal service token (SEC-SERVICE-AUTH) —
    # only /health, /ready and /metrics stay reachable without one, for compose/k8s
    # healthchecks and the Prometheus scraper, none of which can present a service token.
    router = APIRouter(dependencies=[Depends(require_service_principal)])

    @app.get("/health")
    async def health() -> dict:
        """Static liveness probe — kept unchanged for backward compatibility.
        Use /ready to also confirm the database is actually migrated."""
        return {"status": "ok", "service": "evidence-vault"}

    @app.get("/ready")
    async def ready(request: Request) -> dict:
        """
        Readiness probe: unlike /health this exercises the database and, on
        Postgres, confirms the evidence_vault_app role exists — the role
        migration 0004 creates and get_tenant_session SET ROLEs to on every
        /v1/* request. Without it every such request 500s with
        'role "evidence_vault_app" does not exist' even though /health still
        reports ok (issue #48, finding 11). The container's entrypoint runs
        migrations before uvicorn starts, so this is defense-in-depth for
        deployments that bypass that entrypoint.
        """
        sessionmaker = getattr(request.app.state, "sessionmaker", None)
        if sessionmaker is None:
            raise HTTPException(status_code=503, detail="database not initialized")

        try:
            async with sessionmaker() as session:
                if (
                    session.bind is not None
                    and session.bind.dialect.name == "postgresql"
                ):
                    result = await session.execute(
                        text(
                            "SELECT 1 FROM pg_roles WHERE rolname = 'evidence_vault_app'"
                        )
                    )
                    if result.scalar_one_or_none() is None:
                        raise HTTPException(
                            status_code=503,
                            detail=(
                                "evidence_vault_app role is missing - "
                                "migrations have not run (see migration 0004)"
                            ),
                        )
                    # Roles are cluster-level and survive `alembic downgrade
                    # base`, so the role existing does not prove the schema
                    # is migrated — probe a migrated table as well.
                    result = await session.execute(
                        text("SELECT to_regclass('public.ledger_events')")
                    )
                    if result.scalar_one_or_none() is None:
                        raise HTTPException(
                            status_code=503,
                            detail=(
                                "ledger_events table is missing - "
                                "migrations have not run"
                            ),
                        )
                else:
                    await session.execute(text("SELECT 1"))
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Database connectivity check failed: %s", type(exc).__name__)
            raise HTTPException(
                status_code=503,
                detail=f"database connectivity check failed: {exc.__class__.__name__}",
            ) from exc

        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics():
        """Prometheus text-format metrics for this service."""
        response = metrics_response()
        if response is None:
            raise HTTPException(
                status_code=503, detail="prometheus_client not installed"
            )
        return response

    @router.post(
        "/v1/evidence/events", response_model=AppendEventResponse, status_code=201
    )
    async def append_ledger_event(
        request_body: AppendEventRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> AppendEventResponse:
        event = await append_event(
            session=session,
            event_type=request_body.event_type,
            payload=request_body.payload,
            signer_id=request_body.signer_id,
            tenant_id=tenant_id,
        )
        await session.commit()
        return AppendEventResponse(
            event_id=event.event_id,
            payload_hash=event.payload_hash,
            prev_hash=event.prev_hash,
        )

    @router.get("/v1/evidence/verify-chain")
    async def verify_ledger_chain(
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        valid = await verify_chain(session, tenant_id=tenant_id)
        return {"valid": valid}

    @router.get("/v1/evidence/ledger-root")
    async def get_ledger_root(
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """
        Return the current Merkle chain tip — the hash an Annex IV dossier
        should anchor to so subsequent tampering of older events can be
        detected by comparing the dossier's recorded root against a fresh
        verify-chain run.
        """
        root = await get_chain_tip(session, tenant_id=tenant_id)
        return {"ledger_root_hash": root}

    @router.get("/v1/evidence/ledger-history-tips")
    async def get_ledger_history_tips(
        # le: seq is a BigInteger column; a larger value would fail in the
        # driver as a 500 rather than be rejected as bad input.
        after_seq: int | None = Query(default=None, ge=0, le=2**63 - 1),
        limit: int | None = Query(default=None, ge=1, le=5000),
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """
        Return the rolling Merkle tip after every event in the tenant's ledger.

        Used by the verify-ledger tool to confirm that a dossier's recorded
        ledger_root_hash corresponds to a real historical point in the chain.

        Without parameters the response is {"tips", "count"}: every tip as a
        list of sha256:<hex> strings, with the genesis hash at index 0. That
        list is built in memory, so a tenant with more than
        LEDGER_TIPS_MAX_UNPAGED events gets a 413 instead; page with `limit`.
        413 is kept because the request is well-formed and that status is
        already published for this case in the gateway OpenAPI document and
        the REST docs; note that it is the response, not the request content,
        that would be too large.

        With `limit` (and optionally `after_seq`, default 0) the response is
        one page: {"genesis", "tips", "count", "next_after_seq"}. `tips` holds
        the per-event tips after event `after_seq` only (the genesis hash is
        given separately), and `next_after_seq` is the cursor for the next
        page, or null on the last one.
        """
        if limit is None:
            if after_seq is not None:
                raise HTTPException(
                    status_code=422, detail="after_seq requires the limit parameter"
                )
            # Bounded read, not COUNT(*): the keyset helper fetches one event
            # past the cap, so a cursor back means "too long" and memory never
            # exceeds the cap however long the chain is.
            tips, more = await compute_history_tips_page(
                session, tenant_id, 0, limit=LEDGER_TIPS_MAX_UNPAGED
            )
            if more is not None:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"Ledger has more than {LEDGER_TIPS_MAX_UNPAGED} "
                        "events, which is more than an unpaged response may "
                        "hold. Page through it with the limit and after_seq "
                        "query parameters."
                    ),
                )
            tips = [GENESIS_HASH, *tips]
            return {"tips": tips, "count": len(tips)}

        tips, next_after_seq = await compute_history_tips_page(
            session, tenant_id, after_seq or 0, limit=limit
        )
        return {
            "genesis": GENESIS_HASH,
            "tips": tips,
            "count": len(tips),
            "next_after_seq": next_after_seq,
        }

    @router.post(
        "/v1/evidence/objects", response_model=StoreObjectResponse, status_code=201
    )
    async def store_evidence_object(
        request_body: StoreObjectRequest,
        request: Request,
        session: AsyncSession = Depends(get_tenant_session),
        principal: str = Depends(require_service_principal),
    ) -> StoreObjectResponse:
        try:
            content = base64.b64decode(request_body.content_base64, validate=True)
        except Exception as exc:
            logger.warning("Invalid base64 content received: %s", type(exc).__name__)
            raise HTTPException(
                status_code=422, detail=f"Invalid base64 content: {exc}"
            ) from exc

        cas: CASBackend = request.app.state.cas
        content_hash = cas.write(content)
        storage_uri = cas.storage_uri(content_hash)

        source = request_body.source or principal
        collected_at = request_body.collected_at or datetime.now(UTC).isoformat()
        source_version = request_body.source_version
        valid_until = request_body.valid_until

        existing_stmt = select(EvidenceObjectDB).where(
            EvidenceObjectDB.content_hash == content_hash
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing is None:
            row = EvidenceObjectDB(
                evidence_id=str(uuid4()),
                content_hash=content_hash,
                storage_uri=storage_uri,
                source=source,
                source_version=source_version,
                collected_at=collected_at,
                valid_until=valid_until,
            )
            try:
                async with session.begin_nested():
                    session.add(row)
                    await session.flush()
            except IntegrityError:
                # Concurrent request for the same content_hash won the race
                # between our existence check above and this insert.
                existing = (await session.execute(existing_stmt)).scalar_one_or_none()
                if existing is None:
                    raise
            else:
                await session.commit()
                return StoreObjectResponse(
                    content_hash=content_hash,
                    storage_uri=storage_uri,
                    source=row.source,
                    source_version=row.source_version,
                    collected_at=row.collected_at,
                    valid_until=row.valid_until,
                )

        # Same content already stored: idempotent no-op, but backfill
        # provenance on the existing row if it was never recorded.
        updated = False
        if existing.source is None and source is not None:
            existing.source = source
            updated = True
        if existing.source_version is None and source_version is not None:
            existing.source_version = source_version
            updated = True
        if existing.collected_at is None and collected_at is not None:
            existing.collected_at = collected_at
            updated = True
        if existing.valid_until is None and valid_until is not None:
            existing.valid_until = valid_until
            updated = True
        if updated:
            session.add(existing)
        await session.commit()
        return StoreObjectResponse(
            content_hash=content_hash,
            storage_uri=storage_uri,
            source=existing.source,
            source_version=existing.source_version,
            collected_at=existing.collected_at,
            valid_until=existing.valid_until,
        )

    @router.get("/v1/evidence/objects/{content_hash:path}")
    async def get_evidence_object(content_hash: str, request: Request) -> dict:
        if not CONTENT_HASH_RE.match(content_hash):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid content hash format: {content_hash!r}",
            )

        cas: CASBackend = request.app.state.cas
        try:
            content = cas.read(content_hash)
        except FileNotFoundError:
            raise HTTPException(
                status_code=404, detail=f"Evidence object not found: {content_hash}"
            ) from None
        except ValueError as exc:
            raise HTTPException(
                status_code=500, detail=f"Integrity violation: {exc}"
            ) from exc

        return {
            "content_hash": content_hash,
            "content_base64": base64.b64encode(content).decode("utf-8"),
        }

    # ------------------------------------------------------------------
    # Dossier index endpoints — lookup table for server-stored Annex IV
    # dossiers. The dossier JSON lives in the CAS at content_hash; this
    # index lets callers find it by dossier_id or system_id.
    # ------------------------------------------------------------------

    @router.post("/v1/dossiers", response_model=DossierIndexEntry, status_code=201)
    async def store_dossier_index(
        request_body: StoreDossierIndexRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> DossierIndexEntry:
        existing_stmt = select(DossierIndexDB).where(
            DossierIndexDB.dossier_id == request_body.dossier_id,
            DossierIndexDB.tenant_id == tenant_id,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            # Idempotent: same dossier_id may be re-registered with matching content.
            if (
                existing.content_hash != request_body.content_hash
                or existing.bundle_checksum != request_body.bundle_checksum
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"dossier_id {request_body.dossier_id} already exists with "
                        f"different content_hash or bundle_checksum"
                    ),
                )
            return DossierIndexEntry(
                dossier_id=existing.dossier_id,
                system_id=existing.system_id,
                commit_ref=existing.commit_ref,
                content_hash=existing.content_hash,
                bundle_checksum=existing.bundle_checksum,
                ledger_event_id=existing.ledger_event_id,
                created_at=existing.created_at.isoformat(),
            )

        row = DossierIndexDB(
            dossier_id=request_body.dossier_id,
            tenant_id=tenant_id,
            system_id=request_body.system_id,
            commit_ref=request_body.commit_ref,
            content_hash=request_body.content_hash,
            bundle_checksum=request_body.bundle_checksum,
            ledger_event_id=request_body.ledger_event_id,
        )
        try:
            async with session.begin_nested():
                session.add(row)
                await session.flush()
        except IntegrityError:
            # A concurrent request for the same dossier_id (primary key) won
            # the race between our existence check above and this insert.
            # Re-read and apply the same idempotent-vs-conflicting logic as
            # the pre-insert check, instead of surfacing a bare 500.
            existing = (await session.execute(existing_stmt)).scalar_one_or_none()
            if existing is None:
                raise
            if (
                existing.content_hash != request_body.content_hash
                or existing.bundle_checksum != request_body.bundle_checksum
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"dossier_id {request_body.dossier_id} already exists with "
                        f"different content_hash or bundle_checksum"
                    ),
                ) from None
            return DossierIndexEntry(
                dossier_id=existing.dossier_id,
                system_id=existing.system_id,
                commit_ref=existing.commit_ref,
                content_hash=existing.content_hash,
                bundle_checksum=existing.bundle_checksum,
                ledger_event_id=existing.ledger_event_id,
                created_at=existing.created_at.isoformat(),
            )
        await session.commit()
        await session.refresh(row)
        if _METRICS_AVAILABLE:
            _DOSSIER_STORED.labels(system_id=row.system_id).inc()
        return DossierIndexEntry(
            dossier_id=row.dossier_id,
            system_id=row.system_id,
            commit_ref=row.commit_ref,
            content_hash=row.content_hash,
            bundle_checksum=row.bundle_checksum,
            ledger_event_id=row.ledger_event_id,
            created_at=row.created_at.isoformat(),
        )

    @router.get("/v1/dossiers/{dossier_id}", response_model=DossierIndexEntry)
    async def get_dossier_index(
        dossier_id: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> DossierIndexEntry:
        stmt = select(DossierIndexDB).where(
            DossierIndexDB.dossier_id == dossier_id,
            DossierIndexDB.tenant_id == tenant_id,
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"Dossier not found: {dossier_id}"
            )
        return DossierIndexEntry(
            dossier_id=row.dossier_id,
            system_id=row.system_id,
            commit_ref=row.commit_ref,
            content_hash=row.content_hash,
            bundle_checksum=row.bundle_checksum,
            ledger_event_id=row.ledger_event_id,
            created_at=row.created_at.isoformat(),
        )

    @router.get("/v1/dossiers")
    async def list_dossiers_by_system(
        system_id: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        stmt = (
            select(DossierIndexDB)
            .where(
                DossierIndexDB.system_id == system_id,
                DossierIndexDB.tenant_id == tenant_id,
            )
            .order_by(DossierIndexDB.created_at.desc())
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return {
            "system_id": system_id,
            "count": len(rows),
            "dossiers": [
                DossierIndexEntry(
                    dossier_id=row.dossier_id,
                    system_id=row.system_id,
                    commit_ref=row.commit_ref,
                    content_hash=row.content_hash,
                    bundle_checksum=row.bundle_checksum,
                    ledger_event_id=row.ledger_event_id,
                    created_at=row.created_at.isoformat(),
                ).model_dump()
                for row in rows
            ],
        }

    # ------------------------------------------------------------------
    # Bias alert endpoints (REQ-GTVG-001/002)
    # ------------------------------------------------------------------

    @router.post("/v1/bias-alerts", status_code=201)
    async def store_bias_alert_endpoint(
        request_body: StoreBiasAlertRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """Persist a BiasAlert raised by the verification graph."""
        record = await store_bias_alert(
            session=session,
            alert_id=request_body.alert_id,
            severity=request_body.severity,
            metric=request_body.metric,
            threshold=request_body.threshold,
            linked_event_id=request_body.linked_event_id,
            system_id=request_body.system_id,
            tenant_id=tenant_id,
        )
        await session.commit()
        return {
            "id": record.id,
            "alert_id": record.alert_id,
            "created_at": record.created_at.isoformat(),
        }

    @router.post("/v1/admin/purge-bias-data")
    async def purge_bias_data_endpoint(
        request_body: PurgeBiasDataRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """
        Delete BiasAlert records older than retention_days (REQ-GTVG-002).

        Internal-only endpoint — not exposed via egress proxy or gateway.
        Appends a bias_data_purge ledger event for auditability.
        """
        deleted = await purge_expired_bias_data(
            session, request_body.retention_days, tenant_id=tenant_id
        )

        # Append purge event to the immutable ledger
        await append_event(
            session=session,
            event_type="bias_data_purge",
            payload={
                "retention_days": request_body.retention_days,
                "deleted_count": deleted,
            },
            tenant_id=tenant_id,
        )
        await session.commit()
        return {"deleted_count": deleted, "retention_days": request_body.retention_days}

    @router.get("/v1/bias-alerts/count")
    async def count_bias_alerts_endpoint(
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """Return count of stored BiasAlert records (used by purge verification tests)."""
        count = await count_bias_alerts(session, tenant_id=tenant_id)
        return {"count": count}

    # ------------------------------------------------------------------
    # HITL review-queue, override-idempotency, and eval-cache persistence
    # (PERSIST-RISK) — risk-engine's durable backing store. risk-engine
    # keeps its own business logic (assignment, dual-approval, conflict
    # checks) and calls these endpoints instead of process-local dicts.
    # ------------------------------------------------------------------

    @router.put("/v1/hitl/review-items", status_code=200)
    async def upsert_review_item_endpoint(
        request_body: ReviewItemUpsertRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        try:
            item = await upsert_review_item(
                session, request_body.model_dump(), tenant_id=tenant_id
            )
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        await session.commit()
        return {"item": item}

    @router.get("/v1/hitl/review-items")
    async def list_review_items_endpoint(
        state: str | None = None,
        assigned_to: str | None = None,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        items = await list_review_items(
            session, tenant_id=tenant_id, state=state, assigned_to=assigned_to
        )
        return {"items": items}

    # Declared before /v1/hitl/review-items/{review_id}: FastAPI resolves
    # paths in declaration order, so the parametrised route would otherwise
    # swallow "summary" as a review_id and always 404.
    @router.get("/v1/hitl/review-items/summary")
    async def summarize_review_items_endpoint(
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        return await summarize_review_items(session, tenant_id=tenant_id)

    @router.get("/v1/hitl/review-items/{review_id}")
    async def get_review_item_endpoint(
        review_id: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        item = await get_review_item(session, review_id, tenant_id=tenant_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Review item not found")
        return {"item": item}

    @router.post("/v1/hitl/review-contexts", status_code=201)
    async def store_review_context_endpoint(
        request_body: ReviewContextStoreRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        await store_review_context(
            session,
            request_body.context_ref,
            request_body.context_json,
            tenant_id=tenant_id,
        )
        await session.commit()
        return {"context_ref": request_body.context_ref}

    @router.get("/v1/hitl/review-contexts/{context_ref}")
    async def get_review_context_endpoint(
        context_ref: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        context_json = await get_review_context(
            session, context_ref, tenant_id=tenant_id
        )
        if context_json is None:
            raise HTTPException(status_code=404, detail="Review context not found")
        return {"context_json": context_json}

    @router.get(
        "/v1/hitl/overrides/{idempotency_key}",
        response_model=AcceptedOverrideLookupResponse,
    )
    async def lookup_accepted_override_endpoint(
        idempotency_key: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> AcceptedOverrideLookupResponse:
        cached = await get_accepted_override(
            session, idempotency_key, tenant_id=tenant_id
        )
        if cached is None:
            return AcceptedOverrideLookupResponse(found=False)
        fingerprint, response_json = cached
        return AcceptedOverrideLookupResponse(
            found=True, payload_fingerprint=fingerprint, response_json=response_json
        )

    @router.post("/v1/hitl/overrides", status_code=201)
    async def store_accepted_override_endpoint(
        request_body: AcceptedOverrideStoreRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        await store_accepted_override(
            session,
            request_body.idempotency_key,
            request_body.payload_fingerprint,
            request_body.response_json,
            tenant_id=tenant_id,
        )
        await session.commit()
        return {"idempotency_key": request_body.idempotency_key}

    @router.get(
        "/v1/evals/cache/{eval_run_id}", response_model=CompletedEvalLookupResponse
    )
    async def lookup_completed_eval_endpoint(
        eval_run_id: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> CompletedEvalLookupResponse:
        result_json = await get_completed_eval(
            session, eval_run_id, tenant_id=tenant_id
        )
        if result_json is None:
            return CompletedEvalLookupResponse(found=False)
        return CompletedEvalLookupResponse(found=True, result_json=result_json)

    @router.post("/v1/evals/cache", status_code=201)
    async def store_completed_eval_endpoint(
        request_body: CompletedEvalStoreRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        await store_completed_eval(
            session,
            request_body.eval_run_id,
            request_body.result_json,
            tenant_id=tenant_id,
        )
        await session.commit()
        return {"eval_run_id": request_body.eval_run_id}

    # ------------------------------------------------------------------
    # Control instance registry persistence (CTRL-STORE) — evidence-vault
    # is the durable home for control instances per D1. Identity is the
    # deterministic control_id (D2); manifest_fingerprints tracks the last
    # manifest fingerprint seen per (tenant, system) (D5).
    # ------------------------------------------------------------------

    @router.put("/v1/controls")
    async def upsert_controls_endpoint(
        request_body: ControlsUpsertRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        items = [item.model_dump(exclude_unset=True) for item in request_body.items]
        try:
            result = await upsert_controls(session, items, tenant_id=tenant_id)
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        await session.commit()
        return {"items": result}

    @router.get("/v1/controls/{system_id}")
    async def list_controls_endpoint(
        system_id: str,
        state: str | None = None,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        items = await list_controls(
            session, system_id, tenant_id=tenant_id, state=state
        )
        return {"items": items}

    @router.get("/v1/fingerprints/{system_id}")
    async def get_fingerprint_endpoint(
        system_id: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        result = await get_fingerprint(session, system_id, tenant_id=tenant_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Fingerprint not found")
        return result

    @router.put("/v1/fingerprints/{system_id}")
    async def put_fingerprint_endpoint(
        system_id: str,
        request_body: FingerprintPutRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        result = await put_fingerprint(
            session, system_id, request_body.fingerprint, tenant_id=tenant_id
        )
        await session.commit()
        return result

    # ------------------------------------------------------------------
    # Portfolio — distinct AI systems on record (PRD §5 — Pro)
    # ------------------------------------------------------------------

    @router.get("/v1/portfolio")
    async def portfolio_endpoint(
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """
        Return the portfolio of AI systems the vault has on record — one entry
        per distinct system_id, carrying its most recently issued badge
        (status ``scan_passed``: the scan passed with no pending verifications). Backs the dashboard portfolio view and the demo-smoke check.
        """
        stmt = (
            select(BadgeDB)
            .where(BadgeDB.tenant_id == tenant_id)
            .order_by(BadgeDB.system_id, BadgeDB.issued_at)
        )
        badges = (await session.execute(stmt)).scalars().all()

        # Rows are ordered by issued_at ascending, so the last write per
        # system_id wins — i.e. the most recently issued badge.
        latest_by_system: dict[str, BadgeDB] = {}
        for badge in badges:
            latest_by_system[badge.system_id] = badge

        systems = [
            {
                "system_id": badge.system_id,
                "badge_id": badge.badge_id,
                "bundle_checksum": badge.bundle_checksum,
                "issued_at": badge.issued_at,
                "status": "scan_passed",
            }
            for badge in latest_by_system.values()
        ]
        systems.sort(key=lambda entry: entry["system_id"])
        return {"systems": systems, "count": len(systems)}

    # ------------------------------------------------------------------
    # Compliance badge endpoints (PRD §5 — Pro)
    # ------------------------------------------------------------------

    @router.post("/v1/pro/badges/issue", status_code=201)
    async def issue_badge_endpoint(
        request_body: IssueBadgeRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """
        Issue a compliance badge for a passing ScanStatusArtifact.

        Idempotent: same (tenant_id, system_id, bundle_checksum) always
        returns the same badge. Blocked if result != 'pass' or
        pending_verifications_count != 0.
        """
        try:
            badge, created = await issue_badge(
                session=session,
                system_id=request_body.system_id,
                bundle_checksum=request_body.bundle_checksum,
                artifact=request_body.artifact,
                signature=request_body.signature,
                tenant_id=tenant_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        await session.commit()
        if _METRICS_AVAILABLE and created:
            _BADGE_ISSUED.labels(system_id=badge.system_id).inc()
        return {
            "badge_id": badge.badge_id,
            "system_id": badge.system_id,
            "issued_at": badge.issued_at,
            "status_artifact_hash": badge.status_artifact_hash,
            "created": created,
        }

    @router.get("/v1/pro/badges/verify/{badge_id:path}")
    async def verify_badge_endpoint(
        badge_id: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """Return badge metadata without exposing raw artifact data."""
        badge = await get_badge(session, badge_id, tenant_id=tenant_id)
        if badge is None:
            raise HTTPException(status_code=404, detail=f"Badge not found: {badge_id}")
        return {
            "badge_id": badge.badge_id,
            "system_id": badge.system_id,
            "bundle_checksum": badge.bundle_checksum,
            "issued_at": badge.issued_at,
            "status_artifact_hash": badge.status_artifact_hash,
            "valid": True,
        }

    @router.get("/v1/pro/badges/{badge_id:path}/svg")
    async def badge_svg_endpoint(
        badge_id: str,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> Response:
        """Return an SVG scan-passed badge asset for embedding in READMEs."""
        badge = await get_badge(session, badge_id, tenant_id=tenant_id)
        if badge is None:
            raise HTTPException(status_code=404, detail=f"Badge not found: {badge_id}")

        # Every field below is attacker-influenced (system_id comes straight
        # from the issue request) and lands inside an HTML comment in a
        # document served as image/svg+xml — escape unconditionally so a
        # "-->" breakout can never inject live markup/script.
        safe_badge_id = _escape_xml(badge.badge_id)
        safe_system_id = _escape_xml(badge.system_id)
        safe_issued_at = _escape_xml(badge.issued_at)

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="20">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect rx="3" width="200" height="20" fill="#555"/>
  <rect rx="3" x="120" width="80" height="20" fill="#4c1"/>
  <rect rx="3" width="200" height="20" fill="url(#s)"/>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,sans-serif" font-size="11">
    <text x="60" y="15" fill="#010101" fill-opacity=".3">OpenComplAI</text>
    <text x="60" y="14">OpenComplAI</text>
    <text x="160" y="15" fill="#010101" fill-opacity=".3">scan passed</text>
    <text x="160" y="14">scan passed</text>
  </g>
  <!-- badge_id: {safe_badge_id} system: {safe_system_id} issued: {safe_issued_at} -->
</svg>"""
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={
                "Content-Security-Policy": "default-src 'none'; script-src 'none'",
                "X-Content-Type-Options": "nosniff",
            },
        )

    # ------------------------------------------------------------------
    # Pro ingest endpoints (REQ-ARC-001 — validated by egress-proxy DLP)
    # ------------------------------------------------------------------

    @router.post("/v1/pro/ingest/status-artifact", status_code=201)
    async def pro_ingest_status_artifact(
        request_body: ProIngestStatusArtifactRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """Persist a ScanStatusArtifact received from the Pro dashboard ingest pipeline."""
        event = await append_event(
            session=session,
            event_type="pro_status_artifact_ingested",
            payload=request_body.model_dump(exclude_none=False),
            tenant_id=tenant_id,
        )
        await session.commit()
        if _METRICS_AVAILABLE:
            sid = request_body.system_id or "unknown"
            result = request_body.result or "unknown"
            _COMPLIANCE_CHECK.labels(status=result, system_id=sid).inc()
            if request_body.pending_verifications_count == 0 and result == "pass":
                _FIRST_SCAN.labels(system_id=sid).inc()
        return {"event_id": event.event_id, "payload_hash": event.payload_hash}

    @router.post("/v1/pro/ingest/dossier-metadata", status_code=201)
    async def pro_ingest_dossier_metadata(
        request_body: ProIngestDossierRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """Persist dossier metadata received from the egress-proxy sync pipeline."""
        event = await append_event(
            session=session,
            event_type="pro_dossier_metadata_ingested",
            payload=request_body.model_dump(exclude_none=False),
            tenant_id=tenant_id,
        )
        await session.commit()
        return {"event_id": event.event_id, "payload_hash": event.payload_hash}

    @router.post("/v1/pro/ingest/metrics", status_code=201)
    async def pro_ingest_metrics(
        request_body: ProIngestMetricsRequest,
        session: AsyncSession = Depends(get_tenant_session),
        tenant_id: str = Depends(get_tenant_id),
    ) -> dict:
        """Persist compliance metrics received from the Pro dashboard."""
        event = await append_event(
            session=session,
            event_type="pro_metrics_ingested",
            payload=request_body.model_dump(exclude_none=False),
            tenant_id=tenant_id,
        )
        await session.commit()
        return {"event_id": event.event_id, "payload_hash": event.payload_hash}

    app.include_router(router)
    return app


app = create_app()
