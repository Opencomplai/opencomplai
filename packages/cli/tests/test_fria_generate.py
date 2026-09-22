"""CLI test for `opencomplai fria generate` (CP-14, D-1).

End-to-end: `opencomplai checker` exports a real checker session
(high-risk-deployer scenario, matching the golden fixture
`07_high_risk_deployer_fria.json`), `opencomplai init` writes a manifest that
references it plus the Section 2/3 fields a real deployer would supply, then
`opencomplai fria generate` drafts a populated Art. 27(1)(a)-(f) document in
both Markdown and JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _build_manifest_with_checker_session(tmp_path: Path) -> Path:
    answers_file = tmp_path / "answers.json"
    answers_file.write_text(
        json.dumps(
            {
                "answers": {
                    "gate_is_ai_system": True,
                    "e1_entity_type": "deployer",
                    "hr2_annex_iii": True,
                    "s1_in_scope": True,
                    "r5_fria": True,
                }
            }
        ),
        encoding="utf-8",
    )

    checker_report = tmp_path / "checker-report.json"
    result = runner.invoke(
        app,
        [
            "checker",
            "--answers",
            str(answers_file),
            "--export-json",
            str(checker_report),
        ],
    )
    assert result.exit_code == 0, result.output
    checker_data = json.loads(checker_report.read_text(encoding="utf-8"))
    assert "fria" in [o["id"] for o in checker_data["obligations"]]

    extras_file = tmp_path / "extras.json"
    extras_file.write_text(
        json.dumps(
            {
                "known_limitations": [
                    "May mis-score applicants near the credit threshold"
                ],
                "human_oversight_measures": [
                    "A human reviewer confirms every denial before it is issued"
                ],
                "operator_role": "deployer",
                "checker_session": {
                    "checker_version": checker_data["checker_version"],
                    "session_id": checker_data["session_id"] or "test-session",
                    "completed_at": "2026-09-18T00:00:00+00:00",
                    "report_json_path": str(checker_report),
                },
            }
        ),
        encoding="utf-8",
    )

    manifest_file = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "credit-scoring-deployer",
            "--intended-purpose",
            "Score loan applicants for a public housing authority",
            "--high-risk-presumption",
            "--incident-response-procedure",
            "Complaints routed to the compliance officer within 2 business days",
            "--section-extras-file",
            str(extras_file),
            "--output",
            str(manifest_file),
        ],
    )
    assert result.exit_code == 0, result.output
    return manifest_file


def test_fria_generate_produces_populated_markdown_and_json(tmp_path: Path):
    manifest_file = _build_manifest_with_checker_session(tmp_path)
    output_dir = tmp_path / "fria"

    result = runner.invoke(
        app,
        [
            "fria",
            "generate",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "5/6 points" in result.output

    json_files = list(output_dir.glob("fria_*.json"))
    md_files = list(output_dir.glob("fria_*.md"))
    assert len(json_files) == 1, result.output
    assert len(md_files) == 1, result.output

    document = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert document["system_id"] == "credit-scoring-deployer"
    assert document["entity_role"] == "deployer"
    assert document["is_high_risk"] is True
    assert "fria" in document["trigger_obligation_ids"]
    assert document["populated_point_count"] == 5
    by_point = {p["point"]: p for p in document["points"]}
    assert by_point["a"]["populated"] is True
    assert "Score loan applicants" in by_point["a"]["assessment"]
    assert by_point["b"]["populated"] is False
    assert by_point["c"]["populated"] is True
    assert by_point["d"]["populated"] is True
    assert by_point["e"]["populated"] is True
    assert by_point["f"]["populated"] is True

    markdown = md_files[0].read_text(encoding="utf-8")
    assert "{{" not in markdown  # every placeholder substituted
    assert "Score loan applicants" in markdown
    assert "mis-score applicants" in markdown
    assert "human reviewer" in markdown
    assert "compliance officer" in markdown
    # (b) has no data source, and Owner is never auto-filled -- both stay honest.
    assert "_fill in_" in markdown


def test_fria_generate_missing_manifest_exits_2(tmp_path: Path):
    result = runner.invoke(
        app,
        ["fria", "generate", "--manifest", str(tmp_path / "does-not-exist.json")],
    )
    assert result.exit_code == 2
