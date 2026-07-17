"""Tests for the per-article gap report projection (opencomplai gaps)."""

from opencomplai_core.engine import assess
from opencomplai_core.eval_engine import run_evals
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    AssessmentInput,
    CorroborationReport,
    EvalSampleSet,
    GapStatus,
    ModelMetadata,
)


def _make_risk_result(use_case: str):
    return assess(
        AssessmentInput(
            model=ModelMetadata(
                name="test-model",
                version="1.0.0",
                modality="text",
                use_case=use_case,
                deployment_context="local",
            )
        )
    )


def test_gap_report_has_a_row_per_mapped_article():
    risk_result = _make_risk_result("customer support chatbot")
    report = build_gap_report("test-sys", "HEAD", risk_result=risk_result)
    articles = {row.article for row in report.articles}
    assert "Art. 5" in articles
    assert "Art. 6" in articles
    assert "Art. 25" in articles


def test_gap_report_reflects_rule_pass_as_met():
    risk_result = _make_risk_result("customer support chatbot")
    report = build_gap_report("test-sys", "HEAD", risk_result=risk_result)
    art5 = next(row for row in report.articles if row.article == "Art. 5")
    art25 = next(row for row in report.articles if row.article == "Art. 25")
    assert art5.status == GapStatus.MET
    assert art25.status == GapStatus.MET


def test_gap_report_reflects_rule_fail_as_missing():
    risk_result = _make_risk_result("employment screening and ranking")
    report = build_gap_report("test-sys", "HEAD", risk_result=risk_result)
    art6 = next(row for row in report.articles if row.article == "Art. 6")
    assert art6.status == GapStatus.MISSING
    assert art6.evidence_ref == "EU_AIA_ART6_HIGH_RISK"


def test_gap_report_is_unverified_without_any_source():
    report = build_gap_report("test-sys", "HEAD")
    for row in report.articles:
        assert row.status == GapStatus.UNVERIFIED


def test_gap_report_round_trips_through_json():
    risk_result = _make_risk_result("customer support chatbot")
    report = build_gap_report("test-sys", "HEAD", risk_result=risk_result)
    from opencomplai_core.models import GapReport

    restored = GapReport.model_validate_json(report.model_dump_json())
    assert restored == report


def test_scan_discrepancy_surfaces_as_missing_even_when_rule_passes():
    risk_result = _make_risk_result("customer support chatbot")

    corroboration_report = CorroborationReport.model_validate(
        {
            "scan_id": "scan-1",
            "system_id": "test-sys",
            "commit_ref": "HEAD",
            "scanner_version": "0.1.0",
            "input_digest": "sha256:abc",
            "config_hash": "sha256:def",
            "detector_versions": {},
            "declared_purpose": "customer support chatbot",
            "declared_categories": [],
            "evidence": [],
            "findings": [
                {
                    "finding_id": "find_1",
                    "signal_category": "biometric",
                    "evidence_ids": [],
                    "locations": ["src/face.py:1"],
                    "mapped_taxonomy": [],
                    "strength": 1.0,
                    "scope": "prod",
                    "reachability": "reachable_entrypoint",
                    "confidence_rationale": [],
                    "reviewer_prompt": "",
                }
            ],
            "detected_categories": ["biometric"],
            "discrepancies": ["biometric"],
            "score_breakdown": {},
            "severity": "major",
            "feature_summary": {},
            "cache_summary": {},
            "skipped_paths": [],
            "limits_hit": [],
            "warnings": [],
            "detector_errors": [],
            "baseline_ref": None,
            "generated_at": "2026-07-11T00:00:00Z",
            "report_hash": "sha256:ghi",
        }
    )

    report = build_gap_report(
        "test-sys",
        "HEAD",
        risk_result=risk_result,
        corroboration_report=corroboration_report,
    )
    art6 = next(row for row in report.articles if row.article == "Art. 6")
    assert art6.status == GapStatus.MISSING
    assert art6.source.value == "scan"


def test_art_10_and_15_are_unverified_without_an_eval_report():
    """1.5: no sample set supplied -> UNVERIFIED, not MISSING (evaluator never ran)."""
    risk_result = _make_risk_result("customer support chatbot")
    report = build_gap_report("test-sys", "HEAD", risk_result=risk_result)
    art10 = next(row for row in report.articles if row.article == "Art. 10")
    art15 = next(row for row in report.articles if row.article == "Art. 15")
    assert art10.status == GapStatus.UNVERIFIED
    assert art15.status == GapStatus.UNVERIFIED


def test_art_15_is_missing_when_safety_evaluator_fails():
    """1.5: a sample set that fails EVAL_SAFETY_LEXICAL_V1 surfaces Art. 15 as MISSING,
    citing the evaluator's evidence_hash and reference in the rationale."""
    risk_result = _make_risk_result("customer support chatbot")
    sample_set = EvalSampleSet(
        eval_set_id="s1",
        system_id="test-sys",
        outputs=["this contains kill instructions"],
    )
    eval_report = run_evals("test-sys", "HEAD", sample_set)

    report = build_gap_report(
        "test-sys", "HEAD", risk_result=risk_result, eval_report=eval_report
    )
    art15 = next(row for row in report.articles if row.article == "Art. 15")
    assert art15.status == GapStatus.MISSING
    assert art15.source.value == "evaluator"
    failed_result = next(
        r for r in eval_report.results if r.evaluator_id == "EVAL_SAFETY_LEXICAL_V1"
    )
    assert art15.evidence_ref == failed_result.evidence_hash
    assert failed_result.reference in art15.rationale
