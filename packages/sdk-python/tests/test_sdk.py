"""Tests for the Opencomplai Python SDK."""

from pathlib import Path

import opencomplai
import opencomplai_core
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
    framework_exports = {
        "FRAMEWORKS",
        "FrameworkPack",
        "FrameworkReport",
        "GapReport",
        "evaluate_targets",
        "resolve_targets",
    }
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
        *framework_exports,
    }
    assert set(opencomplai.__all__) == expected_exports
    assert framework_exports <= set(opencomplai_core.__all__)
    for name in expected_exports:
        assert getattr(opencomplai, name) is not None
    for name in opencomplai_core.__all__:
        assert getattr(opencomplai_core, name) is not None
    py_typed = Path(opencomplai.__file__).parent / "py.typed"
    assert py_typed.is_file()
    core_py_typed = Path(opencomplai_core.__file__).parent / "py.typed"
    assert core_py_typed.is_file()


def test_sdk_evaluates_several_frameworks_side_by_side():
    manifest = opencomplai.SystemManifest(
        system_id="sdk-test-model",
        intended_purpose="customer support chatbot",
        compliance_targets=["EU_AI_ACT", "NIST_AI_RMF"],
    )
    targets = opencomplai.resolve_targets(manifest)
    reports = opencomplai.evaluate_targets(manifest, targets, commit_ref="HEAD")

    assert list(reports) == ["EU_AI_ACT", "NIST_AI_RMF"]
    assert set(reports) <= set(opencomplai.FRAMEWORKS)
    nist = reports["NIST_AI_RMF"]
    assert isinstance(nist, opencomplai.FrameworkReport)
    assert isinstance(nist.report, opencomplai.GapReport)
    assert nist.derived_from == "EU_AI_ACT"
    assert all(row.article.startswith("NIST_AI_RMF:") for row in nist.report.articles)
