"""Tests for the checker -> manifest bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.compliance_checker import (
    CHECKER_VERDICTS,
    bridge_to_manifest_fields,
    evaluate,
)
from opencomplai_core.compliance_checker.models import CheckerSession

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "checker_golden"


def _bridge(fixture: str) -> dict[str, object]:
    payload = json.loads((FIXTURES_DIR / fixture).read_text(encoding="utf-8"))
    return bridge_to_manifest_fields(
        evaluate(CheckerSession.model_validate(payload["session"]))
    )


@pytest.mark.parametrize(
    ("fixture", "verdict"),
    [
        ("05_prohibited.json", "prohibited_practice"),
        ("06_high_risk_provider.json", "high_risk_ai_system"),
        ("02_out_of_scope_not_ai.json", "out_of_scope"),
    ],
)
def test_bridge_returns_verdict(fixture: str, verdict: str):
    bridged = _bridge(fixture)
    assert bridged["checker_verdict"] == verdict
    # Deprecated 0.7.x alias, kept until 0.8.0.
    assert bridged["intended_purpose"] == verdict


@pytest.mark.parametrize("fixture", sorted(p.name for p in FIXTURES_DIR.glob("*.json")))
def test_every_verdict_is_a_known_label(fixture: str):
    assert _bridge(fixture)["checker_verdict"] in CHECKER_VERDICTS
