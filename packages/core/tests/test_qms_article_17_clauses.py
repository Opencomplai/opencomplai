"""Tests for Art. 17(1)(a)-(m) per-clause QMS gap probes (CP-7)."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.gap_probes import (
    QMS_17_1_CLAUSES,
    qms_article_17_clause_statuses,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    GapReport,
    GapStatus,
)
from opencomplai_core.recommend_engine import render_recommendations

_PRESENT_CLAUSE_FILES = {
    "a": "REGULATORY_COMPLIANCE_STRATEGY.md",
    "b": "DESIGN_CONTROL.md",
    "c": "QUALITY_MANAGEMENT_PROCEDURES.md",
    "d": "TESTING_VALIDATION.md",
    "e": "TECHNICAL_DOCUMENTATION.md",
    "f": "DATA_GOVERNANCE.md",
}
# (g)-(m) intentionally left without any matching evidence file:
# RISK_MANAGEMENT_SYSTEM.md, POST_MARKET_MONITORING.md, INCIDENT_REPORTING.md,
# TRANSPARENCY.md, RECORD_KEEPING.md, RESOURCE_MANAGEMENT.md,
# ACCOUNTABILITY_FRAMEWORK.md


def _make_report() -> GapReport:
    return GapReport(
        system_id="test-sys",
        commit_ref="HEAD",
        generated_at="2026-09-18T00:00:00Z",
        articles=[
            ArticleGapStatus(
                article="Art. 17",
                status=GapStatus.MISSING,
                source=ArticleGapSource.ARTIFACT,
                evidence_ref="provider_qms",
                rationale="No conventional QMS documentation/code probe matched.",
            )
        ],
    )


def test_thirteen_clauses_lettered_a_to_m():
    letters = [letter for letter, _ref, _title in QMS_17_1_CLAUSES]
    assert letters == list("abcdefghijklm")
    for letter, ref, _title in QMS_17_1_CLAUSES:
        assert ref == f"provider_qms_17_1_{letter}"


def test_clause_statuses_are_unverified_without_repo_root():
    rows = qms_article_17_clause_statuses(None)
    assert len(rows) == 13
    assert all(r.status == GapStatus.UNVERIFIED for r in rows)


def test_six_of_thirteen_clauses_present_not_one_article_verdict(tmp_path: Path):
    """Accept criteria: evidence for 6/13 clauses -> 6 present / 7 missing,
    never a single pass/fail for the whole article."""
    for filename in _PRESENT_CLAUSE_FILES.values():
        (tmp_path / filename).write_text("evidence\n", encoding="utf-8")

    rows = qms_article_17_clause_statuses(tmp_path)
    assert len(rows) == 13

    by_letter = {row.article.split("(")[-1].rstrip(")"): row for row in rows}
    for letter in _PRESENT_CLAUSE_FILES:
        assert by_letter[letter].status == GapStatus.PARTIAL, letter
    for letter in "ghijklm":
        assert by_letter[letter].status == GapStatus.MISSING, letter

    present = sum(1 for r in rows if r.status == GapStatus.PARTIAL)
    missing = sum(1 for r in rows if r.status == GapStatus.MISSING)
    assert (present, missing) == (6, 7)


def test_recommend_renders_per_clause_status_table(tmp_path: Path):
    for filename in _PRESENT_CLAUSE_FILES.values():
        (tmp_path / filename).write_text("evidence\n", encoding="utf-8")

    written = render_recommendations(
        _make_report(), tmp_path / "fixes", repo_root=tmp_path
    )
    qms_file = next(p for p in written if p.name == "art17-qms_outline.md")
    content = qms_file.read_text(encoding="utf-8")

    assert "{{" not in content  # every placeholder substituted
    assert content.count("| Present |") == 6
    assert content.count("| Missing |") == 7
    assert "6 present / 7 missing" in content
