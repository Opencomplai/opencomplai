"""
Tests for compliance badge issuance and verification (PRD §5 — Pro features).

Covers:
  - Issuance blocked for non-pass result
  - Issuance blocked when pending_verifications_count != 0
  - Successful badge issuance (201, badge_id deterministic)
  - Idempotent issuance — same (system_id, bundle_checksum) returns same badge
  - Verify endpoint returns valid metadata
  - Verify 404 for unknown badge_id
  - SVG badge asset returned with correct content-type
  - Pro ingest endpoints: status-artifact, dossier-metadata, metrics
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opencomplai_evidence_vault.badges import _BadgeBase
from opencomplai_evidence_vault.bias_alerts import _Base as _BiasBase
from opencomplai_evidence_vault.cas import CASStore
from opencomplai_evidence_vault.main import create_app
from opencomplai_evidence_vault.models import Base as _LedgerBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def client(tmp_path):
    db_path = tmp_path / "test-badges.db"
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

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    await engine.dispose()


_GOOD_ARTIFACT = {
    "result": "pass",
    "pending_verifications_count": 0,
    "system_id": "sys-abc",
    "bundle_checksum": "chk-xyz",
}


# ---------------------------------------------------------------------------
# Badge issuance — blocked cases
# ---------------------------------------------------------------------------


async def test_badge_issue_blocked_for_fail_result(client):
    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-1",
            "bundle_checksum": "chk-1",
            "artifact": {**_GOOD_ARTIFACT, "result": "fail"},
        },
    )
    assert resp.status_code == 422
    assert "pass" in resp.text


async def test_badge_issue_blocked_for_pending_verifications(client):
    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-2",
            "bundle_checksum": "chk-2",
            "artifact": {**_GOOD_ARTIFACT, "pending_verifications_count": 3},
        },
    )
    assert resp.status_code == 422
    assert "pending" in resp.text.lower()


# ---------------------------------------------------------------------------
# Badge issuance — success
# ---------------------------------------------------------------------------


async def test_badge_issue_success(client):
    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-abc",
            "bundle_checksum": "chk-xyz",
            "artifact": _GOOD_ARTIFACT,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["badge_id"].startswith("sha256:")
    assert data["system_id"] == "sys-abc"
    assert data["created"] is True


async def test_badge_id_is_deterministic(client):
    payload = {
        "system_id": "sys-det",
        "bundle_checksum": "chk-det",
        "artifact": {
            **_GOOD_ARTIFACT,
            "system_id": "sys-det",
            "bundle_checksum": "chk-det",
        },
    }
    r1 = await client.post("/v1/pro/badges/issue", json=payload)
    r2 = await client.post("/v1/pro/badges/issue", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["badge_id"] == r2.json()["badge_id"]
    # Second call must be idempotent
    assert r2.json()["created"] is False


# ---------------------------------------------------------------------------
# Badge verification
# ---------------------------------------------------------------------------


async def test_badge_verify_returns_metadata(client):
    issue_resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-v",
            "bundle_checksum": "chk-v",
            "artifact": {
                **_GOOD_ARTIFACT,
                "system_id": "sys-v",
                "bundle_checksum": "chk-v",
            },
        },
    )
    assert issue_resp.status_code == 201
    badge_id = issue_resp.json()["badge_id"]

    resp = await client.get(f"/v1/pro/badges/verify/{badge_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["badge_id"] == badge_id
    assert data["system_id"] == "sys-v"
    assert data["valid"] is True


async def test_badge_verify_404_for_unknown(client):
    resp = await client.get("/v1/pro/badges/verify/sha256:deadbeef")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# SVG badge asset
# ---------------------------------------------------------------------------


async def test_badge_svg_content_type(client):
    issue_resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-svg",
            "bundle_checksum": "chk-svg",
            "artifact": {
                **_GOOD_ARTIFACT,
                "system_id": "sys-svg",
                "bundle_checksum": "chk-svg",
            },
        },
    )
    badge_id = issue_resp.json()["badge_id"]
    resp = await client.get(f"/v1/pro/badges/{badge_id}/svg")
    assert resp.status_code == 200
    assert "svg" in resp.headers["content-type"]
    assert "<svg" in resp.text
    assert badge_id in resp.text


async def test_badge_svg_404_for_unknown(client):
    resp = await client.get("/v1/pro/badges/sha256:deadbeef/svg")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Pro ingest endpoints
# ---------------------------------------------------------------------------


async def test_pro_ingest_status_artifact(client):
    resp = await client.post(
        "/v1/pro/ingest/status-artifact",
        json={
            "system_id": "sys-ingest",
            "result": "pass",
            "failed_controls": [],
            "pending_verifications_count": 0,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "event_id" in data
    assert "payload_hash" in data


async def test_pro_ingest_dossier_metadata(client):
    resp = await client.post(
        "/v1/pro/ingest/dossier-metadata",
        json={"system_id": "sys-doss", "policy_bundle_version": "1.0.0"},
    )
    assert resp.status_code == 201
    assert "event_id" in resp.json()


async def test_pro_ingest_metrics(client):
    resp = await client.post(
        "/v1/pro/ingest/metrics",
        json={"system_id": "sys-met", "pass_count": 10, "fail_count": 2},
    )
    assert resp.status_code == 201
    assert "event_id" in resp.json()
