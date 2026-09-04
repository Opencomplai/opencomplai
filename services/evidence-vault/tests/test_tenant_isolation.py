"""
Tenant isolation tests for evidence-vault (TEN-VAULT).

These exercise query-layer scoping on SQLite — the same level dashboard_db's
own unit tests operate at (see dashboard_db/tests/test_artifacts_dao.py).
Postgres RLS itself (the authoritative fence) is verified separately in
test_rls_postgres.py, mirroring dashboard_db's split between
test_artifacts_dao.py (SQLite, DAO-level) and test_rls_postgres.py
(Postgres, database-level).
"""

from __future__ import annotations

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opencomplai_core.service_auth import mint_service_token
from opencomplai_evidence_vault.badges import _BadgeBase
from opencomplai_evidence_vault.bias_alerts import _Base as _BiasBase
from opencomplai_evidence_vault.cas import CASStore
from opencomplai_evidence_vault.main import create_app
from opencomplai_evidence_vault.models import Base as _LedgerBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def client(tmp_path, _service_token_secret):
    db_path = tmp_path / "test-tenant-isolation.db"
    cas_path = tmp_path / "cas"
    cas_path.mkdir()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_LedgerBase.metadata.create_all)
        await conn.run_sync(_BiasBase.metadata.create_all)
        await conn.run_sync(_BadgeBase.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    app = create_app()
    app.state.engine = engine
    app.state.sessionmaker = session_factory
    app.state.cas = CASStore(str(cas_path))

    token = mint_service_token(
        "test-caller", os.environ["INTERNAL_SERVICE_TOKEN_SECRET"]
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac

    await engine.dispose()


def _headers(tenant_id: str) -> dict[str, str]:
    return {"X-Tenant-Id": tenant_id}


# ---------------------------------------------------------------------------
# Ledger: each tenant has its own independent Merkle chain
# ---------------------------------------------------------------------------


async def test_ledger_events_scoped_to_tenant(client):
    await client.post(
        "/v1/evidence/events",
        json={"event_type": "test", "payload": {"n": 1}},
        headers=_headers("tenant-a"),
    )
    await client.post(
        "/v1/evidence/events",
        json={"event_type": "test", "payload": {"n": 1}},
        headers=_headers("tenant-b"),
    )

    tips_a = (
        await client.get(
            "/v1/evidence/ledger-history-tips", headers=_headers("tenant-a")
        )
    ).json()
    tips_b = (
        await client.get(
            "/v1/evidence/ledger-history-tips", headers=_headers("tenant-b")
        )
    ).json()

    # Each tenant sees exactly its own single event, not both.
    assert tips_a["count"] == 2  # genesis + 1 event
    assert tips_b["count"] == 2


async def test_ledger_root_differs_per_tenant_after_divergent_writes(client):
    await client.post(
        "/v1/evidence/events",
        json={"event_type": "test", "payload": {"n": 1}},
        headers=_headers("tenant-a"),
    )

    root_a = (
        await client.get("/v1/evidence/ledger-root", headers=_headers("tenant-a"))
    ).json()["ledger_root_hash"]
    root_b = (
        await client.get("/v1/evidence/ledger-root", headers=_headers("tenant-b"))
    ).json()["ledger_root_hash"]

    # tenant-b's chain is still empty (genesis hash); tenant-a's has advanced.
    assert root_a != root_b


async def test_missing_tenant_header_defaults_to_oss_sentinel(client):
    # No X-Tenant-Id at all — must not error, must land in the OSS default
    # namespace rather than being rejected (TEN-VAULT is additive for OSS).
    resp = await client.post(
        "/v1/evidence/events", json={"event_type": "test", "payload": {"n": 1}}
    )
    assert resp.status_code == 201

    root_default = (await client.get("/v1/evidence/ledger-root")).json()[
        "ledger_root_hash"
    ]
    root_a = (
        await client.get("/v1/evidence/ledger-root", headers=_headers("tenant-a"))
    ).json()["ledger_root_hash"]
    assert root_default != root_a


# ---------------------------------------------------------------------------
# Dossier index: cross-tenant reads return 404, not another tenant's data
# ---------------------------------------------------------------------------


async def test_dossier_index_not_visible_across_tenants(client):
    row = {
        "dossier_id": "d-cross",
        "system_id": "sys-a",
        "commit_ref": "c1",
        "content_hash": "sha256:d-cross",
        "bundle_checksum": "sha256:d-cross-bundle",
        "ledger_event_id": "evt-d-cross",
    }
    resp = await client.post("/v1/dossiers", json=row, headers=_headers("tenant-a"))
    assert resp.status_code == 201

    # tenant-b must not see tenant-a's dossier by id.
    resp_b = await client.get("/v1/dossiers/d-cross", headers=_headers("tenant-b"))
    assert resp_b.status_code == 404

    # tenant-a still sees its own.
    resp_a = await client.get("/v1/dossiers/d-cross", headers=_headers("tenant-a"))
    assert resp_a.status_code == 200


async def test_dossier_list_by_system_scoped_to_tenant(client):
    row = {
        "dossier_id": "d-list-cross",
        "system_id": "sys-shared-name",
        "commit_ref": "c1",
        "content_hash": "sha256:d-list-cross",
        "bundle_checksum": "sha256:d-list-cross-bundle",
        "ledger_event_id": "evt-d-list-cross",
    }
    await client.post("/v1/dossiers", json=row, headers=_headers("tenant-a"))

    resp_b = await client.get(
        "/v1/dossiers",
        params={"system_id": "sys-shared-name"},
        headers=_headers("tenant-b"),
    )
    assert resp_b.json()["count"] == 0

    resp_a = await client.get(
        "/v1/dossiers",
        params={"system_id": "sys-shared-name"},
        headers=_headers("tenant-a"),
    )
    assert resp_a.json()["count"] == 1


# ---------------------------------------------------------------------------
# Badges: idempotency and lookups are per-tenant, not global
# ---------------------------------------------------------------------------

_GOOD_ARTIFACT = {
    "result": "pass",
    "pending_verifications_count": 0,
    "system_id": "sys-shared",
    "bundle_checksum": "chk-shared",
}


async def test_two_tenants_can_issue_same_badge_id_independently(client):
    """
    Two tenants issuing a badge for the same (system_id, bundle_checksum)
    produce the same badge_id digest (badge_id has no tenant component) but
    are tracked as independent rows — issuing for tenant-b must not be
    treated as "already exists" just because tenant-a already issued it.
    """
    payload = {
        "system_id": "sys-shared",
        "bundle_checksum": "chk-shared",
        "artifact": _GOOD_ARTIFACT,
    }
    resp_a = await client.post(
        "/v1/pro/badges/issue", json=payload, headers=_headers("tenant-a")
    )
    resp_b = await client.post(
        "/v1/pro/badges/issue", json=payload, headers=_headers("tenant-b")
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
    assert resp_a.json()["badge_id"] == resp_b.json()["badge_id"]
    # Both are first-time issuance for their own tenant.
    assert resp_a.json()["created"] is True
    assert resp_b.json()["created"] is True


async def test_badge_verify_not_visible_across_tenants(client):
    payload = {
        "system_id": "sys-shared",
        "bundle_checksum": "chk-shared",
        "artifact": _GOOD_ARTIFACT,
    }
    issue_resp = await client.post(
        "/v1/pro/badges/issue", json=payload, headers=_headers("tenant-a")
    )
    badge_id = issue_resp.json()["badge_id"]

    resp_b = await client.get(
        f"/v1/pro/badges/verify/{badge_id}", headers=_headers("tenant-b")
    )
    assert resp_b.status_code == 404

    resp_a = await client.get(
        f"/v1/pro/badges/verify/{badge_id}", headers=_headers("tenant-a")
    )
    assert resp_a.status_code == 200


async def test_portfolio_scoped_to_tenant(client):
    await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-portfolio-a",
            "bundle_checksum": "chk-portfolio-a",
            "artifact": {
                **_GOOD_ARTIFACT,
                "system_id": "sys-portfolio-a",
                "bundle_checksum": "chk-portfolio-a",
            },
        },
        headers=_headers("tenant-a"),
    )
    await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-portfolio-b",
            "bundle_checksum": "chk-portfolio-b",
            "artifact": {
                **_GOOD_ARTIFACT,
                "system_id": "sys-portfolio-b",
                "bundle_checksum": "chk-portfolio-b",
            },
        },
        headers=_headers("tenant-b"),
    )

    portfolio_a = (
        await client.get("/v1/portfolio", headers=_headers("tenant-a"))
    ).json()
    portfolio_b = (
        await client.get("/v1/portfolio", headers=_headers("tenant-b"))
    ).json()

    assert portfolio_a["count"] == 1
    assert portfolio_a["systems"][0]["system_id"] == "sys-portfolio-a"
    assert portfolio_b["count"] == 1
    assert portfolio_b["systems"][0]["system_id"] == "sys-portfolio-b"


# ---------------------------------------------------------------------------
# Bias alerts: count/purge scoped to tenant
# ---------------------------------------------------------------------------


async def test_bias_alert_count_scoped_to_tenant(client):
    await client.post(
        "/v1/bias-alerts",
        json={
            "alert_id": "alert-a",
            "severity": "high",
            "metric": "demographic_parity",
            "threshold": 0.1,
            "linked_event_id": "evt-1",
        },
        headers=_headers("tenant-a"),
    )

    count_a = (
        await client.get("/v1/bias-alerts/count", headers=_headers("tenant-a"))
    ).json()
    count_b = (
        await client.get("/v1/bias-alerts/count", headers=_headers("tenant-b"))
    ).json()

    assert count_a["count"] == 1
    assert count_b["count"] == 0
