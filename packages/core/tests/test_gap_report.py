"""Tests for the per-article gap report projection (opencomplai gaps)."""

import itertools

import pytest
from opencomplai_core import gap_report as gap_report_module
from opencomplai_core.engine import assess
from opencomplai_core.eval_engine import run_evals
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    AssessmentInput,
    ConfidenceLabel,
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
    art25 = next(row for row in report.articles if row.article == "Art. 25")
    assert art25.status == GapStatus.MET


def test_passing_rule_does_not_mask_an_unverified_obligation():
    """Art. 5 draws on a rule *and* an obligation with no automated verification.

    The rule passing does not discharge the obligation, so the article reports
    UNVERIFIED rather than MET — an article is only as evidenced as its
    least-evidenced source.
    """
    risk_result = _make_risk_result("customer support chatbot")
    report = build_gap_report("test-sys", "HEAD", risk_result=risk_result)
    art5 = next(row for row in report.articles if row.article == "Art. 5")
    assert art5.status == GapStatus.UNVERIFIED
    assert art5.source.value == "obligation"


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


# --- multi-source aggregation: the worst status wins, whatever the order ---


def _stub_article_map(monkeypatch, statuses: list[GapStatus]) -> None:
    """Map one synthetic article onto N artifact sources with fixed statuses."""
    refs = [f"src{i}" for i in range(len(statuses))]
    by_ref = dict(zip(refs, statuses, strict=True))

    monkeypatch.setattr(
        gap_report_module,
        "load_gap_article_map",
        lambda: {
            "Art. TEST": {"sources": [{"kind": "artifact", "ref": r} for r in refs]}
        },
    )
    monkeypatch.setattr(
        gap_report_module,
        "artifact_gap_status",
        lambda ref, repo_root=None: ArticleGapStatus(
            article="",
            status=by_ref[ref],
            source=ArticleGapSource.ARTIFACT,
            evidence_ref=ref,
            rationale=f"stub {ref}",
            confidence=None,
            confidence_label=ConfidenceLabel.NOT_ASSESSED,
            disclaimer_ref="DISCLAIMER_V1",
        ),
    )


@pytest.mark.parametrize(
    "order",
    list(itertools.permutations([GapStatus.MET, GapStatus.PARTIAL, GapStatus.MISSING])),
    ids=lambda o: "-".join(s.value for s in o),
)
def test_worst_status_wins_regardless_of_source_order(monkeypatch, order):
    """MET -> PARTIAL -> MISSING and every other ordering must all end MISSING.

    The previous rule bucketed MISSING and PARTIAL together, so a strictly worse
    MISSING arriving after a PARTIAL could never overwrite it.
    """
    _stub_article_map(monkeypatch, list(order))
    report = build_gap_report("test-sys", "HEAD")
    row = next(r for r in report.articles if r.article == "Art. TEST")
    assert row.status == GapStatus.MISSING
    assert row.rationale == f"stub src{list(order).index(GapStatus.MISSING)}"


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([GapStatus.PARTIAL, GapStatus.MISSING], GapStatus.MISSING),
        ([GapStatus.MISSING, GapStatus.PARTIAL], GapStatus.MISSING),
        ([GapStatus.MET, GapStatus.PARTIAL], GapStatus.PARTIAL),
        ([GapStatus.PARTIAL, GapStatus.MET], GapStatus.PARTIAL),
        ([GapStatus.MET, GapStatus.UNVERIFIED], GapStatus.UNVERIFIED),
        ([GapStatus.UNVERIFIED, GapStatus.MET], GapStatus.UNVERIFIED),
        ([GapStatus.UNVERIFIED, GapStatus.PARTIAL], GapStatus.PARTIAL),
        ([GapStatus.MISSING, GapStatus.UNVERIFIED], GapStatus.MISSING),
        ([GapStatus.MET, GapStatus.MET], GapStatus.MET),
    ],
)
def test_pairwise_status_precedence(monkeypatch, statuses, expected):
    _stub_article_map(monkeypatch, statuses)
    report = build_gap_report("test-sys", "HEAD")
    row = next(r for r in report.articles if r.article == "Art. TEST")
    assert row.status == expected


def test_failing_leakage_evaluator_overrides_an_earlier_partial_on_art_15():
    """Art. 15 lists the safety evaluator before the leakage one.

    A safety WARN (PARTIAL) followed by a leakage FAIL (MISSING) used to leave the
    article reporting PARTIAL, understating a zero-tolerance PII leak.
    """
    risk_result = _make_risk_result("customer support chatbot")
    outputs = ["how to kill someone", "contact ssn 123-45-6789"]
    outputs += ["a perfectly ordinary reply"] * 48
    sample_set = EvalSampleSet(eval_set_id="s1", system_id="test-sys", outputs=outputs)
    eval_report = run_evals("test-sys", "HEAD", sample_set)

    safety = next(
        r for r in eval_report.results if r.evaluator_id == "EVAL_SAFETY_LEXICAL_V1"
    )
    leakage = next(
        r for r in eval_report.results if r.evaluator_id == "EVAL_DATA_LEAKAGE_V1"
    )
    assert safety.outcome.value == "warn", (
        "precondition: safety must be the PARTIAL source"
    )
    assert leakage.outcome.value == "fail", (
        "precondition: leakage must be the MISSING source"
    )

    report = build_gap_report(
        "test-sys", "HEAD", risk_result=risk_result, eval_report=eval_report
    )
    art15 = next(row for row in report.articles if row.article == "Art. 15")
    assert art15.status == GapStatus.MISSING
    assert art15.evidence_ref == leakage.evidence_hash
