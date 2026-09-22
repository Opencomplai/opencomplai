"""Tests for the NIST AI RMF 1.0 subcategory re-projection (CP-16, D-3c).

`build_nist_rmf_report` re-projects an existing `GapReport` (already-computed
EU_AI_ACT evidence) into per-subcategory verdicts via
`data/framework_crosswalk.json` -- no new scanner/evaluator involved. The four
golden scenarios below (GOVERN/MAP/MEASURE/MANAGE) are this epic's required
"at least one subcategory per RMF function" fixtures.
"""

from __future__ import annotations

from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    GapReport,
    GapStatus,
)
from opencomplai_core.nist_rmf_report import build_nist_rmf_report


def _make_report(rows: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at="2026-09-18T00:00:00Z",
        articles=rows,
    )


class TestShape:
    def test_all_72_subcategories_present(self):
        report = build_nist_rmf_report(_make_report([]))
        assert len(report.subcategories) == 72

    def test_system_id_and_commit_ref_carried_through(self):
        report = build_nist_rmf_report(_make_report([]))
        assert report.system_id == "test-sys"
        assert report.commit_ref == "HEAD"

    def test_no_article_evidence_is_unverified_not_fabricated(self):
        """Every subcategory with an empty gap report must be UNVERIFIED /
        not_assessed -- never a guessed-confident verdict (CP-16 guardrail)."""
        report = build_nist_rmf_report(_make_report([]))
        for row in report.subcategories:
            assert row.status == GapStatus.UNVERIFIED
            assert row.confidence_label == ConfidenceLabel.NOT_ASSESSED
            assert row.mapping_confidence is None

    def test_every_row_needs_founder_review(self):
        report = build_nist_rmf_report(_make_report([]))
        for row in report.subcategories:
            assert row.needs_founder_review is True


class TestGovernGoldenScenario:
    """Art. 17 (Quality management system) crosswalks to GOVERN 1 at
    confidence=medium -- the most direct mapping in framework_crosswalk.json."""

    def test_govern_1_1_reprojects_art_17_missing(self):
        report = build_nist_rmf_report(
            _make_report(
                [
                    ArticleGapStatus(
                        article="Art. 17",
                        status=GapStatus.MISSING,
                        source=ArticleGapSource.OBLIGATION,
                        evidence_ref="provider_qms",
                    )
                ]
            )
        )
        row = next(r for r in report.subcategories if r.subcategory == "GOVERN 1.1")
        assert row.status == GapStatus.MISSING
        assert row.mapping_confidence == "medium"
        assert row.confidence_label == ConfidenceLabel.HEURISTIC_ESTIMATE
        assert "Art. 17" in row.source_eu_ai_act_articles
        assert "Art. 17" in row.rationale
        assert "provider_qms" in row.rationale


class TestMapGoldenScenario:
    """Art. 10 (Data and data governance) crosswalks to MAP 2 at
    confidence=medium."""

    def test_map_2_1_reprojects_art_10_met(self):
        report = build_nist_rmf_report(
            _make_report(
                [
                    ArticleGapStatus(
                        article="Art. 10",
                        status=GapStatus.MET,
                        source=ArticleGapSource.RULE,
                        evidence_ref="EU_AIA_ART10_DATA_GOVERNANCE",
                    )
                ]
            )
        )
        row = next(r for r in report.subcategories if r.subcategory == "MAP 2.1")
        assert row.status == GapStatus.MET
        assert row.mapping_confidence == "medium"
        assert row.source_eu_ai_act_articles == ["Art. 10"]

    def test_map_2_2_gets_the_same_reprojection_as_map_2_1(self):
        """The crosswalk maps at category granularity ("MAP 2"), so every
        subcategory under it shares the same re-projected verdict -- this is
        the honest consequence of the crosswalk's own resolution."""
        report = build_nist_rmf_report(
            _make_report(
                [
                    ArticleGapStatus(
                        article="Art. 10",
                        status=GapStatus.MET,
                        source=ArticleGapSource.RULE,
                        evidence_ref="EU_AIA_ART10_DATA_GOVERNANCE",
                    )
                ]
            )
        )
        row_1 = next(r for r in report.subcategories if r.subcategory == "MAP 2.1")
        row_2 = next(r for r in report.subcategories if r.subcategory == "MAP 2.2")
        assert row_1.status == row_2.status
        assert row_1.mapping_confidence == row_2.mapping_confidence


