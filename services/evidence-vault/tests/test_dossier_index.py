"""Tests for the dossier index endpoints (closes Gap #2 from the self-audit)."""

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
    db_path = tmp_path / "test-dossier-index.db"
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


def _row(dossier_id: str, system_id: str = "sys-a", commit_ref: str = "c1") -> dict:
    return {
        "dossier_id": dossier_id,
        "system_id": system_id,
        "commit_ref": commit_ref,
        "content_hash": f"sha256:{dossier_id}",
        "bundle_checksum": f"sha256:{dossier_id}-bundle",
        "ledger_event_id": f"evt-{dossier_id}",
    }


async def test_store_and_get_dossier_by_id(client):
    resp = await client.post("/v1/dossiers", json=_row("d1"))
    assert resp.status_code == 201
    assert resp.json()["dossier_id"] == "d1"

    resp = await client.get("/v1/dossiers/d1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "sys-a"
    assert body["content_hash"] == "sha256:d1"
    assert body["ledger_event_id"] == "evt-d1"


async def test_get_dossier_404_for_unknown(client):
    resp = await client.get("/v1/dossiers/does-not-exist")
    assert resp.status_code == 404


async def test_store_is_idempotent_for_same_content(client):
    payload = _row("d2")
    first = await client.post("/v1/dossiers", json=payload)
    second = await client.post("/v1/dossiers", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["dossier_id"] == second.json()["dossier_id"]


async def test_store_conflict_on_mismatched_content(client):
    await client.post("/v1/dossiers", json=_row("d3"))
    conflicting = _row("d3")
    conflicting["content_hash"] = "sha256:tampered"
    resp = await client.post("/v1/dossiers", json=conflicting)
    assert resp.status_code == 409


async def test_list_dossiers_by_system_id(client):
    await client.post("/v1/dossiers", json=_row("d4", system_id="sys-x"))
    await client.post(
        "/v1/dossiers", json=_row("d5", system_id="sys-x", commit_ref="c2")
    )
    await client.post("/v1/dossiers", json=_row("d6", system_id="sys-y"))

    resp = await client.get("/v1/dossiers", params={"system_id": "sys-x"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "sys-x"
    assert body["count"] == 2
    ids = {entry["dossier_id"] for entry in body["dossiers"]}
    assert ids == {"d4", "d5"}


async def test_list_dossiers_returns_empty_for_unknown_system(client):
    resp = await client.get("/v1/dossiers", params={"system_id": "no-such-system"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["dossiers"] == []
