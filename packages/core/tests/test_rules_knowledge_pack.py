"""Regression tests for H-06 (single-word over-flagging) and H-08 (silent
empty ruleset on a missing opencomplai-ai plugin).
"""

from __future__ import annotations

import sys

import pytest
from opencomplai_core import rules
from opencomplai_core.models import AssessmentInput, ModelMetadata
from opencomplai_core.rules import (
    AnnexIIIClassifierRule,
    ProfilingDetectionRule,
)


def _input(use_case: str) -> AssessmentInput:
    return AssessmentInput(
        model=ModelMetadata(
            name="m",
            version="1.0",
            modality="text",
            use_case=use_case,
            deployment_context="production",
        ),
    )


class TestGenericWordFalsePositives:
    """H-06: a single generic word must never trigger an Annex III category."""

    def test_ci_testing_pipeline_is_not_high_risk(self):
        result = AnnexIIIClassifierRule().evaluate(
            _input(
                "AI system for internal performance testing of software build pipelines"
            )
        )
        assert result.passed is True

    def test_supply_chain_forecasting_is_not_critical_infrastructure(self):
        result = AnnexIIIClassifierRule().evaluate(
            _input("Automated supply chain inventory forecasting for a warehouse")
        )
        assert result.passed is True

    def test_vocabulary_flashcard_study_is_not_essential_services(self):
        result = AnnexIIIClassifierRule().evaluate(
            _input(
                "Model that helps students study by testing their vocabulary "
                "flashcards at home"
            )
        )
        assert result.passed is True

    def test_profiling_rule_not_triggered_by_generic_words(self):
        result = ProfilingDetectionRule().evaluate(
            _input(
                "Model that helps students study by testing their vocabulary "
                "flashcards at home"
            )
        )
        assert result.passed is True


class TestGenuineHighRiskStillFlagged:
    """The H-06 fix must not under-classify genuinely high-risk systems."""

    def test_resume_screening_recruitment_is_high_risk(self):
        result = AnnexIIIClassifierRule().evaluate(
            _input("CV screening and candidate ranking for recruitment")
        )
        assert result.passed is False

    def test_credit_scoring_for_loans_is_high_risk(self):
        result = AnnexIIIClassifierRule().evaluate(
            _input("credit scoring model for loan applications")
        )
        assert result.passed is False

    def test_asylum_seeker_use_case_is_not_gated_away_from_migration_area(self):
        """NATURAL_PERSON_CUES used to hold the compound token
        "asylum_seeker", which prose ("asylum seekers") can never produce
        after tokenization — so an asylum/migration use case that also
        contained a product/entity cue ("device") was subject-gated away as
        if it scored something other than a natural person, and Annex III
        7(b) silently passed."""
        result = AnnexIIIClassifierRule().evaluate(
            _input(
                "entry risk assessment device flags asylum seekers for "
                "extra screening at the border"
            )
        )
        assert result.passed is False

    def test_facial_recognition_access_control_is_high_risk(self):
        result = AnnexIIIClassifierRule().evaluate(
            _input("real-time facial recognition system for access control")
        )
        assert result.passed is False

    def test_recidivism_profiling_still_forces_high_risk(self):
        result = ProfilingDetectionRule().evaluate(
            _input("recidivism prediction for individual offenders")
        )
        assert result.passed is False


ANNEX_III_USE_CASES = [
    "assessing eligibility for social welfare benefits",
    "predicting recidivism for parole decisions",
    "assessing the risk of a person reoffending",
    "ranking job applicants for interviews",
    "profiling suspects during a police investigation",
    "evaluating the truthfulness of witness statements",
    "detecting cheating during remote examinations",
    "assigning students to school placement tracks",
    "categorization of people by ethnicity",
    "microtargeting voters ahead of the election",
    "interpreting the law to assist a judge",
    "emotion recognition in the workplace",
    "biometric identification of individuals in public spaces",
]

BENIGN_USE_CASES = [
    "internal performance testing of build pipelines",
    "warehouse supply forecasting",
    "batch inference service for product image tagging",
    "cascade classifier for detecting defects on a production line",
    "cloud migration planning tool",
    "database migration assistant that rewrites SQL schemas",
    "self-serve education videos about our API",
    "customer support chatbot",
    "performance profiling of our build pipeline",
    "CAD software for mechanical parts",
]


