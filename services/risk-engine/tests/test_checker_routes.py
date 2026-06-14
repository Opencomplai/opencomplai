"""Tests for compliance checker HTTP routes."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from opencomplai_risk_engine.main import app

client = TestClient(app)
FIXTURES = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "core"
    / "tests"
    / "fixtures"
    / "fli_golden"
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
