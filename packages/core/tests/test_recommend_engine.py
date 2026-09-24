"""Tests for remediation template rendering (opencomplai recommend)."""

from pathlib import Path

from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from opencomplai_core.recommend_engine import load_template_map, render_recommendations

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).parent
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)


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


def test_other_framework_row_without_template_gets_generic_requirement(
    tmp_path, monkeypatch
):
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
    report = _make_report(
        [
            ArticleGapStatus(
                article="FIXTURE:REQ-3",
                status=GapStatus.MISSING,
                source=ArticleGapSource.ARTIFACT,
                evidence_ref="deployer_instructions",
                rationale="no deployer instructions found",
            )
        ]
    )
    written = render_recommendations(report, tmp_path)

    assert [path.name for path in written] == ["fixture--req-3-generic_requirement.md"]
    content = written[0].read_text(encoding="utf-8")
    assert "# Requirement Action Plan — FIXTURE:REQ-3" in content
    assert "**Requirement:** Deployer instructions published" in content
    assert "no deployer instructions found" in content
    assert "`framework_inputs.FIXTURE.excluded`" in content
    assert "{{" not in content


def test_eu_file_names_are_unchanged_for_every_template(tmp_path):
    """The slug that now also handles "<FW>:<id>" names EU files as before."""
    template_map = load_template_map()
    report = _make_report(
        [
            ArticleGapStatus(
                article=article,
                status=GapStatus.MISSING,
                source=ArticleGapSource.RULE,
                evidence_ref="RULE",
                rationale="test rationale",
            )
            for article in template_map
        ]
    )
    names = {path.name for path in render_recommendations(report, tmp_path)}

    for article, mapping in template_map.items():
        old_slug = article.lower().replace(" ", "").replace(".", "")
        suffix = Path(mapping["file"]).suffix
        assert f"{old_slug}-{mapping['template_id']}{suffix}" in names