@pytest.mark.parametrize("use_case", ANNEX_III_USE_CASES)
def test_canonical_annex_iii_use_cases_are_high_risk(use_case):
    """Suppressing single-word vocabulary under-classified real Annex III systems.

    Each of these is a textbook Annex III use case whose distinguishing term
    ("recidivism", "ethnicity", "microtargeting") only ever appears as one
    word. Dropping bare-word expansion to stop over-flagging silently turned
    all of them MINIMAL — a false negative, which for a compliance gate is the
    worse direction of the two.
    """
    assert AnnexIIIClassifierRule().evaluate(_input(use_case)).passed is False


@pytest.mark.parametrize("use_case", BENIGN_USE_CASES)
def test_benign_engineering_use_cases_are_not_high_risk(use_case):
    """Ordinary engineering work must not trip a compliance gate.

    Covers both failure modes: substring matching (pack token "fer" firing
    inside "inference", "cad" inside "cascade") and bare area names
    ("migration", "education") firing with no corroborating term.
    """
    assert AnnexIIIClassifierRule().evaluate(_input(use_case)).passed is True
    assert ProfilingDetectionRule().evaluate(_input(use_case)).passed is True


class TestKeywordMatchingSemantics:
    """Matching is word-boundary + co-occurrence, not bare substring."""

    def test_pack_token_does_not_match_inside_a_longer_word(self):
        assert rules._matches_keyword("fer", "batch inference service") is False
        assert rules._matches_keyword("cad", "a cascade classifier") is False

    def test_pack_token_matches_as_a_whole_word(self):
        assert rules._matches_keyword("fer", "fer based emotion scoring") is True

    def test_trailing_plural_still_matches(self):
        assert rules._matches_keyword("applicant", "ranking job applicants") is True
        assert rules._matches_keyword("examination", "remote examinations") is True

    def test_single_token_alone_does_not_fire_a_category(self):
        assert rules._match_pack_keywords({"education"}, "education videos") == []

    def test_two_distinct_single_tokens_co_occur_and_fire(self):
        matched = rules._match_pack_keywords(
            {"cheating", "examination"}, "detecting cheating during examinations"
        )
        assert sorted(matched) == ["cheating", "examination"]

    def test_multi_word_phrase_fires_alone(self):
        matched = rules._match_pack_keywords(
            {"biometric categorization"}, "biometric categorization of faces"
        )
        assert matched == ["biometric categorization"]


class TestEmptyKnowledgePackFailsLoudly:
    """H-08: an empty ruleset must raise, never silently classify clean."""

    def test_annex_iii_categories_raises_when_pack_is_empty(self, monkeypatch):
        import opencomplai_core.knowledge.annex_iii as annex_mod

        monkeypatch.setattr(annex_mod, "ANNEX_III", [])
        with pytest.raises(rules.KnowledgePackError):
            rules._build_annex_iii_categories()

    def test_subject_gated_keywords_raises_when_pack_is_empty(self, monkeypatch):
        import opencomplai_core.knowledge.annex_iii as annex_mod

        monkeypatch.setattr(annex_mod, "ANNEX_III", [])
        with pytest.raises(rules.KnowledgePackError):
            rules._build_subject_gated_keywords()

    def test_unacceptable_risk_signals_raises_when_pack_is_empty(self, monkeypatch):
        import opencomplai_core.knowledge.prohibited as prohibited_mod

        monkeypatch.setattr(prohibited_mod, "PROHIBITED", [])
        with pytest.raises(rules.KnowledgePackError):
            rules._build_unacceptable_risk_signals()

    def test_profiling_signals_raises_when_pack_is_empty(self, monkeypatch):
        import opencomplai_core.knowledge.annex_iii as annex_mod

        monkeypatch.setattr(annex_mod, "ANNEX_III", [])
        with pytest.raises(rules.KnowledgePackError):
            rules._build_profiling_signals()

    def test_module_level_rulesets_are_non_empty_at_import(self):
        # Guards against reintroducing the silent-empty path: the
        # module-level constants computed at import time must never be
        # empty on a standard install, with or without opencomplai-ai.
        assert rules.ANNEX_III_CATEGORIES
        assert all(v for v in rules.ANNEX_III_CATEGORIES.values())
        assert rules.UNACCEPTABLE_RISK_SIGNALS
        assert rules.SUBJECT_GATED_KEYWORDS
        assert ProfilingDetectionRule.PROFILING_SIGNALS
        # Subject-gating cue sets (48.1): bundled in core so installing or
        # uninstalling the optional opencomplai-ai plugin never silently
        # changes a pass/fail verdict.
        assert rules._NATURAL_PERSON_CUES
        assert rules._PRODUCT_OR_ENTITY_CUES


