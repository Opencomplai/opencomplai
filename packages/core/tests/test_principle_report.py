"""Tests for the 6 EU Trustworthy AI principle rollup (opencomplai gaps)."""

from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from opencomplai_core.principle_report import build_principle_summary


def _make_report(rows: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at="2026-07-11T00:00:00Z",
        articles=rows,
    )


def test_all_six_principles_present():
    report = _make_report([])
    summary = build_principle_summary(report)
    ids = {p.principle_id for p in summary.principles}
    assert ids == {
        "technical_robustness_safety",
        "privacy_data_governance",
        "transparency",
        "diversity_non_discrimination_fairness",
        "societal_environmental_wellbeing",
        "accountability",
    }


def test_principle_status_is_unverified_when_no_articles_present():
    report = _make_report([])
    summary = build_principle_summary(report)
    for p in summary.principles:
        assert p.status == GapStatus.UNVERIFIED


def test_principle_rollup_uses_worst_case_status():
    """diversity_non_discrimination_fairness maps Art.5, Art.6, Art.10 -- MISSING wins."""
    report = _make_report(
        [
            ArticleGapStatus(
                article="Art. 5",
                status=GapStatus.MET,
                source=ArticleGapSource.RULE,
                evidence_ref="EU_AIA_ART5_UNACCEPTABLE",
            ),
            ArticleGapStatus(
                article="Art. 6",
                status=GapStatus.MISSING,
                source=ArticleGapSource.RULE,
                evidence_ref="EU_AIA_ART6_HIGH_RISK",
            ),
        ]
    )
    summary = build_principle_summary(report)
    fairness = next(
        p for p in summary.principles if p.principle_id == "diversity_non_discrimination_fairness"
    )
    assert fairness.status == GapStatus.MISSING


def test_gap_report_principle_summary_field_defaults_to_none():
    """Byte-for-byte compatibility: existing GapReport consumers see None by default."""
    report = _make_report([])
    assert report.principle_summary is None


def test_gap_report_round_trips_with_principle_summary_attached():
    report = _make_report(
        [
            ArticleGapStatus(
                article="Art. 5",
                status=GapStatus.MET,
                source=ArticleGapSource.RULE,
                evidence_ref="EU_AIA_ART5_UNACCEPTABLE",
            )
        ]
    )
    summary = build_principle_summary(report)
    report_with_summary = report.model_copy(update={"principle_summary": summary})

    restored = GapReport.model_validate_json(report_with_summary.model_dump_json())
    assert restored.principle_summary is not None
    assert len(restored.principle_summary.principles) == 6
