"""
Tests for badge-issue signature verification (SEC-SERVICE-AUTH).

POST /v1/pro/badges/issue accepts an optional `signature` field. When
OSS_BADGE_PUBLIC_KEY_PATH is configured, that signature must verify against
the configured Ed25519 public key or issuance is rejected; when unset, the
signature is stored but not checked (OSS unsigned mode is unaffected).
"""

from __future__ import annotations

import json

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from opencomplai_core.service_auth import mint_service_token
from opencomplai_core.signing import SigningDomain, generate_keypair, sign_bundle_bytes
from opencomplai_evidence_vault.badges import _BadgeBase
from opencomplai_evidence_vault.bias_alerts import _Base as _BiasBase
from opencomplai_evidence_vault.cas import CASStore
from opencomplai_evidence_vault.main import create_app
from opencomplai_evidence_vault.models import Base as _LedgerBase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_SERVICE_TOKEN_SECRET = "evidence-vault-test-secret"


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN_SECRET", TEST_SERVICE_TOKEN_SECRET)
    db_path = tmp_path / "test-badge-sig.db"
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

    token = mint_service_token("test-caller", TEST_SERVICE_TOKEN_SECRET)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac

    await engine.dispose()


_GOOD_ARTIFACT = {
    "result": "pass",
    "pending_verifications_count": 0,
    "system_id": "sys-sig",
    "bundle_checksum": "chk-sig",
}


async def test_badge_issue_unaffected_when_no_public_key_configured(
    client, monkeypatch
):
    """OSS unsigned mode: OSS_BADGE_PUBLIC_KEY_PATH unset -> any signature value is accepted."""
    monkeypatch.delenv("OSS_BADGE_PUBLIC_KEY_PATH", raising=False)
    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-sig",
            "bundle_checksum": "chk-sig",
            "artifact": _GOOD_ARTIFACT,
            "signature": "not-even-base64!!",
        },
    )
    assert resp.status_code == 201


async def test_badge_issue_accepts_valid_signature(client, tmp_path, monkeypatch):
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setenv("OSS_BADGE_PUBLIC_KEY_PATH", str(key_dir / "signing.pub"))

    serialized = json.dumps(_GOOD_ARTIFACT, sort_keys=True).encode()
    signature = sign_bundle_bytes(
        serialized, key_dir / "signing.key", SigningDomain.BADGE
    )

    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-sig",
            "bundle_checksum": "chk-sig",
            "artifact": _GOOD_ARTIFACT,
            "signature": signature,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["created"] is True


async def test_badge_issue_rejects_invalid_signature(client, tmp_path, monkeypatch):
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setenv("OSS_BADGE_PUBLIC_KEY_PATH", str(key_dir / "signing.pub"))

    other_key_dir = tmp_path / "other-keys"
    generate_keypair(other_key_dir)
    serialized = json.dumps(_GOOD_ARTIFACT, sort_keys=True).encode()
    # Signed with a DIFFERENT key than the one evidence-vault is configured to verify against.
    wrong_signature = sign_bundle_bytes(
        serialized, other_key_dir / "signing.key", SigningDomain.BADGE
    )

    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-sig",
            "bundle_checksum": "chk-sig",
            "artifact": _GOOD_ARTIFACT,
            "signature": wrong_signature,
        },
    )
    assert resp.status_code == 422
    assert "signature" in resp.text.lower()


async def test_badge_issue_rejects_tampered_artifact(client, tmp_path, monkeypatch):
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setenv("OSS_BADGE_PUBLIC_KEY_PATH", str(key_dir / "signing.pub"))

    serialized = json.dumps(_GOOD_ARTIFACT, sort_keys=True).encode()
    signature = sign_bundle_bytes(
        serialized, key_dir / "signing.key", SigningDomain.BADGE
    )

    tampered_artifact = {**_GOOD_ARTIFACT, "result": "fail"}
    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-sig",
            "bundle_checksum": "chk-sig",
            "artifact": tampered_artifact,
            "signature": signature,
        },
    )
    # result='fail' is rejected by the pass/pending check before signature
    # verification runs, so this specific case surfaces as that error instead
    # — confirmed separately below with a tamper that keeps result='pass'.
    assert resp.status_code == 422


async def test_badge_issue_rejects_tampered_field_that_still_passes_gate(
    client, tmp_path, monkeypatch
):
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setenv("OSS_BADGE_PUBLIC_KEY_PATH", str(key_dir / "signing.pub"))

    serialized = json.dumps(_GOOD_ARTIFACT, sort_keys=True).encode()
    signature = sign_bundle_bytes(
        serialized, key_dir / "signing.key", SigningDomain.BADGE
    )

    tampered_artifact = {**_GOOD_ARTIFACT, "system_id": "sys-tampered"}
    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-sig",
            "bundle_checksum": "chk-sig",
            "artifact": tampered_artifact,
            "signature": signature,
        },
    )
    assert resp.status_code == 422
    assert "signature" in resp.text.lower()


async def test_badge_issue_requires_a_signature_when_a_key_is_configured(
    client, tmp_path, monkeypatch
):
    """
    Configuring a verification key means signatures are required.

    This inverts the behaviour a previous test pinned, deliberately. Omitting
    the signature used to skip verification entirely even with the key set, so
    anyone unable to produce a valid signature could simply leave it out — which
    made the whole verification path, and the domain separation protecting it,
    a lock on an open door.
    """
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setenv("OSS_BADGE_PUBLIC_KEY_PATH", str(key_dir / "signing.pub"))

    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-sig",
            "bundle_checksum": "chk-sig",
            "artifact": _GOOD_ARTIFACT,
        },
    )
    assert resp.status_code == 422


async def test_badge_issue_without_signature_still_works_when_no_key_configured(
    client, monkeypatch
):
    """
    OSS unsigned mode is unchanged: with no key configured, unsigned issuance
    is still supported. Only configuring a key — an explicit opt-in — makes a
    signature mandatory.
    """
    monkeypatch.delenv("OSS_BADGE_PUBLIC_KEY_PATH", raising=False)

    resp = await client.post(
        "/v1/pro/badges/issue",
        json={
            "system_id": "sys-unsigned",
            "bundle_checksum": "chk-unsigned",
            "artifact": _GOOD_ARTIFACT,
        },
    )
    assert resp.status_code == 201