class TestClassificationSurvivesMissingOptionalPlugin:
    """H-08 root fix: opencomplai-ai is not a declared dependency of core, so
    the bundled packs in opencomplai_core.knowledge must be authoritative —
    classification must work even when opencomplai-ai cannot be imported.
    """

    def test_builders_succeed_with_ai_plugin_unimportable(self, monkeypatch):
        for name in (
            "opencomplai_ai",
            "opencomplai_ai.knowledge",
            "opencomplai_ai.knowledge.annex_iii",
            "opencomplai_ai.knowledge.prohibited",
        ):
            monkeypatch.setitem(sys.modules, name, None)

        assert rules._build_annex_iii_categories()
        assert rules._build_unacceptable_risk_signals()
        assert rules._build_subject_gated_keywords()
        assert rules._build_profiling_signals()

    def test_subject_gating_verdict_survives_missing_optional_plugin(self, monkeypatch):
        """48.1 regression: installing/uninstalling opencomplai-ai must never
        change a pass/fail verdict. Before the fix, opencomplai_core.rules
        imported the cue sets from opencomplai_ai.models inside a
        try/except ImportError, falling back to empty frozensets when the
        optional plugin was unimportable — which silently turned this
        bond-portfolio use case from PASS (correct — not a natural person)
        into FAIL (high-risk) because the empty-set guard made subject
        gating a no-op.

        rules.py is executed here as an *isolated* module object (not
        registered as opencomplai_core.rules in sys.modules) with
        opencomplai_ai poisoned, so a reintroduced try/except would be
        exercised even though this dev environment has the plugin
        installed — and without mutating the shared rules module that
        other test files already imported.
        """
        import importlib.util

        for name in ("opencomplai_ai", "opencomplai_ai.models"):
            monkeypatch.setitem(sys.modules, name, None)

        spec = importlib.util.spec_from_file_location(
            "opencomplai_core._rules_isolated_test", rules.__file__
        )
        isolated_rules = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(isolated_rules)

        result = isolated_rules.AnnexIIIClassifierRule().evaluate(
            _input("credit risk scorecard for our bond portfolio")
        )
        assert result.passed is True


class TestOptionalAiPluginReExportsCoreKnowledge:
    """D6: opencomplai-ai must re-export core's pack, never keep a second
    copy that could drift from the bundled data.
    """

    def test_ai_annex_iii_is_the_same_object_as_core(self):
        import opencomplai_ai.knowledge.annex_iii as ai_mod
        import opencomplai_core.knowledge.annex_iii as core_mod

        assert ai_mod.ANNEX_III is core_mod.ANNEX_III

    def test_ai_prohibited_is_the_same_object_as_core(self):
        import opencomplai_ai.knowledge.prohibited as ai_mod
        import opencomplai_core.knowledge.prohibited as core_mod

        assert ai_mod.PROHIBITED is core_mod.PROHIBITED

    def test_ai_natural_person_cues_is_the_same_object_as_core(self):
        import opencomplai_ai.models as ai_mod
        import opencomplai_core.knowledge.subject_cues as core_mod

        assert ai_mod.NATURAL_PERSON_CUES is core_mod.NATURAL_PERSON_CUES

    def test_ai_product_or_entity_cues_is_the_same_object_as_core(self):
        import opencomplai_ai.models as ai_mod
        import opencomplai_core.knowledge.subject_cues as core_mod

        assert ai_mod.PRODUCT_OR_ENTITY_CUES is core_mod.PRODUCT_OR_ENTITY_CUES


def test_matched_keywords_come_back_in_a_stable_order():
    # Matches used to be returned in set order, which follows the
    # per-process string hash seed, so rule rationales differed run to run.
    matcher = rules._CompiledKeywordMatcher(["zeta", "alpha", "credit scoring", "mid"])
    assert matcher.find_matching_keywords("zeta mid credit scoring alpha") == [
        "alpha",
        "credit scoring",
        "mid",
        "zeta",
    ]
