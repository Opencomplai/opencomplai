"""Tests for remediation template rendering (opencomplai recommend)."""

from opencomplai_core.models import ArticleGapSource, ArticleGapStatus, GapReport, GapStatus
from opencomplai_core.recommend_engine import render_recommendations


def _make_report(rows: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at="2026-07-11T00:00:00Z",
        articles=rows,
    )


def test_writes_one_file_per_missing_row(tmp_path):
    report = _make_report(
        [
            ArticleGapStatus(
                article="Art. 6",
                status=GapStatus.MISSING,
                source=ArticleGapSource.RULE,
                evidence_ref="EU_AIA_ART6_HIGH_RISK",
                rationale="test rationale",
            )
        ]
    )
    written = render_recommendations(report, tmp_path)
    assert len(written) == 1
    assert written[0].exists()
    content = written[0].read_text()
    assert "Art. 6" in content
    assert "EU_AIA_ART6_HIGH_RISK" in content
    assert "test rationale" in content


def test_no_output_for_met_rows(tmp_path):
    report = _make_report(
        [
            ArticleGapStatus(
                article="Art. 25",
                status=GapStatus.MET,
                source=ArticleGapSource.RULE,
                evidence_ref="EU_AIA_ART25_MODIFICATION_TRAP",
                rationale="no modification declared",
            )
        ]
    )
    written = render_recommendations(report, tmp_path)
    assert written == []


def test_no_output_for_unverified_rows(tmp_path):
    report = _make_report(
        [
            ArticleGapStatus(
                article="Art. 50",
                status=GapStatus.UNVERIFIED,
                source=ArticleGapSource.OBLIGATION,
                evidence_ref="transparency",
                rationale="no automated verification run",
            )
        ]
    )
    written = render_recommendations(report, tmp_path)
    assert written == []


def test_partial_row_also_produces_template(tmp_path):
    report = _make_report(
        [
            ArticleGapStatus(
                article="Art. 10",
                status=GapStatus.PARTIAL,
                source=ArticleGapSource.EVALUATOR,
                evidence_ref="EVAL_BIAS_FAIRNESS_V1",
                rationale="borderline fairness metric",
            )
        ]
    )
    written = render_recommendations(report, tmp_path)
    assert len(written) == 1


def test_unmapped_article_is_skipped_without_error(tmp_path):
    report = _make_report(
        [
            ArticleGapStatus(
                article="Art. 99",
                status=GapStatus.MISSING,
                source=ArticleGapSource.RULE,
                evidence_ref="NONEXISTENT_RULE",
                rationale="no template mapping exists for this article",
            )
        ]
    )
    written = render_recommendations(report, tmp_path)
    assert written == []
