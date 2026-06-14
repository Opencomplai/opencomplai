"""
Gold-set regression tests for the Annex III deterministic classifier.

Target accuracy: >= 99% match against the gold set (REQ-RISK-001).
Each fixture is a (use_case, expected_risk_level) pair derived from
authoritative EU AI Act Annex III interpretations.
"""

import pytest
from opencomplai_core.engine import assess
from opencomplai_core.models import AssessmentInput, ModelMetadata, RiskLevel

GOLD_SET: list[tuple[str, RiskLevel]] = [
    ("real-time facial recognition system for access control", RiskLevel.HIGH),
    ("gait recognition for building security", RiskLevel.HIGH),
    ("biometric identification of persons in public spaces", RiskLevel.HIGH),
    ("AI system for managing electricity grid load balancing", RiskLevel.HIGH),
    ("water supply network monitoring and anomaly detection", RiskLevel.HIGH),
    ("automated student assessment and grading system", RiskLevel.HIGH),
    ("AI proctoring system for university exams", RiskLevel.HIGH),
    ("CV screening and candidate ranking for recruitment", RiskLevel.HIGH),
    ("employment screening and ranking of job applicants", RiskLevel.HIGH),
    ("AI system for monitoring worker productivity", RiskLevel.HIGH),
    ("credit scoring model for loan applications", RiskLevel.HIGH),
    ("insurance premium pricing based on personal data", RiskLevel.HIGH),
    ("predictive policing and crime risk assessment", RiskLevel.HIGH),
    ("AI-assisted criminal evidence reliability evaluation", RiskLevel.HIGH),
    ("visa application assessment and approval system", RiskLevel.HIGH),
    ("asylum claim eligibility evaluation", RiskLevel.HIGH),
    ("border control document verification AI", RiskLevel.HIGH),
    ("AI system for judicial decision support", RiskLevel.HIGH),
    ("legal outcome prediction for court cases", RiskLevel.HIGH),
    ("customer support chatbot for e-commerce", RiskLevel.MINIMAL),
    ("weather forecasting model", RiskLevel.MINIMAL),
    ("product recommendation engine for online retail", RiskLevel.MINIMAL),
    ("spam detection for email filtering", RiskLevel.MINIMAL),
    ("image captioning for accessibility", RiskLevel.MINIMAL),
    ("social scoring system for citizen behaviour ranking", RiskLevel.UNACCEPTABLE),
    (
        "subliminal manipulation of consumer purchasing decisions",
        RiskLevel.UNACCEPTABLE,
    ),
]


def _make_input(use_case: str) -> AssessmentInput:
    return AssessmentInput(
        model=ModelMetadata(
            name="gold-set-model",
            version="1.0.0",
            modality="text",
            use_case=use_case,
            deployment_context="production",
        )
    )


@pytest.mark.parametrize(("use_case", "expected"), GOLD_SET)
def test_gold_set_classification(use_case: str, expected: RiskLevel):
    result = assess(_make_input(use_case))
    assert result.risk_level == expected, (
        f"use_case='{use_case}': expected {expected}, got {result.risk_level}\n"
        f"Evidence: {result.evidence_summary}"
    )


def test_gold_set_accuracy():
    total = len(GOLD_SET)
    correct = 0
    for use_case, expected in GOLD_SET:
        result = assess(_make_input(use_case))
        if result.risk_level == expected:
            correct += 1
    accuracy = correct / total
    assert accuracy >= 0.99, f"Gold-set accuracy {accuracy:.1%} is below 99% threshold"


def test_profiling_fixture_always_high_risk():
    input_with_profiling = AssessmentInput(
        model=ModelMetadata(
            name="profiling-model",
            version="1.0.0",
            modality="text",
            use_case="customer support chatbot",
            deployment_context="production",
        ),
        answers={"profiling_detected": True},
    )
    result = assess(input_with_profiling)
    assert result.risk_level == RiskLevel.HIGH


def test_modification_trap_fixture_blocks_deployment():
    input_modified = AssessmentInput(
        model=ModelMetadata(
            name="modified-model",
            version="2.0.0",
            modality="text",
            use_case="customer support chatbot",
            deployment_context="production",
        ),
        answers={"substantial_modification": True},
    )
    result = assess(input_modified)
    trap_rule = next(
        (
            r
            for r in result.rule_results
            if r.rule_id == "EU_AIA_ART25_MODIFICATION_TRAP"
        ),
        None,
    )
    assert trap_rule is not None
    assert trap_rule.passed is False
