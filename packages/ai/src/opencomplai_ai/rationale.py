"""Deterministic Flag Rationale builder for EU AI Act scan findings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opencomplai_ai.models import IntentAnnotation


def build_needed_action(
    annotation: IntentAnnotation,
    *,
    declared_purpose: str = "",
) -> str:
    """Return remediation guidance for a flagged callsite."""
    regulation_ref = annotation.regulation_ref or ""
    entry_title = annotation.knowledge_entry_title or "regulated AI use"

    if annotation.art5_prohibited:
        return (
            "Remove or disable this prohibited AI capability before production use. "
            "If the code path is inactive, delete it or isolate it from user-facing flows. "
            "Update intended_purpose to reflect the actual system scope and document why "
            f"this practice is not deployed ({regulation_ref or 'Art. 5'})."
        )

    if annotation.annex_iii_area is not None:
        purpose_hint = ""
        if declared_purpose.strip():
            purpose_hint = (
                f' Confirm intended_purpose ("{declared_purpose.strip()}") matches this '
                "high-risk use, or revise the declaration."
            )
        else:
            purpose_hint = (
                " Declare this high-risk use in intended_purpose and align your "
                "system manifest with Annex III obligations."
            )
        return (
            f"Implement high-risk AI controls for {entry_title}: risk management (Art. 9), "
            "data governance (Art. 10), logging (Art. 12), transparency (Art. 13), and "
            "human oversight (Art. 14), plus conformity assessment and EU database "
            f"registration where applicable ({regulation_ref or 'Art. 6(2)'})."
            f"{purpose_hint} If this is not an AI system use, rename or refactor the "
            "code to remove the regulated signal."
        )

    if annotation.risk_tier == "limited_risk":
        return (
            "Disclose AI interaction to end users under Art. 50, document the limited-risk "
            "transparency obligation in your system manifest, and ensure user-facing flows "
            "clearly indicate AI-generated or AI-assisted content."
        )

    return (
        "Review this callsite, confirm whether it performs regulated AI processing, and "
        "update intended_purpose or refactor the code so the system scope matches your "
        "EU AI Act declaration."
    )


def build_flag_rationale(
    annotation: IntentAnnotation,
    *,
    gate_reason: str | None = None,
    declared_purpose: str = "",
) -> Any:
    """Build a structured FlagRationale from an intent annotation and gate context."""
    from opencomplai_core.models import FlagRationale

    signals = list(annotation.matched_signals)
    entry_title = annotation.knowledge_entry_title
    regulation_ref = annotation.regulation_ref or ""
    purpose_used = annotation.declared_purpose_used
    gate = gate_reason or annotation.gate_reason
    needed_action = build_needed_action(annotation, declared_purpose=declared_purpose)

    if annotation.art5_prohibited:
        signal_text = signals[0] if signals else "prohibited practice"
        summary = (
            f'Matched Art. 5 prohibition signal "{signal_text}"'
            + (f" ({entry_title})" if entry_title else "")
            + f"; system is prohibited under {regulation_ref or 'Art. 5'}."
        )
        if gate:
            summary += f" Gate: {gate}."
        return FlagRationale(
            summary=summary,
            needed_action=needed_action,
            matched_signals=signals,
            gate_reason=gate,
            regulation_ref=regulation_ref or "Art. 5",
            knowledge_entry_title=entry_title,
            declared_purpose_used=purpose_used,
        )

    if annotation.annex_iii_area is not None:
        area = annotation.annex_iii_area
        signal_text = ", ".join(signals) if signals else "Annex III code signal"
        summary = (
            f"Matched Annex III area {area} code signal "
            f'"{signal_text}"'
            + (f" ({entry_title})" if entry_title else "")
            + f"; high-risk obligations apply under {regulation_ref or 'Art. 6(2)'}."
        )
        if purpose_used and declared_purpose:
            summary += f' Declared purpose "{declared_purpose.strip()}" confirmed the classification.'
        if gate:
            summary += f" Gate: {gate}."
        return FlagRationale(
            summary=summary,
            needed_action=needed_action,
            matched_signals=signals,
            gate_reason=gate,
            regulation_ref=regulation_ref or f"Art. 6(2), Annex III area {area}",
            knowledge_entry_title=entry_title,
            declared_purpose_used=purpose_used,
        )

    if annotation.risk_tier == "limited_risk":
        signal_text = signals[0] if signals else "limited-risk trigger"
        summary = (
            f'Matched Art. 50 limited-risk trigger "{signal_text}"'
            + (f" ({entry_title})" if entry_title else "")
            + f"; transparency obligations under {regulation_ref or 'Art. 50'}."
        )
        if gate:
            summary += f" Gate: {gate}."
        return FlagRationale(
            summary=summary,
            needed_action=needed_action,
            matched_signals=signals,
            gate_reason=gate,
            regulation_ref=regulation_ref or "Art. 50",
            knowledge_entry_title=entry_title,
            declared_purpose_used=purpose_used,
        )

    return FlagRationale(
        summary=annotation.explanation or "Regulatory signal detected.",
        needed_action=needed_action,
        matched_signals=signals,
        gate_reason=gate,
        regulation_ref=regulation_ref,
        knowledge_entry_title=entry_title,
        declared_purpose_used=purpose_used,
    )
