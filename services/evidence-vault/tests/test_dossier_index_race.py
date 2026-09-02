"""
PERSIST-RACES: dossier-index idempotent-insert race.

store_dossier_index's existence check and insert are not atomic — a
concurrent request for the same dossier_id (the primary key) can commit its
row in the window between our existence check and our own insert. Before
this fix that raised an unhandled IntegrityError (a bare 500) instead of
applying the same idempotent-vs-conflicting logic the pre-insert check
already implements.

Reproduced deterministically end-to-end through the real route: the first
`AsyncSession.execute` call in the request (the route's own pre-insert
existence check) is monkeypatched to report "not found" exactly once, so the
insert itself is what collides with a row committed just before — same
technique as test_badges_race.py, applied at the HTTP layer since
store_dossier_index's except branch also re-runs a second query and returns
an HTTP response shape worth asserting on directly.
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
from opencomplai_evidence_vault.models import OSS_DEFAULT_TENANT_ID, DossierIndexDB
from opencomplai_evidence_vault.models import Base as _LedgerBase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def env(tmp_path, _service_token_secret):
    db_path = tmp_path / "test-dossier-race.db"
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
        yield ac, session_factory

    await engine.dispose()


async def test_store_dossier_index_recovers_via_reread_on_pk_collision(
    env, monkeypatch
):
    client, session_factory = env
    row = {
        "dossier_id": "d-race",
        "system_id": "sys-a",
        "commit_ref": "c1",
        "content_hash": "sha256:d-race",
        "bundle_checksum": "sha256:d-race-bundle",
        "ledger_event_id": "evt-d-race",
    }

    # A concurrent writer commits the identical row directly, simulating it
    # winning the race in the window between our route's existence check and
    # its own insert.
    async with session_factory() as winner_session:
        winner_session.add(
            DossierIndexDB(
                dossier_id=row["dossier_id"],
                tenant_id=OSS_DEFAULT_TENANT_ID,
                system_id=row["system_id"],
                commit_ref=row["commit_ref"],
                content_hash=row["content_hash"],
                bundle_checksum=row["bundle_checksum"],
                ledger_event_id=row["ledger_event_id"],
            )
        )
        await winner_session.commit()

    # Make the *next* AsyncSession.execute call anywhere (the route's own
    # pre-insert existence check, the first query it runs) report "not
    # found", so its subsequent insert is what collides with `winner`.
    real_execute = AsyncSession.execute
    state = {"blinded": False}

    async def _blind_once(self, stmt, *args, **kwargs):
        if not state["blinded"]:
            state["blinded"] = True

            class _EmptyResult:
                def scalar_one_or_none(self) -> None:
                    return None

            return _EmptyResult()
        return await real_execute(self, stmt, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", _blind_once)

    resp = await client.post("/v1/dossiers", json=row)

    assert resp.status_code == 201
    assert resp.json()["dossier_id"] == "d-race"
    assert resp.json()["content_hash"] == "sha256:d-race"

    async with session_factory() as verify_session:
        result = await verify_session.execute(
            select(DossierIndexDB).where(DossierIndexDB.dossier_id == "d-race")
        )
        rows = result.scalars().all()
        assert len(rows) == 1  # no duplicate row from the race
