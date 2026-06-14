"""Bridge compliance checker results to system manifest fields."""

from __future__ import annotations

from opencomplai_core.compliance_checker.models import ComplianceCheckerResult


def bridge_to_manifest_fields(result: ComplianceCheckerResult) -> dict[str, object]:
    """Map checker output to SystemManifest-compatible fields."""
    entity = result.effective_entity
    operator_role = entity.value if entity is not None else "unknown"

    if result.is_prohibited:
        intended_purpose = "prohibited_practice"
    elif result.is_high_risk:
        intended_purpose = "high_risk_ai_system"
    elif any(item.id == "transparency" for item in result.obligations):
        intended_purpose = "limited_risk_transparency"
    elif any(item.id == "gpai_provider" for item in result.obligations):
        intended_purpose = "general_purpose_ai_model"
    elif result.in_scope:
        intended_purpose = "in_scope_ai_system"
    else:
        intended_purpose = "out_of_scope"

    return {
        "operator_role": operator_role,
        "intended_purpose": intended_purpose,
        "high_risk_presumption": result.is_high_risk,
    }
