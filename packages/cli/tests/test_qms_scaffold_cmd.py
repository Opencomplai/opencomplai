"""CLI tests for `opencomplai qms generate --scaffold` (SU-24a1)."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _invoke(tmp_path: Path, *extra: str):
    # --output sits outside docs/ so the rendered document is never probed.
    return runner.invoke(
        app,
        [
            "qms",
            "generate",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "out.md"),
            "--scan-report",
            str(tmp_path / "no-scan.json"),
            "--eval-report",
            str(tmp_path / "no-eval.json"),
            "--output-format",
            "json",
            *extra,
        ],
    )


def test_scaffold_flag_writes_files_and_document_reads_all_unfilled(
    tmp_path: Path,
) -> None:
    result = _invoke(tmp_path, "--scaffold")
    assert result.exit_code == 0, result.output
    assert len(list((tmp_path / "docs" / "qms").glob("*.md"))) == 13
    payload = json.loads(result.output)
    assert len(payload["scaffold"]["created"]) == 13
    assert [c["status_label"] for c in payload["clauses"]] == ["Unfilled"] * 13
    assert payload["present_count"] == 0


def test_scaffold_twice_second_run_creates_nothing(tmp_path: Path) -> None:
    assert _invoke(tmp_path, "--scaffold").exit_code == 0
    payload = json.loads(_invoke(tmp_path, "--scaffold").output)
    assert payload["scaffold"]["created"] == []
    assert len(payload["scaffold"]["skipped"]) == 13


def test_no_scaffold_flag_writes_no_files_and_payload_has_no_scaffold_key(
    tmp_path: Path,
) -> None:
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "docs").exists()
    assert "scaffold" not in json.loads(result.output)


def test_scaffold_on_missing_repo_root_exits_2(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["qms", "generate", "--scaffold", "--repo-root", str(tmp_path / "nope")],
    )
    assert result.exit_code == 2
