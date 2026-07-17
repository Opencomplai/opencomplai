"""CLI `scan --quick` — zero-config discovery mode."""

from __future__ import annotations

from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _biometric_repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "face.py").write_text(
        "import face_recognition\n", encoding="utf-8"
    )
    return tmp_path


def test_quick_scan_runs_without_a_manifest(tmp_path):
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        ["scan", "--quick", "--repo-root", str(repo), "--no-ocignore-bootstrap"],
    )
    assert result.exit_code == 0
    assert "Discovery only" in result.stdout


def test_quick_scan_exits_zero_regardless_of_findings(tmp_path):
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        [
            "scan",
            "--quick",
            "--repo-root",
            str(repo),
            "--no-ocignore-bootstrap",
            "--fail-on",
            "critical",
        ],
    )
    assert result.exit_code == 0


def test_quick_scan_does_not_emit_evidence_even_when_requested(tmp_path):
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        [
            "scan",
            "--quick",
            "--repo-root",
            str(repo),
            "--no-ocignore-bootstrap",
            "--emit-evidence",
        ],
    )
    assert result.exit_code == 0
    assert "Discovery only" in result.stdout


def test_quick_scan_prints_suggested_init_command_when_categories_detected(tmp_path):
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        ["scan", "--quick", "--repo-root", str(repo), "--no-ocignore-bootstrap"],
    )
    assert result.exit_code == 0
    assert "opencomplai init" in result.stdout
    assert "biometric" in result.stdout


def test_quick_scan_on_clean_repo_has_no_suggested_purpose(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["scan", "--quick", "--repo-root", str(tmp_path), "--no-ocignore-bootstrap"],
    )
    assert result.exit_code == 0
    assert "No AI signals detected" in result.stdout


def test_quick_scan_does_not_write_compliance_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = _biometric_repo(tmp_path)
    result = runner.invoke(
        app,
        ["scan", "--quick", "--repo-root", str(repo), "--no-ocignore-bootstrap"],
    )
    assert result.exit_code == 0
    assert not (tmp_path / "compliance-artifact.json").exists()
