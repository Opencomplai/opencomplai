"""CLI test for `opencomplai qms generate` (CP-15).

Fixture mirrors `test_recommend_qms_clauses.py`'s exact 6/13 present split,
per CP-15's own Accept criterion ("matching CP-7's own Accept criterion's
exact split, for consistency").
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

_FILLED = (
    "This procedure documents regulatory compliance, design control, quality "
    "assurance, testing validation, technical specifications and standards, "
    "data governance, risk management, post-market monitoring, incident "
    "reporting, authority communication, record retention, resource planning "
    "and accountability.\n"
)

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


def test_qms_generate_shows_per_clause_status_not_one_article_verdict(
    tmp_path: Path,
) -> None:
    for name in _PRESENT_CLAUSE_FILES:
        (tmp_path / name).write_text(_FILLED, encoding="utf-8")

    output_file = tmp_path / "qms-document.md"
    result = runner.invoke(
        app,
        [
            "qms",
            "generate",
            "--system-id",
            "qms-fixture",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output_file),
            # No scan-report.json/eval-report.json in tmp_path -- absence
            # stays honest, cwd-relative defaults must not leak in.
            "--scan-report",
            str(tmp_path / "scan-report.json"),
            "--eval-report",
            str(tmp_path / "eval-report.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "6 present / 7 missing" in result.output

    assert output_file.exists(), result.output
    content = output_file.read_text(encoding="utf-8")
    assert content.count("| Present |") == 6
    assert content.count("| Missing |") == 7
    assert "6 present / 7 missing" in content
    assert "No evidence-vault references supplied" in content


def test_qms_generate_json_output_has_thirteen_clause_rows(tmp_path: Path) -> None:
    for name in _PRESENT_CLAUSE_FILES:
        (tmp_path / name).write_text(_FILLED, encoding="utf-8")

    output_file = tmp_path / "qms-document.md"
    result = runner.invoke(
        app,
        [
            "qms",
            "generate",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output_file),
            "--scan-report",
            str(tmp_path / "scan-report.json"),
            "--eval-report",
            str(tmp_path / "eval-report.json"),
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["clauses"]) == 13
    assert (payload["present_count"], payload["missing_count"]) == (6, 7)
    statuses = {c["clause"]: c["status_label"] for c in payload["clauses"]}
    assert statuses["Art. 17(1)(a)"] == "Present"
    assert statuses["Art. 17(1)(g)"] == "Missing"


def test_recommend_and_generate_agree_clause_by_clause(tmp_path: Path) -> None:
    filled = (
        "REGULATORY_COMPLIANCE_STRATEGY.md",
        "DESIGN_CONTROL.md",
        "TESTING_VALIDATION.md",
    )
    scaffold = ("QUALITY_MANAGEMENT_PROCEDURES.md", "TECHNICAL_DOCUMENTATION.md")
    for name in filled:
        (tmp_path / name).write_text(_FILLED, encoding="utf-8")
    for name in scaffold:
        (tmp_path / name).write_text(
            "# Procedure\n\n| Owner | _fill in_ |\n", encoding="utf-8"
        )

    manifest_file = tmp_path / "system-manifest.json"
    init = runner.invoke(
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
    assert init.exit_code == 0, init.output
    fixes = tmp_path / "fixes"  # outside docs/, never inside a probed path
    rec = runner.invoke(
        app,
        [
            "recommend",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--output",
            str(fixes),
        ],
    )
    assert rec.exit_code == 0, rec.output
    outline = (fixes / "art17-qms_outline.md").read_text(encoding="utf-8")
    recommend_labels = dict(
        re.findall(r"^\| \(([a-m])\) \|[^|]*\| ([^|]+?) \|", outline, re.M)
    )

    gen = runner.invoke(
        app,
        [
            "qms",
            "generate",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "qms-document.md"),
            "--scan-report",
            str(tmp_path / "scan-report.json"),
            "--eval-report",
            str(tmp_path / "eval-report.json"),
            "--output-format",
            "json",
        ],
    )
    assert gen.exit_code == 0, gen.output
    generate_labels = {
        c["clause"][-2]: c["status_label"] for c in json.loads(gen.output)["clauses"]
    }

    assert len(recommend_labels) == len(generate_labels) == 13
    assert recommend_labels == generate_labels
    assert sorted(set(generate_labels.values())) == ["Missing", "Present", "Unfilled"]
    assert sum(v == "Unfilled" for v in generate_labels.values()) == 2
