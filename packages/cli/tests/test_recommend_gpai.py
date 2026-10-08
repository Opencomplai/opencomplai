"""`opencomplai recommend` reaches the GPAI copyright and summary drafts (SU-135c)."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _run(tmp_path: Path, gpai: bool) -> Path:
    manifest = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "gpai-fixture",
            "--intended-purpose",
            "general-purpose model",
            "--output",
            str(manifest),
        ],
    )
    assert result.exit_code == 0, result.output
    if gpai:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["checker_session"] = {
            "checker_version": "t",
            "session_id": "s",
            "completed_at": "2026-01-01T00:00:00Z",
            "obligation_ids": ["gpai_provider"],
        }
        manifest.write_text(json.dumps(data), encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "fixes"
    result = runner.invoke(
        app,
        [
            "recommend",
            "--manifest",
            str(manifest),
            "--output",
            str(out),
            "--repo-root",
            str(repo),
        ],
    )
    assert result.exit_code == 0, result.output
    return out


def test_recommend_writes_gpai_extras_for_gpai_session(tmp_path):
    out = _run(tmp_path, gpai=True)
    assert (out / "art53-gpai_copyright_policy.md").is_file()
    assert (out / "art53-gpai_training_summary.md").is_file()


def test_recommend_without_session_writes_no_gpai_extras(tmp_path):
    out = _run(tmp_path, gpai=False)
    assert not (out / "art53-gpai_copyright_policy.md").exists()
    assert not (out / "art53-gpai_training_summary.md").exists()
