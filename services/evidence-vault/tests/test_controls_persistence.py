"""
Tests for control-instance registry persistence routes (CTRL-STORE).

Exercises the same route-level pattern as test_hitl_persistence.py: a real
ASGI client against create_app(), SQLite-backed, confirming the bulk-upsert
patch semantics, list/filter, fingerprint round-trip, and tenant scoping.
Also includes a migration round-trip test (VERIFY-MIGRATION) that runs
migration 0007 up/down/up against a temp SQLite file and asserts the two new
tables and the four evidence_objects columns appear and disappear correctly.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from opencomplai_core.control_assessment import derive_controls
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.control_identity import make_control_id
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    ControlInstance,
    GapReport,
    GapStatus,
    SystemManifest,
)
from opencomplai_core.service_auth import mint_service_token
from opencomplai_evidence_vault.badges import _BadgeBase
from opencomplai_evidence_vault.bias_alerts import _Base as _BiasBase
from opencomplai_evidence_vault.cas import CASStore
from opencomplai_evidence_vault.controls import _Base as _ControlsBase
from opencomplai_evidence_vault.hitl import _Base as _HitlBase
from opencomplai_evidence_vault.main import create_app
from opencomplai_evidence_vault.models import Base as _LedgerBase
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def client(tmp_path, _service_token_secret):
    db_path = tmp_path / "test-controls-persistence.db"
    cas_path = tmp_path / "cas"
    cas_path.mkdir()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(_LedgerBase.metadata.create_all)
        await conn.run_sync(_BiasBase.metadata.create_all)
        await conn.run_sync(_BadgeBase.metadata.create_all)
        await conn.run_sync(_HitlBase.metadata.create_all)
        await conn.run_sync(_ControlsBase.metadata.create_all)

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


def _control_item(
    tenant_id: str = "tenant-a",
    system_id: str = "sys-1",
    obligation_id: str = "Art. 9",
    **overrides,
) -> dict:
    item = {
        "system_id": system_id,
        "obligation_id": obligation_id,
        "article_ref": "Art. 9",
        "owner": "compliance-team",
        "state": "evidence_missing",
        "evidence_refs": [],
        "ttl_days": 90,
        "last_assessed_at": None,
        "last_evidence_at": None,
        "due_at": None,
        "waiver_rationale": None,
    }
    item.update(overrides)
    return item


# ---------------------------------------------------------------------------
# Bulk upsert
# ---------------------------------------------------------------------------


async def test_bulk_upsert_creates_rows(client):
    resp = await client.put(
        "/v1/controls",
        json={"items": [_control_item()]},
        headers=_headers("tenant-a"),
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    expected_id = make_control_id("tenant-a", "sys-1", "Art. 9")
    assert items[0]["control_id"] == expected_id
    assert items[0]["tenant_id"] == "tenant-a"
    assert items[0]["state"] == "evidence_missing"
    assert items[0]["owner"] == "compliance-team"


async def test_second_identical_upsert_is_idempotent(client):
    resp1 = await client.put(
        "/v1/controls",
        json={"items": [_control_item()]},
        headers=_headers("tenant-a"),
    )
    resp2 = await client.put(
        "/v1/controls",
        json={"items": [_control_item()]},
        headers=_headers("tenant-a"),
    )
    assert resp1.status_code == resp2.status_code == 200
    ids1 = [i["control_id"] for i in resp1.json()["items"]]
    ids2 = [i["control_id"] for i in resp2.json()["items"]]
    assert ids1 == ids2

    listed = await client.get("/v1/controls/sys-1", headers=_headers("tenant-a"))
    assert len(listed.json()["items"]) == 1


async def test_owner_only_patch_keeps_state_and_evidence_refs(client):
    await client.put(
        "/v1/controls",
        json={
            "items": [
                _control_item(state="satisfied", evidence_refs=["sha256:" + "a" * 64])
            ]
        },
        headers=_headers("tenant-a"),
    )
    control_id = make_control_id("tenant-a", "sys-1", "Art. 9")

    resp = await client.put(
        "/v1/controls",
        json={
            "items": [
                {
                    "control_id": control_id,
                    "system_id": "sys-1",
                    "obligation_id": "Art. 9",
                    "owner": "new-owner",
                }
            ]
        },
        headers=_headers("tenant-a"),
    )
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["owner"] == "new-owner"
    assert item["state"] == "satisfied"
    assert item["evidence_refs"] == ["sha256:" + "a" * 64]


async def test_state_patch_keeps_owner(client):
    await client.put(
        "/v1/controls",
        json={"items": [_control_item(owner="original-owner")]},
        headers=_headers("tenant-a"),
    )
    control_id = make_control_id("tenant-a", "sys-1", "Art. 9")

    resp = await client.put(
        "/v1/controls",
        json={
            "items": [
                {
                    "control_id": control_id,
                    "system_id": "sys-1",
                    "obligation_id": "Art. 9",
                    "state": "satisfied",
                    "last_assessed_at": "2026-08-01T00:00:00+00:00",
                }
            ]
        },
        headers=_headers("tenant-a"),
    )
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["state"] == "satisfied"
    assert item["last_assessed_at"] == "2026-08-01T00:00:00+00:00"
    assert item["owner"] == "original-owner"


async def test_list_controls_filters_by_state(client):
    await client.put(
        "/v1/controls",
        json={
            "items": [
                _control_item(obligation_id="Art. 9", state="satisfied"),
                _control_item(obligation_id="Art. 10", state="evidence_missing"),
            ]
        },
        headers=_headers("tenant-a"),
    )

    resp = await client.get(
        "/v1/controls/sys-1",
        params={"state": "satisfied"},
        headers=_headers("tenant-a"),
    )
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["obligation_id"] == "Art. 9"


async def test_cross_tenant_upsert_of_same_control_id_is_rejected(client):
    await client.put(
        "/v1/controls",
        json={"items": [_control_item()]},
        headers=_headers("tenant-a"),
    )
    control_id = make_control_id("tenant-a", "sys-1", "Art. 9")

    resp = await client.put(
        "/v1/controls",
        json={
            "items": [
                {
                    "control_id": control_id,
                    "system_id": "sys-1",
                    "obligation_id": "Art. 9",
                    "article_ref": "Art. 9",
                    "state": "satisfied",
                }
            ]
        },
        headers=_headers("tenant-b"),
    )
    assert resp.status_code == 404


async def test_controls_not_visible_cross_tenant(client):
    await client.put(
        "/v1/controls",
        json={"items": [_control_item()]},
        headers=_headers("tenant-a"),
    )
    resp = await client.get("/v1/controls/sys-1", headers=_headers("tenant-b"))
    assert resp.json()["items"] == []


async def test_derive_controls_output_pushed_twice_through_put_is_idempotent(client):
    """CTRL-ASSESS end-to-end idempotency probe (VERIFY-CORE).

    Pushes the real `derive_controls` projection through the real
    `PUT /v1/controls` route twice and asserts the stored control count is
    unchanged — the same probe the CLI runs informally via `opencomplai gaps`
    twice, but here against the actual evidence-vault persistence layer
    rather than a fake in-memory vault.
    """
    manifest = SystemManifest(
        system_id="sys-derive",
        intended_purpose="credit scoring",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=True,
        commit_ref="abc123",
        training_data_description="internal loan applications 2018-2024",
        model_architecture="gradient boosted trees",
        operator_role="provider",
    )
    gap_report = GapReport(
        system_id="sys-derive",
        commit_ref="abc123",
        generated_at="2026-08-17T00:00:00+00:00",
        articles=[
            ArticleGapStatus(
                article="Art. 9",
                status=GapStatus.MET,
                source=ArticleGapSource.RULE,
                evidence_ref="RULE_ART9_RISK_MGMT",
                rationale="test fixture row",
                confidence=0.9,
                confidence_label=ConfidenceLabel.MEASURED,
            ),
            ArticleGapStatus(
                article="Art. 10",
                status=GapStatus.MISSING,
                source=ArticleGapSource.RULE,
                evidence_ref="RULE_ART10_DATA_GOV",
                rationale="test fixture row",
                confidence=None,
                confidence_label=ConfidenceLabel.NOT_ASSESSED,
            ),
        ],
    )

    derived_first = derive_controls(
        gap_report,
        manifest,
        get_catalog(),
        tenant_id="tenant-a",
        now="2026-08-17T00:00:00+00:00",
    )
    resp1 = await client.put(
        "/v1/controls",
        json={"items": [c.model_dump(mode="json") for c in derived_first]},
        headers=_headers("tenant-a"),
    )
    assert resp1.status_code == 200
    ids1 = {i["control_id"] for i in resp1.json()["items"]}
    assert len(ids1) == 2

    listed1 = await client.get("/v1/controls/sys-derive", headers=_headers("tenant-a"))
    assert len(listed1.json()["items"]) == 2

    # Round-trip through the core model so `derive_controls` sees the same
    # shape it would from a real GET /v1/controls response.
    existing_instances = [
        ControlInstance.model_validate(item) for item in listed1.json()["items"]
    ]
    derived_second = derive_controls(
        gap_report,
        manifest,
        get_catalog(),
        existing_instances,
        tenant_id="tenant-a",
        now="2026-08-17T00:00:00+00:00",
    )
    resp2 = await client.put(
        "/v1/controls",
        json={"items": [c.model_dump(mode="json") for c in derived_second]},
        headers=_headers("tenant-a"),
    )
    assert resp2.status_code == 200
    ids2 = {i["control_id"] for i in resp2.json()["items"]}
    assert ids2 == ids1

    listed2 = await client.get("/v1/controls/sys-derive", headers=_headers("tenant-a"))
    assert len(listed2.json()["items"]) == 2


# ---------------------------------------------------------------------------
# Manifest fingerprints
# ---------------------------------------------------------------------------


async def test_get_fingerprint_missing_returns_404(client):
    resp = await client.get("/v1/fingerprints/sys-1", headers=_headers("tenant-a"))
    assert resp.status_code == 404


async def test_put_then_get_fingerprint(client):
    put_resp = await client.put(
        "/v1/fingerprints/sys-1",
        json={"fingerprint": "a" * 64},
        headers=_headers("tenant-a"),
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["fingerprint"] == "a" * 64

    get_resp = await client.get("/v1/fingerprints/sys-1", headers=_headers("tenant-a"))
    assert get_resp.status_code == 200
    assert get_resp.json()["fingerprint"] == "a" * 64


async def test_put_fingerprint_overwrites_existing(client):
    await client.put(
        "/v1/fingerprints/sys-1",
        json={"fingerprint": "a" * 64},
        headers=_headers("tenant-a"),
    )
    await client.put(
        "/v1/fingerprints/sys-1",
        json={"fingerprint": "b" * 64},
        headers=_headers("tenant-a"),
    )
    resp = await client.get("/v1/fingerprints/sys-1", headers=_headers("tenant-a"))
    assert resp.json()["fingerprint"] == "b" * 64


async def test_fingerprint_not_visible_cross_tenant(client):
    await client.put(
        "/v1/fingerprints/sys-1",
        json={"fingerprint": "a" * 64},
        headers=_headers("tenant-a"),
    )
    resp = await client.get("/v1/fingerprints/sys-1", headers=_headers("tenant-b"))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Migration round-trip (VERIFY-MIGRATION)
# ---------------------------------------------------------------------------


def _service_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_migration_0007_round_trip(tmp_path, monkeypatch):
    db_path = tmp_path / "scratch-0007-round-trip.db"
    database_url = f"sqlite:///{db_path}"

    # migrations/env.py reads DATABASE_URL from the environment directly
    # (see _get_database_url), so setting sqlalchemy.url on the Config alone
    # is not enough.
    monkeypatch.setenv("DATABASE_URL", database_url)

    cfg = Config(str(_service_root() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)

    # Target 0007 explicitly: this test pins 0007's own round-trip, and
    # "head" has moved past it (0008/0009), so `downgrade -1` from head
    # would revert a different revision than the one under test.
    command.upgrade(cfg, "0007")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "control_instances" in tables
    assert "manifest_fingerprints" in tables
    evidence_columns = {c["name"] for c in inspector.get_columns("evidence_objects")}
    assert {
        "source",
        "source_version",
        "collected_at",
        "valid_until",
    } <= evidence_columns
    engine.dispose()

    command.downgrade(cfg, "-1")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "control_instances" not in tables
    assert "manifest_fingerprints" not in tables
    evidence_columns = {c["name"] for c in inspector.get_columns("evidence_objects")}
    assert not (
        {"source", "source_version", "collected_at", "valid_until"} & evidence_columns
    )
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "control_instances" in tables
    assert "manifest_fingerprints" in tables
    engine.dispose()


async def test_waiver_source_round_trips_and_can_be_cleared(client):
    await client.put(
        "/v1/controls",
        json={
            "items": [
                _control_item(
                    state="waived",
                    waiver_rationale="Out of scope.",
                    waiver_source="exclusion",
                )
            ]
        },
        headers=_headers("tenant-a"),
    )
    listed = await client.get("/v1/controls/sys-1", headers=_headers("tenant-a"))
    assert listed.json()["items"][0]["waiver_source"] == "exclusion"

    # The CLI PUTs a full dump, so a lifted waiver sends waiver_source=None.
    await client.put(
        "/v1/controls",
        json={
            "items": [
                _control_item(
                    state="evidence_missing",
                    waiver_rationale=None,
                    waiver_source=None,
                )
            ]
        },
        headers=_headers("tenant-a"),
    )
    listed = await client.get("/v1/controls/sys-1", headers=_headers("tenant-a"))
    row = listed.json()["items"][0]
    assert row["state"] == "evidence_missing"
    assert row["waiver_source"] is None


def test_migration_0010_adds_and_drops_waiver_source(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'scratch-0010.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    cfg = Config(str(_service_root() / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)

    def columns() -> set[str]:
        engine = create_engine(database_url)
        try:
            return {c["name"] for c in inspect(engine).get_columns("control_instances")}
        finally:
            engine.dispose()

    command.upgrade(cfg, "0010")
    assert "waiver_source" in columns()
    command.downgrade(cfg, "0009")
    assert "waiver_source" not in columns()
