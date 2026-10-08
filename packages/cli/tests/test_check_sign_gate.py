"""SU-3a: `check --sign` gate, stamp-before-sign, env key, real commit ref."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
from opencomplai_cli import main
from opencomplai_cli.check_signing import signing_key_available, stamp_artifact
from opencomplai_cli.main import app
from opencomplai_cli.publish import envelope_signature, prepare_scan_status_artifact
from opencomplai_core.models import ScanStatusArtifact, SystemManifest
from opencomplai_core.signing import generate_keypair, verify_artifact
from typer.testing import CliRunner

runner = CliRunner()
SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "dashboard-saas"
    / "schemas"
    / "first_scan_status.schema.json"
)


def _setup(tmp_path: Path, monkeypatch, *, key: bool = True) -> tuple[Path, Path]:
    """Chdir to tmp_path, isolate env, write a manifest. Returns (manifest, keys dir).

    With `key`, a keypair is generated and `main._SIGNING_KEY` points at it;
    otherwise `main._SIGNING_KEY` points at a nonexistent path.
    """
    monkeypatch.chdir(tmp_path)
    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "SIGNING_KEY_PRIVATE",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    key_dir = tmp_path / "keys"
    if key:
        generate_keypair(key_dir)
        monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    else:
        monkeypatch.setattr(main, "_SIGNING_KEY", tmp_path / "nokey" / "signing.key")
    manifest_file = tmp_path / "system-manifest.json"
    manifest_file.write_text(
        SystemManifest(
            system_id="gate-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    return manifest_file, key_dir


def _artifact_dict(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "compliance-artifact.json").read_text("utf-8"))


def _check(manifest_file: Path, *args: str):
    return runner.invoke(app, ["check", "--manifest", str(manifest_file), *args])


def _bare_artifact() -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="a" * 40,
        result="pass",
        evidence_hashes=[],
        rationale_hash="r",
        duration_ms=1,
    )


def test_sign_without_key_exits_2_and_writes_nothing(tmp_path, monkeypatch):
    manifest_file, _ = _setup(tmp_path, monkeypatch, key=False)
    result = _check(manifest_file, "--sign")
    assert result.exit_code == 2, result.output
    assert not (tmp_path / "compliance-artifact.json").exists()
    assert not (tmp_path / "state").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["system-manifest.json"]


def test_sign_if_available_without_key_warns_and_writes_unsigned(tmp_path, monkeypatch):
    manifest_file, _ = _setup(tmp_path, monkeypatch, key=False)
    result = _check(manifest_file, "--sign-if-available")
    assert result.exit_code == 0, result.output
    assert _artifact_dict(tmp_path)["signature"] is None
    assert "unsigned" in result.output
    assert "OSS unsigned" in result.output


def test_sign_if_available_with_key_signs(tmp_path, monkeypatch):
    manifest_file, key_dir = _setup(tmp_path, monkeypatch)
    result = _check(manifest_file, "--sign-if-available")
    assert result.exit_code == 0, result.output
    artifact = ScanStatusArtifact.model_validate(_artifact_dict(tmp_path))
    assert verify_artifact(artifact, key_dir / "signing.pub") is True


def test_env_key_signature_survives_push_envelope(tmp_path, monkeypatch):
    manifest_file, key_dir = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "_SIGNING_KEY", tmp_path / "nokey" / "signing.key")
    monkeypatch.setenv(
        "SIGNING_KEY_PRIVATE",
        base64.b64encode((key_dir / "signing.key").read_bytes()).decode(),
    )
    result = _check(manifest_file, "--sign")
    assert result.exit_code == 0, result.output

    raw = _artifact_dict(tmp_path)
    assert raw["signature"]
    artifact = ScanStatusArtifact.model_validate(raw)
    assert verify_artifact(artifact, key_dir / "signing.pub")
    prepared = prepare_scan_status_artifact(raw, repo_dir=tmp_path)
    assert envelope_signature(raw, prepared) == raw["signature"]


def test_stamped_fields_are_covered_by_signature(tmp_path, monkeypatch):
    manifest_file, key_dir = _setup(tmp_path, monkeypatch)
    assert _check(manifest_file, "--sign").exit_code == 0
    artifact = ScanStatusArtifact.model_validate(_artifact_dict(tmp_path))
    assert artifact.timestamp
    assert artifact.policy_bundle_version
    tampered = artifact.model_copy(update={"timestamp": "2000-01-01T00:00:00Z"})
    assert verify_artifact(tampered, key_dir / "signing.pub") is False


def test_commit_ref_resolved_and_consistent(tmp_path, monkeypatch):
    manifest_file, _ = _setup(tmp_path, monkeypatch, key=False)
    repo = ["--repo-root", str(tmp_path)]
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    assert _check(manifest_file, "--with-gaps", *repo).exit_code == 0
    raw = _artifact_dict(tmp_path)
    assert raw["commit_ref"] == "a" * 40
    assert raw["gap_report"]["commit_ref"] == "a" * 40

    monkeypatch.delenv("GITHUB_SHA")
    # tmp_path is not inside a git repo, so git cannot answer either.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert _check(manifest_file, "--with-gaps", *repo).exit_code == 0
    raw = _artifact_dict(tmp_path)
    assert raw["commit_ref"] == "unresolved"
    assert raw["gap_report"]["commit_ref"] == "unresolved"

    assert _check(manifest_file, "--commit-ref", "abcdef123456").exit_code == 0
    assert _artifact_dict(tmp_path)["commit_ref"] == "abcdef123456"


def test_stamp_uses_injected_clock():
    stamped = stamp_artifact(
        _bare_artifact(), now=datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)
    )
    assert stamped.timestamp == "2030-01-02T03:04:05Z"
    assert stamped.policy_bundle_version.startswith("cli-")
    # Already-set values are kept.
    again = stamp_artifact(stamped, now=datetime(2040, 1, 1, tzinfo=UTC))
    assert again.timestamp == stamped.timestamp


def test_stamp_matches_what_push_would_add():
    stamped = json.loads(
        stamp_artifact(_bare_artifact(), now=datetime.now(UTC)).model_dump_json()
    )
    assert prepare_scan_status_artifact(stamped, commit_env={}) == stamped


def test_stamped_artifact_validates_against_live_ingest_schema(tmp_path, monkeypatch):
    if not SCHEMA.exists():
        pytest.skip("dashboard-saas schema not present")
    manifest_file, _ = _setup(tmp_path, monkeypatch, key=False)
    monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    assert _check(manifest_file, "--with-gaps").exit_code == 0
    prepared = prepare_scan_status_artifact(_artifact_dict(tmp_path), commit_env={})
    jsonschema.validate(prepared, json.loads(SCHEMA.read_text("utf-8")))


def test_signing_key_available(tmp_path, monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    assert not signing_key_available(tmp_path / "none")
    monkeypatch.setenv("SIGNING_KEY_PRIVATE", "x")
    assert signing_key_available(tmp_path / "none")
