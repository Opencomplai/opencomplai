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
from opencomplai_core.compliance_checker.bridge import derogation_grounds
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
    # The 0.7.x intended_purpose alias of the verdict was removed in 0.8.0.
    assert "intended_purpose" not in bridged


@pytest.mark.parametrize("fixture", sorted(p.name for p in FIXTURES_DIR.glob("*.json")))
def test_every_verdict_is_a_known_label(fixture: str):
    assert _bridge(fixture)["checker_verdict"] in CHECKER_VERDICTS


def _grounds(fixture: str | None = None, **answers: object) -> list[str]:
    if fixture is not None:
        payload = json.loads((FIXTURES_DIR / fixture).read_text(encoding="utf-8"))
        session = CheckerSession.model_validate(payload["session"])
    else:
        session = CheckerSession(
            answers={"gate_is_ai_system": True, "s1_in_scope": True, **answers}
        )
    return derogation_grounds(evaluate(session))


def test_derogation_grounds_lists_true_exception_answers():
    assert _grounds("21_provider_derogation_registration.json") == ["hr3_art_6_3"]
    assert _grounds("17_hr6_not_high_risk.json") == ["hr6_accessory"]
    # Fixed order, whatever the order the answers were given in.
    assert _grounds(
        e1_entity_type="provider",
        hr2_annex_iii=True,
        hr5_no_significant_risk=True,
        hr3_art_6_3=True,
    ) == ["hr3_art_6_3", "hr5_no_significant_risk"]


def test_derogation_grounds_empty_without_derogation():
    # high-risk, no exception answered
    assert _grounds("06_high_risk_provider.json") == []
    # Annex I with third-party conformity assessment: no Annex III derogation
    assert (
        _grounds(
            e1_entity_type="provider",
            hr1_annex_i=True,
            hr8_conformity_assessment=True,
            hr3_art_6_3=True,
        )
        == []
    )
    # profiling is always high-risk, even with an exception answered
    assert (
        _grounds(
            e1_entity_type="provider",
            hr2_annex_iii=True,
            hr7_profiling=True,
            hr3_art_6_3=True,
        )
        == []
    )
    # exception answered but hr2 absent
    assert _grounds(e1_entity_type="provider", hr3_art_6_3=True) == []
