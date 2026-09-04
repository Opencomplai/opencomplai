"""Tests for compliance checker HTTP routes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from opencomplai_risk_engine import checker_routes
from opencomplai_risk_engine.mailer import MailerNotConfiguredError
from opencomplai_risk_engine.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Each test gets clean rate-limit buckets — TestClient reuses one fake IP."""
    limiters = (
        checker_routes._EMAIL_RATE_LIMITER,
        checker_routes._EXPORT_RATE_LIMITER,
        checker_routes._EVALUATE_RATE_LIMITER,
    )
    for limiter in limiters:
        limiter.clear()
    yield
    for limiter in limiters:
        limiter.clear()


FIXTURES = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "core"
    / "tests"
    / "fixtures"
    / "checker_golden"
)


def test_checker_evaluate_matches_golden() -> None:
    fixture = json.loads(
        (FIXTURES / "06_high_risk_provider.json").read_text(encoding="utf-8")
    )
    resp = client.post("/v1/checker/evaluate", json=fixture["session"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_high_risk"] is True
    assert data["effective_entity"] == "provider"


def test_checker_help_returns_sections() -> None:
    resp = client.get("/v1/checker/help")
    assert resp.status_code == 200
    body = resp.json()
    assert "sections" in body
    assert "disclaimer" in body


def test_checker_export_markdown() -> None:
    fixture = json.loads(
        (FIXTURES / "01_auth_rep_only.json").read_text(encoding="utf-8")
    )
    resp = client.post(
        "/v1/checker/export",
        json={"answers": fixture["session"]["answers"], "format": "md"},
    )
    assert resp.status_code == 200
    assert "EU AI Act Compliance Checker Result" in resp.text


def test_checker_email_sends_pdf_to_valid_address() -> None:
    fixture = json.loads(
        (FIXTURES / "01_auth_rep_only.json").read_text(encoding="utf-8")
    )
    with patch.object(checker_routes, "send_pdf_email") as mock_send:
        resp = client.post(
            "/v1/checker/email",
            json={
                "answers": fixture["session"]["answers"],
                "to_email": "user@example.com",
            },
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"sent": True}
    assert mock_send.call_count == 1
    assert mock_send.call_args.kwargs["to_email"] == "user@example.com"
    assert isinstance(mock_send.call_args.kwargs["pdf_bytes"], bytes)


def test_checker_email_rejects_invalid_address() -> None:
    with patch.object(checker_routes, "send_pdf_email") as mock_send:
        resp = client.post(
            "/v1/checker/email",
            json={"answers": {}, "to_email": "not-an-email"},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error_code"] == "VALIDATION_ERROR"
    mock_send.assert_not_called()


def test_checker_email_returns_503_when_mailer_not_configured() -> None:
    with patch.object(
        checker_routes,
        "send_pdf_email",
        side_effect=MailerNotConfiguredError("no host"),
    ):
        resp = client.post(
            "/v1/checker/email",
            json={"answers": {}, "to_email": "user@example.com"},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"]["error_code"] == "MAILER_NOT_CONFIGURED"


def test_checker_email_is_rate_limited_per_ip() -> None:
    with patch.object(checker_routes, "send_pdf_email"):
        limit = checker_routes._EMAIL_RATE_LIMITER._max_requests
        for _ in range(limit):
            resp = client.post(
                "/v1/checker/email",
                json={"answers": {}, "to_email": "user@example.com"},
            )
            assert resp.status_code == 200
        resp = client.post(
            "/v1/checker/email",
            json={"answers": {}, "to_email": "user@example.com"},
        )
    assert resp.status_code == 429
    assert resp.json()["detail"]["error_code"] == "RATE_LIMITED"


def test_checker_export_is_rate_limited_per_ip() -> None:
    fixture = json.loads(
        (FIXTURES / "01_auth_rep_only.json").read_text(encoding="utf-8")
    )
    limit = checker_routes._EXPORT_RATE_LIMITER._max_requests
    for _ in range(limit):
        resp = client.post(
            "/v1/checker/export",
            json={"answers": fixture["session"]["answers"], "format": "json"},
        )
        assert resp.status_code == 200
    resp = client.post(
        "/v1/checker/export",
        json={"answers": fixture["session"]["answers"], "format": "json"},
    )
    assert resp.status_code == 429
    assert resp.json()["detail"]["error_code"] == "RATE_LIMITED"


def test_checker_evaluate_is_rate_limited_per_ip() -> None:
    limit = checker_routes._EVALUATE_RATE_LIMITER._max_requests
    for _ in range(limit):
        resp = client.post("/v1/checker/evaluate", json={"answers": {}})
        assert resp.status_code == 200
    resp = client.post("/v1/checker/evaluate", json={"answers": {}})
    assert resp.status_code == 429
    assert resp.json()["detail"]["error_code"] == "RATE_LIMITED"


def test_checker_export_rejects_too_many_answers() -> None:
    too_many = {f"q{i}": True for i in range(checker_routes._MAX_ANSWERS + 1)}
    resp = client.post(
        "/v1/checker/export",
        json={"answers": too_many, "format": "json"},
    )
    assert resp.status_code == 422


def test_checker_evaluate_rejects_too_many_answers() -> None:
    too_many = {f"q{i}": True for i in range(checker_routes._MAX_ANSWERS + 1)}
    resp = client.post("/v1/checker/evaluate", json={"answers": too_many})
    assert resp.status_code == 422


def test_resolve_client_ip_defaults_to_socket_peer_when_no_trusted_proxies(
    monkeypatch,
) -> None:
    monkeypatch.setattr(checker_routes, "_TRUSTED_PROXY_HOPS", 0)
    resp = client.post(
        "/v1/checker/evaluate",
        json={"answers": {}},
        headers={"X-Forwarded-For": "1.2.3.4"},
    )
    assert resp.status_code == 200
    # No assertion on the resolved IP value itself (TestClient's socket peer
    # is implementation-defined) — this only pins that an untrusted
    # X-Forwarded-For header does not raise or otherwise break the request.


def test_resolve_client_ip_uses_forwarded_header_when_trusted(monkeypatch) -> None:
    monkeypatch.setattr(checker_routes, "_TRUSTED_PROXY_HOPS", 1)
    seen_ips: list[str] = []
    original = checker_routes._resolve_client_ip
    monkeypatch.setattr(
        checker_routes,
        "_resolve_client_ip",
        lambda request: (seen_ips.append(original(request)), seen_ips[-1])[1],
    )
    resp = client.post(
        "/v1/checker/evaluate",
        json={"answers": {}},
        headers={"X-Forwarded-For": "203.0.113.7"},
    )
    assert resp.status_code == 200
    assert seen_ips == ["203.0.113.7"]
