"""Tests for compliance checker HTTP routes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from opencomplai_risk_engine import checker_routes
from opencomplai_risk_engine.main import app
from opencomplai_risk_engine.mailer import MailerNotConfiguredError

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_email_rate_limit():
    """Each test gets a clean rate-limit bucket — TestClient reuses one fake IP."""
    checker_routes._email_rate_limit_hits.clear()
    yield
    checker_routes._email_rate_limit_hits.clear()
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
            json={"answers": fixture["session"]["answers"], "to_email": "user@example.com"},
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
        checker_routes, "send_pdf_email", side_effect=MailerNotConfiguredError("no host")
    ):
        resp = client.post(
            "/v1/checker/email",
            json={"answers": {}, "to_email": "user@example.com"},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"]["error_code"] == "MAILER_NOT_CONFIGURED"


def test_checker_email_is_rate_limited_per_ip() -> None:
    with patch.object(checker_routes, "send_pdf_email"):
        limit = checker_routes._EMAIL_RATE_LIMIT_MAX_REQUESTS
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
