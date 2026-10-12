"""Scanner taxonomy mapping — no drift from rules.py."""

from __future__ import annotations

import pytest
from opencomplai_core.models import (
    AssessmentInput,
    EvidenceItem,
    EvidenceKind,
    EvidenceScope,
    ModelMetadata,
    Reachability,
    SignalCategory,
)
from opencomplai_core.rules import (
    ANNEX_III_CATEGORIES,
    UNACCEPTABLE_RISK_SIGNALS,
    AnnexIIIClassifierRule,
    match_annex_iii_categories,
)
from opencomplai_core.scanner.fusion import fuse_evidence
from opencomplai_core.scanner.mapping import (
    _AREA_TO_TAXONOMY,
    SIGNAL_TO_TAXONOMY,
    derive_declared_categories,
    signal_category_to_taxonomy,
)


def test_every_signal_category_maps_to_real_taxonomy_or_empty():
    for cat in SignalCategory:
        mapped = signal_category_to_taxonomy(cat)
        for key in mapped:
            if key == "unacceptable":
                continue
            assert key in ANNEX_III_CATEGORIES, f"{cat} mapped to unknown {key}"


def test_biometric_maps_to_biometric_category():
    mapped = signal_category_to_taxonomy(SignalCategory.BIOMETRIC, "face_recognition")
    assert "biometric" in mapped


def test_scoring_profiling_single_area_when_annex_resolved():
    mapped = signal_category_to_taxonomy(
        SignalCategory.SCORING_PROFILING,
        "predict_proba",
        annex_iii_area=5,
    )
    assert mapped == ["essential_services"]


def test_scoring_profiling_unresolved_maps_to_no_area():
    assert SIGNAL_TO_TAXONOMY[SignalCategory.SCORING_PROFILING] == []
    cat = SignalCategory.SCORING_PROFILING
    assert signal_category_to_taxonomy(cat) == []
    assert signal_category_to_taxonomy(cat, annex_iii_area=None) == []
    assert signal_category_to_taxonomy(cat, annex_iii_area=99) == []
    former = {"employment", "essential_services", "law_enforcement"}
    assert not former <= set(signal_category_to_taxonomy(cat, "classifier"))


@pytest.mark.parametrize(("area", "key"), sorted(_AREA_TO_TAXONOMY.items()))
def test_scoring_profiling_resolved_area_maps_to_exactly_that_area(area, key):
    mapped = signal_category_to_taxonomy(
        SignalCategory.SCORING_PROFILING, "", annex_iii_area=area
    )
    assert mapped == [key]


def test_unresolved_scoring_finding_has_empty_mapped_taxonomy():
    item = EvidenceItem(
        evidence_id="ev_score_1",
        evidence_kind=EvidenceKind.CALLSITE,
        category=SignalCategory.SCORING_PROFILING,
        token_hash="sha256:test",
        token_label="score",
        locations=["src/score.py:10"],
        scope=EvidenceScope.PROD,
        reachability=Reachability.INTERNAL_CALLCHAIN,
        detector_id="DET_TEST",
        detector_version="1.0.0",
        redaction_level="hash_only",
        rationale_code="test",
        confidence=0.9,
    )
    findings = fuse_evidence([item])
    assert findings[0].mapped_taxonomy == []


def test_derive_declared_categories_matches_annex_iii():
    declared = derive_declared_categories("candidate ranking for hiring")
    assert "employment" in declared


def test_normalize_text_strips_punctuation():
    from opencomplai_core.rules import normalize_text

    assert (
        normalize_text("Employment, screening & ranking!")
        == "employment screening ranking"
    )


def test_unacceptable_signal_in_purpose():
    declared = derive_declared_categories("social scoring system")
    assert "unacceptable" in declared or any(
        s in "social scoring system" for s in UNACCEPTABLE_RISK_SIGNALS
    )


def test_analytics_dashboard_yields_no_employment_category():
    assert "employment" not in derive_declared_categories("analytics dashboard")


def test_resume_screening_for_hiring_still_yields_employment():
    assert "employment" in derive_declared_categories(
        "automated resume screening for hiring"
    )


def test_part_word_keyword_does_not_map():
    assert derive_declared_categories("inference cascade service") == []


def test_part_word_prohibited_signal_does_not_map():
    assert derive_declared_categories("olive rbi planner") == []


def test_social_scoring_still_unacceptable():
    assert "unacceptable" in derive_declared_categories("social scoring system")


def _rule_input(use_case: str) -> AssessmentInput:
    return AssessmentInput(
        model=ModelMetadata(
            name="m",
            version="1.0",
            modality="text",
            use_case=use_case,
            deployment_context="production",
        ),
        answers={},
    )


@pytest.mark.parametrize(
    "text",
    [
        "analytics dashboard",
        "automated resume screening for hiring",
        "inference cascade service",
        "olive rbi planner",
        "social scoring system",
        "candidate ranking for hiring",
        "credit scoring to approve consumer loan applicants",
        "credit scoring for corporate bond portfolio counterparty",
    ],
)
def test_declared_categories_agree_with_rule_engine(text):
    declared = [c for c in derive_declared_categories(text) if c != "unacceptable"]
    engine = sorted(match_annex_iii_categories(text).categories)
    assert declared == engine
    assert AnnexIIIClassifierRule().evaluate(_rule_input(text)).passed is (not engine)


def test_match_annex_iii_categories_reports_gated_areas():
    m = match_annex_iii_categories("credit risk scorecard for our bond portfolio")
    assert m.subject_gated
    assert m.categories == []


def test_bare_label_tokens_do_not_add_areas():
    assert signal_category_to_taxonomy(SignalCategory.AI_SDK, "credit") == []
    assert (
        signal_category_to_taxonomy(SignalCategory.SCORING_PROFILING, "classifier")
        == []
    )
