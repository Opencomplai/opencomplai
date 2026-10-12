"""Real deterministic classifier output feeds the call-site aggregation."""

from __future__ import annotations

from opencomplai_ai.classifier import IntentClassifier
from opencomplai_core.models import (
    EvidenceItem,
    EvidenceKind,
    EvidenceScope,
    Reachability,
    SignalCategory,
)
from opencomplai_core.scan_engine import _build_eu_ai_scan_summary
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.proposal import build_classification_proposal


def _item(snippet: str, token: str, location: str) -> EvidenceItem:
    ann = IntentClassifier().classify(snippet, location=location, token=token)
    assert ann is not None
    ev = build_evidence(
        detector_id="DET_INTENT_V1",
        detector_version="1.1.0",
        evidence_kind=EvidenceKind.CALLSITE,
        category=SignalCategory.SCORING_PROFILING,
        token_label=token,
        location=location,
        scope=EvidenceScope.PROD,
        rationale_code=f"ai_intent:{ann.risk_tier}",
        confidence=ann.confidence if ann.confidence > 0 else 0.5,
        reachability=Reachability.INTERNAL_CALLCHAIN,
    )
    return ev.model_copy(update={"intent_annotation": ann})


def test_classifier_output_three_employment_one_biometric():
    # Area 8 is numbered above 4 and "0_stray.py" sorts before the employment
    # lines, so a max-area or first-by-order winner rule fails this test.
    items = [
        _item("judicial_decision(case_file)", "judicial_decision", "0_stray.py:1"),
        _item("rank_candidates(applicant_pool)", "rank_candidates", "a.py:1"),
        _item("rank_candidates(applicant_pool)", "rank_candidates", "b.py:1"),
        _item("rank_candidates(applicant_pool)", "rank_candidates", "c.py:1"),
        _item("predict_ethnicity(face_crop)", "predict_ethnicity", "d.py:1"),
    ]
    summary = _build_eu_ai_scan_summary(usage_matches={}, regulatory_evidence=items)
    proposal = build_classification_proposal(summary)

    assert proposal.proposed_annex_iii_area == 4
    assert proposal.supporting_count == 3
    assert sorted(ln.location for ln in proposal.supporting_evidence) == [
        "a.py:1",
        "b.py:1",
        "c.py:1",
    ]
    assert [(ln.location, ln.annex_iii_area) for ln in proposal.minority_evidence] == [
        ("0_stray.py:1", 8),
        ("d.py:1", 1),
    ]
    assert proposal.confidence_label == "medium"
    assert proposal.confirmation_status == "unconfirmed"


def test_non_person_scoring_downgrade_yields_none():
    items = [_item("rank_candidates(portfolio_assets)", "rank_candidates", "a.py:1")]
    summary = _build_eu_ai_scan_summary(usage_matches={}, regulatory_evidence=items)
    assert summary.high_risk == []

    proposal = build_classification_proposal(summary)
    assert proposal.proposed_annex_iii_area is None
    assert proposal.confidence_label == "none"
    assert proposal.supporting_evidence == []
    assert proposal.minority_evidence == []
