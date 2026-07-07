"""Subject-type gating — Annex III person-scoped areas must not fire on
product/portfolio/entity scoring that merely shares vocabulary with a
natural-person use case (e.g. "credit scoring" for a bond vs. a consumer).
"""

from __future__ import annotations

from opencomplai_core.models import AssessmentInput, ModelMetadata
from opencomplai_core.rules import AnnexIIIClassifierRule, ProfilingDetectionRule


def _input(use_case: str, **answers: object) -> AssessmentInput:
    return AssessmentInput(
        model=ModelMetadata(
            name="m",
            version="1.0",
            modality="text",
            use_case=use_case,
            deployment_context="production",
        ),
        answers=answers,
    )


class TestAnnexIIIClassifierRuleSubjectGating:
    def test_consumer_credit_scoring_is_high_risk(self):
        rule = AnnexIIIClassifierRule()
        result = rule.evaluate(
            _input("credit scoring to approve consumer loan applicants")
        )
        assert result.passed is False

    def test_portfolio_credit_scoring_is_not_high_risk(self):
        rule = AnnexIIIClassifierRule()
        result = rule.evaluate(
            _input("credit risk scorecard for our bond portfolio")
        )
        assert result.passed is True
        assert "does not apply" in result.rationale or "not apply" in result.rationale

    def test_vendor_risk_scoring_is_not_high_risk(self):
        rule = AnnexIIIClassifierRule()
        result = rule.evaluate(
            _input("risk score for supplier and vendor onboarding")
        )
        assert result.passed is True

    def test_employee_performance_scoring_is_high_risk(self):
        rule = AnnexIIIClassifierRule()
        result = rule.evaluate(
            _input("performance score AI to evaluate employee promotion")
        )
        assert result.passed is False

    def test_device_health_scoring_is_not_high_risk(self):
        rule = AnnexIIIClassifierRule()
        result = rule.evaluate(
            _input("predictive risk score for machine and equipment maintenance")
        )
        assert result.passed is True

    def test_biometrics_not_subject_gated_still_high_risk(self):
        # Area 1 (biometrics) is not subject_gated — should be unaffected
        # by product/entity cues appearing elsewhere in the text.
        rule = AnnexIIIClassifierRule()
        result = rule.evaluate(
            _input("facial recognition system for our retail product")
        )
        assert result.passed is False

    def test_mixed_area_essential_services_dispatch_not_gated(self):
        # 5(d) emergency dispatch is not subject_gated even though it shares
        # an area_name with 5(a-c) which are gated.
        rule = AnnexIIIClassifierRule()
        result = rule.evaluate(_input("emergency dispatch AI for 911 triage"))
        assert result.passed is False

    def test_ambiguous_text_defaults_to_high_risk(self):
        # No person cue and no product/entity cue present — stay high-risk
        # rather than silently downgrading on absence of evidence.
        rule = AnnexIIIClassifierRule()
        result = rule.evaluate(_input("credit scoring model"))
        assert result.passed is False


class TestProfilingDetectionRuleSubjectGating:
    def test_explicit_declaration_always_forces_high_risk(self):
        rule = ProfilingDetectionRule()
        result = rule.evaluate(
            _input("portfolio risk scoring for bonds", profiling_detected=True)
        )
        assert result.passed is False

    def test_portfolio_scoring_profiling_signal_not_forced(self):
        rule = ProfilingDetectionRule()
        result = rule.evaluate(
            _input("recidivism-style risk scorecard applied to corporate counterparty risk")
        )
        assert result.passed is True

    def test_natural_person_recidivism_scoring_forces_high_risk(self):
        rule = ProfilingDetectionRule()
        result = rule.evaluate(
            _input("recidivism prediction for individual offenders")
        )
        assert result.passed is False
