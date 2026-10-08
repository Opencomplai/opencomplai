"""`check --output-dir` and the hermetic-cwd guarantee."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "outdir-test",
            "--intended-purpose",
            "customer support chatbot",
            "--output",
            str(path),
        ],
    )
    assert result.exit_code == 0, result.output
    return path


def test_default_writes_to_cwd(tmp_path):
    manifest = _manifest(tmp_path)
    result = runner.invoke(app, ["check", "--manifest", str(manifest)])
    assert result.exit_code == 0, result.output
    assert (Path.cwd() / "compliance-artifact.json").exists()
    assert "Artifact written to compliance-artifact.json" in result.stdout


def test_output_dir_writes_artifact_and_sidecars(tmp_path):
    manifest = _manifest(tmp_path)
    out = tmp_path / "out" / "nested"
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (repo / "src" / "face.py").write_text("import face_recognition\n", encoding="utf-8")

    result = runner.invoke(
        app, ["check", "--manifest", str(manifest), "--output-dir", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert (out / "compliance-artifact.json").exists()
    assert not (Path.cwd() / "compliance-artifact.json").exists()

    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest),
            "--output-dir",
            str(out),
            "--scan",
            "--repo-root",
            str(repo),
        ],
    )
    assert result.exit_code in (0, 1), result.output
    assert (out / "scan-report.json").exists()
    assert not (Path.cwd() / "scan-report.json").exists()


def test_artifact_bytes_identical_with_and_without_output_dir(tmp_path):
    manifest = _manifest(tmp_path)
    args = ["check", "--manifest", str(manifest)]
    assert runner.invoke(app, args).exit_code == 0
    assert (
        runner.invoke(app, [*args, "--output-dir", str(tmp_path / "o")]).exit_code == 0
    )
    a = json.loads((Path.cwd() / "compliance-artifact.json").read_text())
    b = json.loads((tmp_path / "o" / "compliance-artifact.json").read_text())
    volatile = {"timestamp", "generated_at", "scan_id", "id", "duration_ms"}

    def strip(d):
        return {k: v for k, v in d.items() if k not in volatile}

    assert strip(a) == strip(b)


def test_cli_suite_does_not_write_into_repo_root(tmp_path):
    root_artifact = Path(__file__).resolve().parents[3] / "compliance-artifact.json"
    before = root_artifact.stat().st_mtime_ns if root_artifact.exists() else None
    manifest = _manifest(tmp_path)
    runner.invoke(app, ["check", "--manifest", str(manifest)])
    after = root_artifact.stat().st_mtime_ns if root_artifact.exists() else None
    assert before == after