class TestMeasureGoldenScenario:
    """Art. 15 (Accuracy, robustness and cybersecurity) crosswalks to
    MEASURE 2 at confidence=low -- low confidence must survive, not upgrade."""

    def test_measure_2_1_reprojects_art_15_partial_at_low_confidence(self):
        report = build_nist_rmf_report(
            _make_report(
                [
                    ArticleGapStatus(
                        article="Art. 15",
                        status=GapStatus.PARTIAL,
                        source=ArticleGapSource.EVALUATOR,
                        evidence_ref="sha256:deadbeef",
                        # A highly "measured" underlying signal...
                        confidence=0.95,
                        confidence_label=ConfidenceLabel.MEASURED,
                    )
                ]
            )
        )
        row = next(r for r in report.subcategories if r.subcategory == "MEASURE 2.1")
        assert row.status == GapStatus.PARTIAL
        # ...must NOT upgrade the crosswalk's own "low" mapping confidence.
        assert row.mapping_confidence == "low"
        assert row.confidence_label == ConfidenceLabel.HEURISTIC_ESTIMATE


class TestManageGoldenScenario:
    """CP-5's crosswalk has zero rows mapping to MANAGE -- every MANAGE
    subcategory must stay UNVERIFIED/not_assessed regardless of what the gap
    report contains, never a fabricated verdict for an uncovered function."""

    def test_manage_1_1_is_unverified_even_with_unrelated_evidence_present(self):
        report = build_nist_rmf_report(
            _make_report(
                [
                    ArticleGapStatus(
                        article="Art. 9",
                        status=GapStatus.MET,
                        source=ArticleGapSource.RULE,
                        evidence_ref="EU_AIA_ART9_RISK_MGMT",
                    )
                ]
            )
        )
        row = next(r for r in report.subcategories if r.subcategory == "MANAGE 1.1")
        assert row.status == GapStatus.UNVERIFIED
        assert row.mapping_confidence is None
        assert row.confidence_label == ConfidenceLabel.NOT_ASSESSED
        assert row.source_eu_ai_act_articles == []
        assert "no EU-AI-Act-native evidence" in row.rationale.lower() or (
            "no eu-ai-act-native" in row.rationale.lower()
        )


class TestWorstCaseRollup:
    """When a category maps to more than one article, the subcategory's
    verdict is the worst (most severe) status among the present ones, and
    the lowest (worst) crosswalk confidence -- mirroring principle_report's
    STATUS_SEVERITY rollup."""

    def test_govern_1_takes_the_missing_over_the_met(self):
        # Art. 9 and Art. 17 both crosswalk to GOVERN 1 (medium each).
        report = build_nist_rmf_report(
            _make_report(
                [
                    ArticleGapStatus(
                        article="Art. 9",
                        status=GapStatus.MET,
                        source=ArticleGapSource.RULE,
                        evidence_ref="EU_AIA_ART9_RISK_MGMT",
                    ),
                    ArticleGapStatus(
                        article="Art. 17",
                        status=GapStatus.MISSING,
                        source=ArticleGapSource.OBLIGATION,
                        evidence_ref="provider_qms",
                    ),
                ]
            )
        )
        row = next(r for r in report.subcategories if r.subcategory == "GOVERN 1.1")
        assert row.status == GapStatus.MISSING
        assert set(row.source_eu_ai_act_articles) == {"Art. 9", "Art. 17"}


class TestNistRmfReportRoundTrips:
    def test_json_round_trip(self):
        from opencomplai_core.models import NistRmfReport

        report = build_nist_rmf_report(_make_report([]))
        restored = NistRmfReport.model_validate_json(report.model_dump_json())
        assert len(restored.subcategories) == 72
