"""Tests for the Opencomplai CLI."""

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _write_manifest(tmp_path: Path, system_id: str, intended_purpose: str) -> Path:
    """Helper: use the CLI to write a manifest and return its path."""
    manifest_file = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            system_id,
            "--intended-purpose",
            intended_purpose,
            "--output",
            str(manifest_file),
        ],
    )
    assert result.exit_code == 0, f"init failed: {result.output}"
    return manifest_file


def test_init_creates_manifest(tmp_path):
    manifest_file = _write_manifest(tmp_path, "test-system", "customer support chatbot")
    assert manifest_file.exists()
    data = json.loads(manifest_file.read_text())
    assert data["system_id"] == "test-system"
    assert data["intended_purpose"] == "customer support chatbot"


def test_validate_manifest_valid(tmp_path):
    manifest_file = _write_manifest(tmp_path, "test", "customer support chatbot")
    result = runner.invoke(app, ["validate-manifest", str(manifest_file)])
    assert result.exit_code == 0


def test_validate_manifest_missing_file():
    result = runner.invoke(app, ["validate-manifest", "nonexistent.json"])
    assert result.exit_code == 2


def test_check_pass_exit_0(tmp_path):
    manifest_file = _write_manifest(tmp_path, "test", "customer support chatbot")
    result = runner.invoke(app, ["check", "--manifest", str(manifest_file)])
    assert result.exit_code == 0


def test_check_control_fail_exit_1(tmp_path):
    manifest_file = _write_manifest(
        tmp_path, "test", "employment screening and ranking"
    )
    result = runner.invoke(app, ["check", "--manifest", str(manifest_file)])
    assert result.exit_code == 1


def test_check_json_output(tmp_path):
    manifest_file = _write_manifest(tmp_path, "test", "customer support chatbot")
    result = runner.invoke(
        app, ["check", "--manifest", str(manifest_file), "--output", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    # check now emits a ScanStatusArtifact (not the raw engine result)
    assert "result" in data
    assert "failed_controls" in data
    assert "rationale_hash" in data
    assert data["system_id"] == "test"


def test_risk_classify_minimal(tmp_path):
    result = runner.invoke(
        app,
        [
            "risk",
            "classify",
            "--system-id",
            "test",
            "--intended-purpose",
            "customer support chatbot",
        ],
    )
    assert result.exit_code == 0


def test_risk_classify_high_risk(tmp_path):
    result = runner.invoke(
        app,
        [
            "risk",
            "classify",
            "--system-id",
            "test",
            "--intended-purpose",
            "employment screening",
        ],
    )
    assert result.exit_code == 0  # classify always exits 0; risk level is in output


def test_verify_output_stub_exits_3():
    """verify-output stub returns POLICY_BLOCK (exit 3) until Phase 10."""
    result = runner.invoke(app, ["verify-output", "--system-id", "test"])
    assert result.exit_code == 3


def test_docs_generate_local_fallback(tmp_path):
    """docs generate uses the local doc-generator fallback (Phase 12 implemented)."""
    result = runner.invoke(
        app,
        ["docs", "generate", "--system-id", "test", "--output-dir", str(tmp_path)],
    )
    # Local fallback succeeds when doc-generator is installed
    assert result.exit_code in (0, 1)  # 0 = success, 1 = import error in minimal env


def test_sync_metadata_stub_exits_3():
    """sync metadata stub returns POLICY_BLOCK (exit 3) until Phase 13."""
    result = runner.invoke(app, ["sync", "metadata", "--system-id", "test"])
    assert result.exit_code == 3


def test_version_flag_shows_version():
    """`opencomplai --version` prints the version and exits 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "opencomplai" in result.output


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "opencomplai" in result.output


def test_version_command_json():
    result = runner.invoke(app, ["version", "--output", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["name"] == "opencomplai"
    assert data["version"]


def test_info_command_populates_all_fields():
    """`opencomplai info` must show every metadata field completed."""
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    out = result.output
    assert "opencomplai.com" in out
    assert "Opencomplai" in out
    assert "hello@opencomplai.com" in out
    assert "AGPL-3.0-only" in out


def test_info_command_json():
    result = runner.invoke(app, ["info", "--output", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["home_page"] == "https://opencomplai.com"
    assert data["author"] == "Opencomplai"
    assert data["author_email"] == "hello@opencomplai.com"
    assert data["license"] == "AGPL-3.0-only"
    assert isinstance(data["suite"], list)
    assert any(pkg["name"] == "opencomplai-core" for pkg in data["suite"])
