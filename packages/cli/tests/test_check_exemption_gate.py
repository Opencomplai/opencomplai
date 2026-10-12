"""`check --require-exemption-record`: opt-in gate on the Art. 6(3) record."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_cli.main import app
from opencomplai_core.acceptance import (
    ART_6_3_EXEMPTION,
    build_record,
    public_key_pem_from_private,
    record_path,
    sign_record,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import CheckerSessionRef, SystemManifest
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
PURPOSE = "Summarises internal documents"  # trips no risk rule
DEROGATION = "provider_art_6_4_registration"
CONTROL = "EU_AIA_ART6_3_EXEMPTION_RECORD"
FLAG = "--require-exemption-record"


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    """Fresh HOME with no signing key, so nothing outside the repo is read."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "SIGNING_KEY_PRIVATE",
        "OPENCOMPLAI_TRUSTED_KEY_IDS",
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        monkeypatch.delenv(var, raising=False)
    fresh = tmp_path / "home"
    fresh.mkdir()
    monkeypatch.setenv("HOME", str(fresh))
    monkeypatch.setenv("USERPROFILE", str(fresh))
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", fresh / "missing")
    monkeypatch.setattr(main, "_CONFIG_FILE", fresh / "missing" / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", fresh / "missing" / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", fresh / "missing" / "signing.pub")
    return fresh


def _manifest(
    tmp_path: Path,
    grounds: tuple[str, ...] = ("hr3_art_6_3",),
    obligations: tuple[str, ...] = (DEROGATION,),
) -> SystemManifest:
    manifest = SystemManifest(
        system_id="exempt-sys",
        intended_purpose=PURPOSE,
        operator_role="provider",
        checker_session=CheckerSessionRef(
            checker_version="checker-test",
            session_id="s",
            completed_at="2026-01-01T00:00:00Z",
            obligation_ids=list(obligations),
            derogation_grounds=list(grounds),
        ),
    )
    (tmp_path / "system-manifest.json").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    return manifest


def _commit_record(tmp_path: Path, manifest: SystemManifest) -> None:
    generate_keypair(tmp_path / "keys")
    key = tmp_path / "keys" / "signing.key"
    record = sign_record(
        build_record(
            record_type=ART_6_3_EXEMPTION,
            system_id=manifest.system_id,
            manifest_fingerprint=fingerprint_manifest(manifest),
            accepted_by="dpo@example.test",
            statement="Grounds reviewed.",
            accepted_at="2026-10-07T10:00:00Z",
            public_key_pem=public_key_pem_from_private(key.read_bytes()),
            grounds=manifest.checker_session.derogation_grounds,
        ),
        key,
    )
    path = record_path(tmp_path.resolve(), manifest.system_id, ART_6_3_EXEMPTION)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")


def _check(*args: str):
    return runner.invoke(app, ["check", "-m", "system-manifest.json", *args])


def _artifact(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "compliance-artifact.json").read_text("utf-8"))


def test_flag_fails_check_without_record(tmp_path: Path, home: Path) -> None:
    _manifest(tmp_path)
    result = _check(FLAG)
    assert result.exit_code == 1, result.output
    artifact = _artifact(tmp_path)
    assert artifact["failed_controls"] == [CONTROL]
    assert artifact["result"] == "control_fail"


def test_flag_fails_check_with_stale_record(tmp_path: Path, home: Path) -> None:
    _commit_record(tmp_path, _manifest(tmp_path, grounds=("hr3_art_6_3",)))
    assert _check(FLAG).exit_code == 0
    _manifest(tmp_path, grounds=("hr3_art_6_3", "hr6_accessory"))  # answer changed
    result = _check(FLAG)
    assert result.exit_code == 1, result.output
    assert _artifact(tmp_path)["failed_controls"] == [CONTROL]


def test_flag_passes_with_valid_record(tmp_path: Path, home: Path) -> None:
    _commit_record(tmp_path, _manifest(tmp_path))
    result = _check(FLAG)
    assert result.exit_code == 0, result.output
    assert _artifact(tmp_path)["failed_controls"] == []


def test_without_flag_exit_is_unchanged(tmp_path: Path, home: Path) -> None:
    _manifest(tmp_path)
    result = _check()
    assert result.exit_code == 0, result.output
    assert _artifact(tmp_path)["failed_controls"] == []
    # Stale record without the flag: still unchanged.
    _commit_record(tmp_path, _manifest(tmp_path))
    _manifest(tmp_path, grounds=("hr4_narrow_task",))
    assert _check().exit_code == 0


def test_non_derogating_system_untouched(tmp_path: Path, home: Path) -> None:
    _manifest(tmp_path, grounds=(), obligations=("provider_high_risk",))
    result = _check(FLAG)
    assert result.exit_code == 0, result.output
    assert _artifact(tmp_path)["failed_controls"] == []
