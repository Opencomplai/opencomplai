"""Bridge compliance checker results to system manifest fields."""

from __future__ import annotations

from opencomplai_core.compliance_checker.models import ComplianceCheckerResult

#: Every tier label ``bridge_to_manifest_fields`` can return as
#: ``checker_verdict``. Also lets ``check`` recognise a 0.7.0 manifest whose
#: ``intended_purpose`` holds one of these labels instead of purpose text.
CHECKER_VERDICTS: frozenset[str] = frozenset(
    {
        "prohibited_practice",
        "high_risk_ai_system",
        "limited_risk_transparency",
        "general_purpose_ai_model",
        "in_scope_ai_system",
        "out_of_scope",
    }
)


def bridge_to_manifest_fields(result: ComplianceCheckerResult) -> dict[str, object]:
    """Map checker output to SystemManifest-compatible fields.

    ``checker_verdict`` is the checker's tier label (one of
    ``CHECKER_VERDICTS``); it belongs in ``checker_session.verdict``. There is
    no ``intended_purpose``: the EU rules keyword-match it as the system's
    purpose text, so callers must ask for the real purpose.
    """
    entity = result.effective_entity
    operator_role = entity.value if entity is not None else "unknown"

    if result.is_prohibited:
        verdict = "prohibited_practice"
    elif result.is_high_risk:
        verdict = "high_risk_ai_system"
    elif any(item.id == "transparency" for item in result.obligations):
        verdict = "limited_risk_transparency"
    elif any(item.id == "gpai_provider" for item in result.obligations):
        verdict = "general_purpose_ai_model"
    elif result.in_scope:
        verdict = "in_scope_ai_system"
    else:
        verdict = "out_of_scope"

    return {
        "operator_role": operator_role,
        "checker_verdict": verdict,
        "high_risk_presumption": result.is_high_risk,
    }
