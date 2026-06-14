"""
Evidence Vault FastAPI service.

Exposes endpoints for appending ledger events, storing and retrieving
evidence objects, and verifying ledger chain integrity.
"""

from __future__ import annotations

import asyncio
import base64
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response
from opencomplai_core.telemetry import configure_telemetry, metrics_response
from pydantic import BaseModel
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
from opencomplai_evidence_vault.cas import CASStore, get_cas_backend

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
    append_event,
    compute_history_tips,
    get_chain_tip,
    verify_chain,
)
from opencomplai_evidence_vault.models import Base as _LedgerBase
from opencomplai_evidence_vault.models import DossierIndexDB

configure_telemetry("evidence-vault")


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
    return Path(__file__).resolve().parents[3]


def _alembic_ini_path() -> Path:
    return _service_root() / "alembic.ini"


def _run_migrations(database_url: str) -> None:
    cfg = Config(str(_alembic_ini_path()))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async_session: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with async_session() as session:
        yield session


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
    system_id: str
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


class StoreBiasAlertRequest(BaseModel):
    alert_id: str
    severity: str
    metric: str
    threshold: float = 0.0
    linked_event_id: str
    system_id: str | None = None


class PurgeBiasDataRequest(BaseModel):
    retention_days: int = 90


class StoreObjectResponse(BaseModel):
    content_hash: str
    storage_uri: str


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

        await conn.run_sync(_BiasBase.metadata.create_all)
        await conn.run_sync(_BadgeBase.metadata.create_all)
        await conn.run_sync(_LedgerBase.metadata.create_all)

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
        version="0.1.0-dev",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "service": "evidence-vault"}

    @app.get("/metrics")
    async def metrics():
        """Prometheus text-format metrics for this service."""
        response = metrics_response()
        if response is None:
            raise HTTPException(
                status_code=503, detail="prometheus_client not installed"
            )
        return response

    @app.post(
        "/v1/evidence/events", response_model=AppendEventResponse, status_code=201
    )
    async def append_ledger_event(
        request_body: AppendEventRequest,
        session: AsyncSession = Depends(get_session),
    ) -> AppendEventResponse:
        event = await append_event(
            session=session,
            event_type=request_body.event_type,
            payload=request_body.payload,
            signer_id=request_body.signer_id,
        )
        await session.commit()
        return AppendEventResponse(
            event_id=event.event_id,
            payload_hash=event.payload_hash,
            prev_hash=event.prev_hash,
        )

    @app.get("/v1/evidence/verify-chain")
    async def verify_ledger_chain(
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        valid = await verify_chain(session)
        return {"valid": valid}

    @app.get("/v1/evidence/ledger-root")
    async def get_ledger_root(
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """
        Return the current Merkle chain tip — the hash an Annex IV dossier
        should anchor to so subsequent tampering of older events can be
        detected by comparing the dossier's recorded root against a fresh
        verify-chain run.
        """
        root = await get_chain_tip(session)
        return {"ledger_root_hash": root}

    @app.get("/v1/evidence/ledger-history-tips")
    async def get_ledger_history_tips(
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """
        Return the rolling Merkle tip after every event in the ledger.

        Used by the verify-ledger tool to confirm that a dossier's recorded
        ledger_root_hash corresponds to a real historical point in the chain.
        The response is a list of sha256:<hex> strings, one per event, plus
        the genesis hash at index 0.

        WARNING: this endpoint materialises the full chain in memory.  For
        ledgers with millions of events, add pagination or a streaming variant.
        """
        tips = await compute_history_tips(session)
        return {"tips": tips, "count": len(tips)}

    @app.post(
        "/v1/evidence/objects", response_model=StoreObjectResponse, status_code=201
    )
    async def store_evidence_object(
        request_body: StoreObjectRequest, request: Request
    ) -> StoreObjectResponse:
        try:
            content = base64.b64decode(request_body.content_base64, validate=True)
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"Invalid base64 content: {exc}"
            ) from exc

        cas: CASStore = request.app.state.cas
        content_hash = cas.write(content)
        return StoreObjectResponse(
            content_hash=content_hash,
            storage_uri=str(cas._path_for(content_hash)),
        )

    @app.get("/v1/evidence/objects/{content_hash:path}")
    async def get_evidence_object(content_hash: str, request: Request) -> dict:
        cas: CASStore = request.app.state.cas
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

    @app.post("/v1/dossiers", response_model=DossierIndexEntry, status_code=201)
    async def store_dossier_index(
        request_body: StoreDossierIndexRequest,
        session: AsyncSession = Depends(get_session),
    ) -> DossierIndexEntry:
        existing = await session.get(DossierIndexDB, request_body.dossier_id)
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
            system_id=request_body.system_id,
            commit_ref=request_body.commit_ref,
            content_hash=request_body.content_hash,
            bundle_checksum=request_body.bundle_checksum,
            ledger_event_id=request_body.ledger_event_id,
        )
        session.add(row)
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

    @app.get("/v1/dossiers/{dossier_id}", response_model=DossierIndexEntry)
    async def get_dossier_index(
        dossier_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> DossierIndexEntry:
        row = await session.get(DossierIndexDB, dossier_id)
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

    @app.get("/v1/dossiers")
    async def list_dossiers_by_system(
        system_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        stmt = (
            select(DossierIndexDB)
            .where(DossierIndexDB.system_id == system_id)
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

    @app.post("/v1/bias-alerts", status_code=201)
    async def store_bias_alert_endpoint(
        request_body: StoreBiasAlertRequest,
        session: AsyncSession = Depends(get_session),
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
        )
        await session.commit()
        return {
            "id": record.id,
            "alert_id": record.alert_id,
            "created_at": record.created_at.isoformat(),
        }

    @app.post("/v1/admin/purge-bias-data")
    async def purge_bias_data_endpoint(
        request_body: PurgeBiasDataRequest,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """
        Delete BiasAlert records older than retention_days (REQ-GTVG-002).

        Internal-only endpoint — not exposed via egress proxy or gateway.
        Appends a bias_data_purge ledger event for auditability.
        """
        deleted = await purge_expired_bias_data(session, request_body.retention_days)

        # Append purge event to the immutable ledger
        await append_event(
            session=session,
            event_type="bias_data_purge",
            payload={
                "retention_days": request_body.retention_days,
                "deleted_count": deleted,
            },
        )
        await session.commit()
        return {"deleted_count": deleted, "retention_days": request_body.retention_days}

    @app.get("/v1/bias-alerts/count")
    async def count_bias_alerts_endpoint(
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """Return count of stored BiasAlert records (used by purge verification tests)."""
        count = await count_bias_alerts(session)
        return {"count": count}

    # ------------------------------------------------------------------
    # Portfolio — distinct AI systems on record (PRD §5 — Pro)
    # ------------------------------------------------------------------

    @app.get("/v1/portfolio")
    async def portfolio_endpoint(
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """
        Return the portfolio of AI systems the vault has on record — one entry
        per distinct system_id, carrying its most recently issued compliance
        badge. Backs the dashboard portfolio view and the demo-smoke check.
        """
        stmt = select(BadgeDB).order_by(BadgeDB.system_id, BadgeDB.issued_at)
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
                "status": "compliant",
            }
            for badge in latest_by_system.values()
        ]
        systems.sort(key=lambda entry: entry["system_id"])
        return {"systems": systems, "count": len(systems)}

    # ------------------------------------------------------------------
    # Compliance badge endpoints (PRD §5 — Pro)
    # ------------------------------------------------------------------

    @app.post("/v1/pro/badges/issue", status_code=201)
    async def issue_badge_endpoint(
        request_body: IssueBadgeRequest,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """
        Issue a compliance badge for a passing ScanStatusArtifact.

        Idempotent: same (system_id, bundle_checksum) always returns the same badge.
        Blocked if result != 'pass' or pending_verifications_count != 0.
        """
        try:
            badge, created = await issue_badge(
                session=session,
                system_id=request_body.system_id,
                bundle_checksum=request_body.bundle_checksum,
                artifact=request_body.artifact,
                signature=request_body.signature,
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

    @app.get("/v1/pro/badges/verify/{badge_id:path}")
    async def verify_badge_endpoint(
        badge_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """Return badge metadata without exposing raw artifact data."""
        badge = await get_badge(session, badge_id)
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

    @app.get("/v1/pro/badges/{badge_id:path}/svg")
    async def badge_svg_endpoint(
        badge_id: str,
        session: AsyncSession = Depends(get_session),
    ) -> Response:
        """Return an SVG compliance badge asset for embedding in READMEs."""
        badge = await get_badge(session, badge_id)
        if badge is None:
            raise HTTPException(status_code=404, detail=f"Badge not found: {badge_id}")

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="200" height="20">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <rect rx="3" width="200" height="20" fill="#555"/>
  <rect rx="3" x="120" width="80" height="20" fill="#4c1"/>
  <rect rx="3" width="200" height="20" fill="url(#s)"/>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,sans-serif" font-size="11">
    <text x="60" y="15" fill="#010101" fill-opacity=".3">EU AI Act</text>
    <text x="60" y="14">EU AI Act</text>
    <text x="160" y="15" fill="#010101" fill-opacity=".3">compliant</text>
    <text x="160" y="14">compliant</text>
  </g>
  <!-- badge_id: {badge.badge_id} system: {badge.system_id} issued: {badge.issued_at} -->
</svg>"""
        return Response(content=svg, media_type="image/svg+xml")

    # ------------------------------------------------------------------
    # Pro ingest endpoints (REQ-ARC-001 — validated by egress-proxy DLP)
    # ------------------------------------------------------------------

    @app.post("/v1/pro/ingest/status-artifact", status_code=201)
    async def pro_ingest_status_artifact(
        request_body: ProIngestStatusArtifactRequest,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """Persist a ScanStatusArtifact received from the Pro dashboard ingest pipeline."""
        event = await append_event(
            session=session,
            event_type="pro_status_artifact_ingested",
            payload=request_body.model_dump(exclude_none=False),
        )
        await session.commit()
        if _METRICS_AVAILABLE:
            sid = request_body.system_id or "unknown"
            result = request_body.result or "unknown"
            _COMPLIANCE_CHECK.labels(status=result, system_id=sid).inc()
            if request_body.pending_verifications_count == 0 and result == "pass":
                _FIRST_SCAN.labels(system_id=sid).inc()
        return {"event_id": event.event_id, "payload_hash": event.payload_hash}

    @app.post("/v1/pro/ingest/dossier-metadata", status_code=201)
    async def pro_ingest_dossier_metadata(
        request_body: ProIngestDossierRequest,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """Persist dossier metadata received from the egress-proxy sync pipeline."""
        event = await append_event(
            session=session,
            event_type="pro_dossier_metadata_ingested",
            payload=request_body.model_dump(exclude_none=False),
        )
        await session.commit()
        return {"event_id": event.event_id, "payload_hash": event.payload_hash}

    @app.post("/v1/pro/ingest/metrics", status_code=201)
    async def pro_ingest_metrics(
        request_body: ProIngestMetricsRequest,
        session: AsyncSession = Depends(get_session),
    ) -> dict:
        """Persist compliance metrics received from the Pro dashboard."""
        event = await append_event(
            session=session,
            event_type="pro_metrics_ingested",
            payload=request_body.model_dump(exclude_none=False),
        )
        await session.commit()
        return {"event_id": event.event_id, "payload_hash": event.payload_hash}

    return app


app = create_app()
