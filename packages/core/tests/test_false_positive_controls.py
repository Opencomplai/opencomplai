"""False-positive controls — docs/test/vendor never MAJOR alone."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.models import DiscrepancySeverity, EvidenceScope
from opencomplai_core.scan_engine import run_scan


def test_docs_only_openai_not_major(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text(
        "We use openai for demos.\n", encoding="utf-8"
    )
    report = run_scan("s", "HEAD", tmp_path, "analytics dashboard")
    assert report.severity != DiscrepancySeverity.MAJOR
    assert report.severity != DiscrepancySeverity.CRITICAL


def test_test_only_dependency_not_major(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ai.py").write_text("import openai\n", encoding="utf-8")
    report = run_scan("s", "HEAD", tmp_path, "rule-based scoring")
    prod_evidence = [e for e in report.evidence if e.scope == EvidenceScope.PROD]
    assert report.severity != DiscrepancySeverity.MAJOR or not prod_evidence


def test_requirements_md_not_parsed_as_manifest(tmp_path: Path):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs" / "requirements.md").write_text(
        "optional but recommended: scoring module\n", encoding="utf-8"
    )
    report = run_scan("s", "HEAD", tmp_path, "analytics dashboard")
    assert "scoring" not in report.discrepancies


def test_weak_docs_findings_excluded_from_discrepancies(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "requirements.txt").write_text("scoring\n", encoding="utf-8")
    report = run_scan("s", "HEAD", tmp_path, "analytics dashboard")
    docs_findings = [f for f in report.findings if f.scope == EvidenceScope.DOCS]
    assert docs_findings
    assert docs_findings[0].strength < 0.5
    assert "scoring" not in report.discrepancies


def test_lockfile_only_in_requirements_minor_or_less(tmp_path: Path):
    (tmp_path / "requirements-dev.txt").write_text("torch\n", encoding="utf-8")
    report = run_scan("s", "HEAD", tmp_path, "customer support chatbot")
    assert report.severity in (
        DiscrepancySeverity.NONE,
        DiscrepancySeverity.INFO,
        DiscrepancySeverity.MINOR,
    )
