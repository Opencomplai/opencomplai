"""Risk assessment engine — runs all registered rules against an AssessmentInput."""

from datetime import UTC, datetime

from opencomplai_core.models import (
    AssessmentInput,
    RiskLevel,
    RiskResult,
    RuleResult,
)
from opencomplai_core.rules import RULE_REGISTRY


def assess(input: AssessmentInput) -> RiskResult:
    """
    Run all registered rules against the given assessment input.

    Args:
        input: AssessmentInput with model metadata and optional rule answers.

    Returns:
        RiskResult with risk classification and per-rule evidence.
    """
    rule_results: list[RuleResult] = []

    for rule in RULE_REGISTRY:
        result = rule.evaluate(input)
        rule_results.append(result)

    passed = [r for r in rule_results if r.passed]
    failed = [r for r in rule_results if not r.passed]
    risk_level = _classify_risk(failed)

    return RiskResult(
        model_name=input.model.name,
        model_version=input.model.version,
        risk_level=risk_level,
        rules_evaluated=len(rule_results),
        rules_passed=len(passed),
        rules_failed=len(failed),
        rule_results=rule_results,
        evidence_summary=_build_summary(risk_level, passed, failed),
        generated_at=datetime.now(UTC).isoformat(),
    )


def _classify_risk(failed_rules: list[RuleResult]) -> RiskLevel:
    """Classify overall risk based on which rules failed."""
    failed_ids = {r.rule_id for r in failed_rules}
    if "EU_AIA_ART5_UNACCEPTABLE" in failed_ids:
        return RiskLevel.UNACCEPTABLE
    if "EU_AIA_ART6_HIGH_RISK" in failed_ids or "EU_AIA_ART6_PROFILING" in failed_ids:
        return RiskLevel.HIGH
    if "EU_AIA_ART25_MODIFICATION_TRAP" in failed_ids:
        return RiskLevel.HIGH
    if failed_ids:
        return RiskLevel.LIMITED
    return RiskLevel.MINIMAL


def _build_summary(
    risk_level: RiskLevel,
    passed: list[RuleResult],
    failed: list[RuleResult],
) -> str:
    """Build a human-readable evidence summary."""
    return (
        f"Risk classification: {risk_level.value.upper()}. "
        f"{len(passed)} rules passed, {len(failed)} rules failed."
    )
