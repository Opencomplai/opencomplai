"""CLI test for `opencomplai recommend`'s Art. 17 QMS per-clause breakdown (CP-7)."""

from __future__ import annotations

from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

_PRESENT_CLAUSE_FILES = (
    "REGULATORY_COMPLIANCE_STRATEGY.md",  # (a)
    "DESIGN_CONTROL.md",  # (b)
    "QUALITY_MANAGEMENT_PROCEDURES.md",  # (c)
    "TESTING_VALIDATION.md",  # (d)
    "TECHNICAL_DOCUMENTATION.md",  # (e)
    "DATA_GOVERNANCE.md",  # (f)
)
# (g)-(m) intentionally left without evidence: RISK_MANAGEMENT_SYSTEM.md,
# POST_MARKET_MONITORING.md, INCIDENT_REPORTING.md, TRANSPARENCY.md,
# RECORD_KEEPING.md, RESOURCE_MANAGEMENT.md, ACCOUNTABILITY_FRAMEWORK.md


def _write_manifest(tmp_path: Path) -> Path:
    manifest_file = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "qms-fixture",
            "--intended-purpose",
            "biometric identification",
            "--output",
            str(manifest_file),
        ],
    )
    assert result.exit_code == 0, f"init failed: {result.output}"
    return manifest_file


def test_recommend_shows_six_present_seven_missing_not_one_article_verdict(
    tmp_path: Path,
) -> None:
    """Fixture repo has evidence for 6 of 13 Art. 17(1) clauses ((a)-(f)).

    `opencomplai recommend` must report 6 present / 7 missing for Art. 17 —
    not a single pass/fail verdict for the whole article.
    """
    manifest_file = _write_manifest(tmp_path)
    for name in _PRESENT_CLAUSE_FILES:
        (tmp_path / name).write_text("evidence\n", encoding="utf-8")

    output_dir = tmp_path / "fixes"
    result = runner.invoke(
        app,
        [
            "recommend",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Art. 17 QMS per-clause: 6/13 present, 7/13 missing" in result.output

    qms_file = output_dir / "art17-qms_outline.md"
    assert qms_file.exists(), result.output
    content = qms_file.read_text(encoding="utf-8")
    assert content.count("| Present |") == 6
    assert content.count("| Missing |") == 7
    assert "6 present / 7 missing" in content
    assert "{{" not in content  # every placeholder substituted
