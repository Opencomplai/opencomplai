"""Tests for the NIST AI RMF 1.0 subcategory re-projection (CP-16, D-3c).

`build_nist_rmf_report` re-projects an existing `GapReport` (already-computed
EU_AI_ACT evidence) into per-subcategory verdicts via each subcategory's own
`eu_ai_act` mapping in `data/nist_ai_rmf_subcategories.json` -- no new
scanner/evaluator involved. Subcategories with no EU AI Act mapping take a
provider attestation instead. The golden scenarios below cover at least one
subcategory per RMF function.
"""

from __future__ import annotations

from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    Attestation,
    ConfidenceLabel,
    GapReport,
    GapStatus,
)
from opencomplai_core.nist_rmf_report import (
    attestable_subcategories,
    build_nist_rmf_report,
    nist_rmf_as_gap_report,
)

_ATTESTATION = Attestation(
    statement="Resourcing and non-AI alternatives are reviewed each quarter.",
    attested_by="cto@example.com",
    attested_at="2026-11-02",
)


def _make_report(rows: list[ArticleGapStatus]) -> GapReport:
    return GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at="2026-09-18T00:00:00Z",
        articles=rows,
    )


def _row(article: str, status: GapStatus, **extra) -> ArticleGapStatus:
    return ArticleGapStatus(
        article=article,
        status=status,
        source=extra.pop("source", ArticleGapSource.RULE),
        evidence_ref=extra.pop("evidence_ref", f"ref-{article}"),
        **extra,
    )


def _sub(report, subcategory: str):
    return next(r for r in report.subcategories if r.subcategory == subcategory)


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
    def test_govern_1_2_reprojects_art_17_missing_at_low(self):
        report = build_nist_rmf_report(
            _make_report(
                [_row("Art. 17", GapStatus.MISSING, evidence_ref="provider_qms")]
            )
        )
        row = _sub(report, "GOVERN 1.2")
        assert row.status == GapStatus.MISSING
        assert row.mapping_confidence == "low"
        assert row.confidence_label == ConfidenceLabel.HEURISTIC_ESTIMATE
        assert row.source_eu_ai_act_articles == ["Art. 17"]
        assert "provider_qms" in row.rationale


class TestMapGoldenScenario:
    def test_map_2_3_reprojects_art_10_met(self):
        report = build_nist_rmf_report(_make_report([_row("Art. 10", GapStatus.MET)]))
        row = _sub(report, "MAP 2.3")
        assert row.status == GapStatus.MET
        assert row.mapping_confidence == "medium"
        assert row.source_eu_ai_act_articles == ["Art. 10"]

    def test_mapping_is_per_subcategory_not_per_category(self):
        """MAP 2.1 maps to Art. 11, not Art. 10: evidence for one article no
        longer spreads over every subcategory of a category."""
        report = build_nist_rmf_report(_make_report([_row("Art. 10", GapStatus.MET)]))
        row = _sub(report, "MAP 2.1")
        assert row.status == GapStatus.UNVERIFIED
        assert row.source_eu_ai_act_articles == ["Art. 11"]
        assert "none of those articles are present" in row.rationale


class TestMeasureGoldenScenario:
    def test_measure_2_5_keeps_low_confidence_over_measured_evidence(self):
        report = build_nist_rmf_report(
            _make_report(
                [
                    _row(
                        "Art. 15",
                        GapStatus.PARTIAL,
                        source=ArticleGapSource.EVALUATOR,
                        evidence_ref="sha256:deadbeef",
                        confidence=0.95,
                        confidence_label=ConfidenceLabel.MEASURED,
                    )
                ]
            )
        )
        row = _sub(report, "MEASURE 2.5")
        assert row.status == GapStatus.PARTIAL
        assert row.mapping_confidence == "low"
        assert row.confidence_label == ConfidenceLabel.HEURISTIC_ESTIMATE


class TestManageGoldenScenario:
    def test_manage_1_3_reprojects_art_9(self):
        report = build_nist_rmf_report(_make_report([_row("Art. 9", GapStatus.MET)]))
        row = _sub(report, "MANAGE 1.3")
        assert row.status == GapStatus.MET
        assert row.mapping_confidence == "medium"

    def test_manage_2_1_has_no_eu_evidence_and_asks_for_an_attestation(self):
        report = build_nist_rmf_report(_make_report([_row("Art. 9", GapStatus.MET)]))
        row = _sub(report, "MANAGE 2.1")
        assert row.status == GapStatus.UNVERIFIED
        assert row.confidence_label == ConfidenceLabel.NOT_ASSESSED
        assert row.source_eu_ai_act_articles == []
        assert "framework_inputs.NIST_AI_RMF.attested" in row.rationale


class TestAttestation:
    def test_attestable_set_is_exactly_the_unmapped_subcategories(self):
        assert "NIST_AI_RMF:MANAGE 2.1" in attestable_subcategories()
        assert "NIST_AI_RMF:MANAGE 1.3" not in attestable_subcategories()

    def test_attestation_makes_an_unmapped_subcategory_met(self):
        report = build_nist_rmf_report(
            _make_report([]), {"NIST_AI_RMF:MANAGE 2.1": _ATTESTATION}
        )
        row = _sub(report, "MANAGE 2.1")
        assert row.status == GapStatus.MET
        assert row.confidence_label == ConfidenceLabel.ATTESTED
        assert row.rationale == _ATTESTATION.statement

    def test_attestation_is_ignored_where_eu_evidence_decides(self):
        report = build_nist_rmf_report(
            _make_report([_row("Art. 9", GapStatus.MISSING)]),
            {"NIST_AI_RMF:MANAGE 1.3": _ATTESTATION},
        )
        assert _sub(report, "MANAGE 1.3").status == GapStatus.MISSING

    def test_gap_report_view_marks_attested_rows(self):
        report = nist_rmf_as_gap_report(
            _make_report([]), {"NIST_AI_RMF:MANAGE 2.1": _ATTESTATION}
        )
        row = next(r for r in report.articles if r.article == "NIST_AI_RMF:MANAGE 2.1")
        assert row.source == ArticleGapSource.ATTESTATION
        assert row.evidence_ref == "attestation:cto@example.com@2026-11-02"
        other = next(
            r for r in report.articles if r.article == "NIST_AI_RMF:MANAGE 1.3"
        )
        assert other.source == ArticleGapSource.CROSSWALK


class TestWorstCaseRollup:
    """When a subcategory maps to more than one article, its verdict is the
    worst (most severe) status among the present ones, and the lowest mapping
    confidence -- mirroring principle_report's STATUS_SEVERITY rollup."""

    def test_govern_1_4_takes_the_missing_over_the_met(self):
        # GOVERN 1.4 maps Art. 9 (medium) and Art. 17 (low).
        report = build_nist_rmf_report(
            _make_report(
                [_row("Art. 9", GapStatus.MET), _row("Art. 17", GapStatus.MISSING)]
            )
        )
        row = _sub(report, "GOVERN 1.4")
        assert row.status == GapStatus.MISSING
        assert row.mapping_confidence == "low"
        assert set(row.source_eu_ai_act_articles) == {"Art. 9", "Art. 17"}


class TestNistRmfReportRoundTrips:
    def test_json_round_trip(self):
        from opencomplai_core.models import NistRmfReport

        report = build_nist_rmf_report(_make_report([]))
        restored = NistRmfReport.model_validate_json(report.model_dump_json())
        assert len(restored.subcategories) == 72
