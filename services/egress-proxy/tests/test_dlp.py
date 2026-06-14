"""
DLP test suite for egress-proxy allowlist enforcement (REQ-ARC-001).

Acceptance criteria:
  - 0 forbidden fields reach any external destination.
  - EGRESS_BLOCKED response (403) for any forbidden field or disallowed destination.
  - Conformant payloads return 2xx.
  - Empty allowlist blocks all sync requests to configured destinations.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_egress_proxy.allowlist import (
    ALLOWED_FIELDS,
    validate_destination,
    validate_payload,
)
from opencomplai_egress_proxy.main import app

# ---------------------------------------------------------------------------
# validate_payload unit tests
# ---------------------------------------------------------------------------


def test_validate_payload_all_allowed_fields() -> None:
    payload = {
        "system_id": "sys-1",
        "risk_class": "minimal",
        "pass_count": 10,
        "fail_count": 0,
    }
    allowed, forbidden = validate_payload(payload)
    assert allowed is True
    assert forbidden == []


def test_validate_payload_forbidden_field() -> None:
    payload = {"system_id": "sys-1", "raw_inference_payload": "secret data"}
    allowed, forbidden = validate_payload(payload)
    assert allowed is False
    assert "raw_inference_payload" in forbidden


def test_validate_payload_empty_payload_is_allowed() -> None:
    allowed, forbidden = validate_payload({})
    assert allowed is True
    assert forbidden == []


def test_validate_payload_multiple_forbidden_fields() -> None:
    payload = {
        "system_id": "ok",
        "model_weights": "secret",
        "training_data": "secret",
    }
    allowed, forbidden = validate_payload(payload)
    assert allowed is False
    assert set(forbidden) == {"model_weights", "training_data"}


def test_allowed_fields_covers_prd_schema() -> None:
    required_prd_fields = {
        "system_id",
        "commit_ref",
        "policy_bundle_version",
        "risk_class",
        "control_pass_rate",
        "control_fail_rate",
        "pending_verifications_count",
        "bundle_checksum",
        "size_bytes",
        "signed_by",
        "timestamp",
        "pass_count",
        "fail_count",
        "trap_frequency",
        "override_rate",
    }
    assert required_prd_fields <= ALLOWED_FIELDS


# ---------------------------------------------------------------------------
# validate_destination unit tests
# ---------------------------------------------------------------------------


def test_validate_destination_allowed(monkeypatch) -> None:
    monkeypatch.setenv("EGRESS_ALLOWLIST", "https://dashboard.opencomplai.com")
    assert validate_destination("https://dashboard.opencomplai.com/ingest") is True


def test_validate_destination_not_allowed(monkeypatch) -> None:
    monkeypatch.setenv("EGRESS_ALLOWLIST", "https://dashboard.opencomplai.com")
    assert validate_destination("https://evil.example.com/exfil") is False


def test_validate_destination_empty_allowlist_blocks_all(monkeypatch) -> None:
    monkeypatch.delenv("EGRESS_ALLOWLIST", raising=False)
    assert validate_destination("https://anywhere.example.com") is False


def test_validate_destination_multiple_prefixes(monkeypatch) -> None:
    monkeypatch.setenv(
        "EGRESS_ALLOWLIST", "https://a.example.com\nhttps://b.example.com"
    )
    assert validate_destination("https://a.example.com/api") is True
    assert validate_destination("https://b.example.com/api") is True
    assert validate_destination("https://c.example.com/api") is False


# ---------------------------------------------------------------------------
# /v1/sync/metadata endpoint integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_metadata_conformant_payload_returns_200(monkeypatch) -> None:
    """Payload with only allowed fields → 200, no block."""
    monkeypatch.delenv("PRO_DASHBOARD_URL", raising=False)
    payload = {
        "system_id": "sys-1",
        "risk_class": "minimal",
        "pass_count": 5,
        "fail_count": 0,
        "pending_verifications_count": 0,
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/sync/metadata", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["fields_validated"] is True
    assert data["status"] == "synced"


@pytest.mark.asyncio
async def test_sync_metadata_forbidden_field_returns_403(monkeypatch) -> None:
    """Payload with forbidden field → 403 EGRESS_BLOCKED (0 forbidden fields egress)."""
    monkeypatch.delenv("PRO_DASHBOARD_URL", raising=False)
    payload = {
        "system_id": "sys-1",
        "raw_inference_payload": "this must never leave the local boundary",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/sync/metadata", json=payload)
    assert response.status_code == 403
    data = response.json()
    assert data["error_code"] == "EGRESS_BLOCKED"
    assert data["retryable"] is False


@pytest.mark.asyncio
async def test_sync_metadata_model_weights_blocked(monkeypatch) -> None:
    """Model weights must never egress."""
    monkeypatch.delenv("PRO_DASHBOARD_URL", raising=False)
    payload = {"system_id": "sys-1", "model_weights_path": "/data/model.bin"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/sync/metadata", json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sync_metadata_disallowed_destination_returns_403(monkeypatch) -> None:
    """Non-allowlisted destination → 403 even with conformant payload."""
    monkeypatch.setenv("PRO_DASHBOARD_URL", "https://evil.example.com")
    monkeypatch.setenv("EGRESS_ALLOWLIST", "https://dashboard.opencomplai.com")
    payload = {"system_id": "sys-1", "risk_class": "minimal"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/sync/metadata", json=payload)
    assert response.status_code == 403
    assert response.json()["error_code"] == "EGRESS_BLOCKED"


@pytest.mark.asyncio
async def test_sync_metadata_empty_allowlist_blocks_configured_destination(
    monkeypatch,
) -> None:
    """Empty EGRESS_ALLOWLIST → all configured destinations are blocked."""
    monkeypatch.setenv("PRO_DASHBOARD_URL", "https://dashboard.opencomplai.com")
    monkeypatch.delenv("EGRESS_ALLOWLIST", raising=False)
    payload = {"system_id": "sys-1", "risk_class": "minimal"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/sync/metadata", json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_sync_metadata_non_json_body_returns_422(monkeypatch) -> None:
    monkeypatch.delenv("PRO_DASHBOARD_URL", raising=False)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/sync/metadata",
            content=b"not-json",
            headers={"Content-Type": "text/plain"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_egress_health_returns_200() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/egress-health")
    assert response.status_code == 200
    assert response.json()["service"] == "egress-proxy"


# ---------------------------------------------------------------------------
# Zero-forbidden-fields invariant (DLP smoke test)
# ---------------------------------------------------------------------------


def test_zero_forbidden_fields_in_allowed_set() -> None:
    """
    Exhaustive check: no field in ALLOWED_FIELDS is a sensitive data field.

    This test encodes the DLP invariant: ALLOWED_FIELDS must never contain
    fields that carry raw evidence, model weights, training data, or
    identity-bearing personal data.
    """
    sensitive_keywords = {
        "weight",
        "dataset",
        "training",
        "inference",
        "payload",
        "personal",
        "pseudonym",
        "special_category",
        "raw",
        "full_log",
    }
    for field in ALLOWED_FIELDS:
        for kw in sensitive_keywords:
            assert kw not in field.lower(), (
                f"ALLOWED_FIELDS contains potentially sensitive field '{field}' "
                f"(matches keyword '{kw}'). Review before allowlisting."
            )
