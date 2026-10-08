"""`opencomplai accept`: signed, committable acceptance records (SU-110a)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_cli.main import app
from opencomplai_core.acceptance import (
    CLASSIFICATION_ACCEPTANCE,
    TRAP_APPROVAL,
    evaluate_record,
    record_path,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import CheckerSessionRef, SystemManifest
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
HIGH_RISK = "managing the operation of critical road traffic infrastructure"


@pytest.fixture
def env(tmp_path: Path, monkeypatch) -> Path:
    """Isolated cwd/home; no signing key anywhere. Returns the manifest path."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "SIGNING_KEY_PRIVATE",
        "OPENCOMPLAI_TRUSTED_KEY_IDS",
        "OPENCOMPLAI_API_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")
    return _manifest(tmp_path)


def _manifest(
    tmp_path: Path, purpose: str = HIGH_RISK, verdict: str | None = None
) -> Path:
    session = (
        CheckerSessionRef(
            checker_version="checker-test",
            session_id="s",
            completed_at="2026-01-01T00:00:00Z",
            verdict=verdict,
        )
        if verdict
        else None
    )
    path = tmp_path / "system-manifest.json"
    path.write_text(
        SystemManifest(
            system_id="acc-sys", intended_purpose=purpose, checker_session=session
        ).model_dump_json(),
        encoding="utf-8",
    )
    return path


def _key(tmp_path: Path) -> Path:
    generate_keypair(tmp_path / "keys")
    return tmp_path / "keys" / "signing.key"


def _accept(*extra: str):
    return runner.invoke(
        app,
        [
            "accept",
            "--accepted-by",
            "dpo@example.test",
            "--statement",
            "Reviewed.",
            *extra,
        ],
    )


def _status(tmp_path: Path, manifest_path: Path, record_type=CLASSIFICATION_ACCEPTANCE):
    manifest = SystemManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    path = record_path(tmp_path.resolve(), manifest.system_id, record_type)
    return manifest, path, evaluate_record(path, manifest, record_type)


def test_accept_writes_signed_record_bound_to_fingerprint(
    tmp_path: Path, env: Path
) -> None:
    key = _key(tmp_path)
    result = _accept("--key", str(key), "-o", "json")
    assert result.exit_code == 0, result.output
    manifest, path, status = _status(tmp_path, env)
    assert status.state == "valid"
    assert status.record["manifest_fingerprint"] == fingerprint_manifest(manifest)
    assert status.record["accepted_by"] == "dpo@example.test"
    assert status.record["accepted_at"].endswith("Z")
    out = json.loads(result.stdout)
    assert out["record_type"] == CLASSIFICATION_ACCEPTANCE
    assert out["key_id"] == status.record["key_id"]
    assert Path(out["path"]) == path
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert "\r" not in text
    assert "PRIVATE" not in text


def test_accept_human_output_says_to_commit(tmp_path: Path, env: Path) -> None:
    result = _accept("--key", str(_key(tmp_path)))
    assert result.exit_code == 0, result.output
    assert "Commit" in result.stdout
    assert ".classification_acceptance.json" in result.stdout


def test_accept_without_key_exits_2_and_writes_nothing(
    tmp_path: Path, env: Path
) -> None:
    result = _accept()
    assert result.exit_code == 2, result.output
    assert "SIGNING_KEY_PRIVATE" in result.stderr
    assert not (tmp_path / ".opencomplai").exists()


def test_accept_with_env_key_and_no_key_file(
    tmp_path: Path, env: Path, monkeypatch
) -> None:
    key = _key(tmp_path)
    monkeypatch.setenv(
        "SIGNING_KEY_PRIVATE", base64.b64encode(key.read_bytes()).decode()
    )
    key.unlink()
    result = _accept()
    assert result.exit_code == 0, result.output
    assert _status(tmp_path, env)[2].state == "valid"


def test_accept_requires_statement_and_accepted_by(tmp_path: Path, env: Path) -> None:
    key = str(_key(tmp_path))
    assert (
        runner.invoke(app, ["accept", "--statement", "s", "--key", key]).exit_code == 2
    )
    assert (
        runner.invoke(app, ["accept", "--accepted-by", "a", "--key", key]).exit_code
        == 2
    )
    blank = runner.invoke(
        app, ["accept", "--accepted-by", "a", "--statement", "  ", "--key", key]
    )
    assert blank.exit_code == 2
    assert not (tmp_path / ".opencomplai").exists()


def test_accept_missing_manifest_exits_2(tmp_path: Path, env: Path) -> None:
    result = _accept("-m", str(tmp_path / "nope.json"), "--key", str(_key(tmp_path)))
    assert result.exit_code == 2, result.output


@pytest.mark.parametrize(
    ("purpose", "verdict"),
    [
        ("social scoring of citizens by public authority", None),
        ("Summarises internal documents", "prohibited_practice"),
    ],
)
def test_accept_refuses_prohibited_practice(
    tmp_path: Path, env: Path, purpose: str, verdict: str | None
) -> None:
    manifest = _manifest(tmp_path, purpose, verdict)
    result = _accept("-m", str(manifest), "--key", str(_key(tmp_path)))
    assert result.exit_code == 2, result.output
    assert "Art. 5" in result.stderr
    assert not (tmp_path / ".opencomplai").exists()


def test_accept_trap_approval_writes_record(tmp_path: Path, env: Path) -> None:
    key = str(_key(tmp_path))
    missing = _accept("--trap-approval", "--key", key)
    assert missing.exit_code == 2, missing.output
    assert not (tmp_path / ".opencomplai").exists()
    stray = _accept("--change-context", "model_retrain", "--key", key)
    assert stray.exit_code == 2, stray.output

    ok = _accept("--trap-approval", "--change-context", "model_retrain", "--key", key)
    assert ok.exit_code == 0, ok.output
    _, path, status = _status(tmp_path, env, TRAP_APPROVAL)
    assert path.name.endswith(".trap_approval.json")
    assert status.state == "valid"
    assert status.record["change_context"] == "model_retrain"
    assert _status(tmp_path, env)[2].state == "absent"


def test_accept_overwrites_same_type_record(tmp_path: Path, env: Path) -> None:
    key = str(_key(tmp_path))
    assert _accept("--key", key).exit_code == 0
    second = runner.invoke(
        app,
        [
            "accept",
            "--accepted-by",
            "cto@example.test",
            "--statement",
            "Again.",
            "--key",
            key,
        ],
    )
    assert second.exit_code == 0, second.output
    _, path, status = _status(tmp_path, env)
    assert status.record["accepted_by"] == "cto@example.test"
    assert len(list(path.parent.glob("*.json"))) == 1
