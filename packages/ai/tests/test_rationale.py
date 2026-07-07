"""Tests for deterministic flag rationale builder."""

from __future__ import annotations

from opencomplai_ai.models import IntentAnnotation
from opencomplai_ai.rationale import build_flag_rationale


def test_high_risk_rationale_includes_signal_and_regulation():
    ann = IntentAnnotation(
        annex_iii_area=5,
        risk_tier="high_risk",
        matched_signals=["predict_proba"],
        knowledge_entry_title="Creditworthiness assessment and credit scoring",
        regulation_ref="Art. 6(2), Annex III pt.5(b)",
        gate_reason="inference_verb_with_file_context",
        declared_purpose_used=True,
        confidence=0.8,
    )
    rationale = build_flag_rationale(
        ann,
        gate_reason="inference_verb_with_file_context",
        declared_purpose="automated credit scoring for retail lending",
    )
    assert "predict_proba" in rationale.summary
    assert "Annex III area 5" in rationale.summary
    assert rationale.regulation_ref.startswith("Art. 6(2)")
    assert rationale.gate_reason == "inference_verb_with_file_context"
    assert rationale.declared_purpose_used is True
    assert rationale.needed_action
    assert "intended_purpose" in rationale.needed_action


def test_prohibited_rationale_cites_art5():
    ann = IntentAnnotation(
        art5_prohibited=True,
        risk_tier="prohibited",
        matched_signals=["social_scoring"],
        knowledge_entry_title="Social scoring of natural persons or groups",
        regulation_ref="Art.5(1)(c)",
        gate_reason="pack_code_signal",
    )
    rationale = build_flag_rationale(ann, gate_reason="pack_code_signal")
    assert "Art. 5" in rationale.summary
    assert "social_scoring" in rationale.summary
    assert rationale.regulation_ref == "Art.5(1)(c)"
    assert "Remove or disable" in rationale.needed_action


def test_limited_risk_rationale_cites_art50():
    ann = IntentAnnotation(
        risk_tier="limited_risk",
        matched_signals=["chatbot"],
        knowledge_entry_title="Chatbots and AI interaction systems",
        regulation_ref="Art.50(1)",
        gate_reason="ai_import",
    )
    rationale = build_flag_rationale(ann, gate_reason="ai_import")
    assert "Art. 50" in rationale.summary
    assert "chatbot" in rationale.summary
