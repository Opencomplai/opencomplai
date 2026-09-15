"""Tests for the Opencomplai Python SDK."""

from pathlib import Path

import opencomplai
import pytest
from opencomplai import AssessmentInput, ModelMetadata, RiskLevel, RiskResult, assess


def _input(use_case: str) -> AssessmentInput:
    """Build a minimal AssessmentInput for testing."""
    return AssessmentInput(
        model=ModelMetadata(
            name="sdk-test-model",
            version="1.0.0",
            modality="text",
            use_case=use_case,
            deployment_context="production",
        )
    )


def test_assess_returns_risk_result():
    result = assess(_input("customer support chatbot"))
    assert isinstance(result, RiskResult)


def test_assess_minimal_risk_safe_model():
    result = assess(_input("weather forecasting"))
    assert result.risk_level == RiskLevel.MINIMAL


def test_assess_high_risk_employment():
    result = assess(_input("employment screening"))
    assert result.risk_level == RiskLevel.HIGH


def test_assess_evidence_populated():
    result = assess(_input("customer support chatbot"))
    assert result.evidence_summary
    assert len(result.rule_results) > 0


def test_assess_raises_on_invalid_input():
    with pytest.raises(Exception):  # noqa: B017, PT011 — asserts invalid input raises at all
        assess(None)


def test_sdk_exports_and_pep561():
    expected_exports = {
        "AssessmentInput",
        "ModelMetadata",
        "RiskLevel",
        "RiskResult",
        "RuleResult",
        "ScanResult",
        "ScanStatusArtifact",
        "SystemManifest",
        "assess",
    }
    assert set(opencomplai.__all__) == expected_exports
    py_typed = Path(opencomplai.__file__).parent / "py.typed"
    assert py_typed.is_file()
