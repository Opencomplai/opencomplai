"""
Signed, hash-chained oversight log for `approve` and `resume` (SU-20b1).

Every test isolates the state dir (and the default signing key paths) to
tmp_path, and patches `oversight_log._now` so log bytes are reproducible.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest
from opencomplai_cli import main as cli_main
from opencomplai_cli.commands import halt, oversight_log
from opencomplai_cli.main import app
from opencomplai_core.models import (
    HumanOversight,
    OversightRole,
    SystemManifest,
    SystemState,
)
from opencomplai_core.signing import generate_keypair
from opencomplai_core.system_state_store import load_state, save_state, state_record
from typer.testing import CliRunner

runner = CliRunner()
SYS = "ov-sys"


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    # No default key anywhere unless a test passes one.
    monkeypatch.setattr(cli_main, "_SIGNING_KEY", tmp_path / "none" / "signing.key")
    monkeypatch.setattr(cli_main, "_SIGNING_PUB", tmp_path / "none" / "signing.pub")
    stamps = (f"2026-01-01T00:00:{n:02d}+00:00" for n in itertools.count())
    monkeypatch.setattr(oversight_log, "_now", lambda: next(stamps))


@pytest.fixture
def keys(tmp_path):
    generate_keypair(tmp_path / "keys")
    return tmp_path / "keys" / "signing.key", tmp_path / "keys" / "signing.pub"


def _log(tmp_path: Path) -> Path:
    return tmp_path / "state" / "oversight-log.json"


def _lines(tmp_path: Path) -> list[str]:
    return _log(tmp_path).read_text(encoding="utf-8").splitlines()


def _entries(tmp_path: Path) -> list[dict]:
    return [json.loads(line) for line in _lines(tmp_path)]


def _halt(tmp_path: Path) -> None:
    save_state(
        tmp_path / "state",
        SYS,
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="abc123",
    )


def _manifest(tmp_path: Path, *roles: str) -> Path:
    oversight = (
        HumanOversight(roles=[OversightRole(role=r) for r in roles]) if roles else None
    )
    manifest = SystemManifest(
        system_id=SYS, intended_purpose="test", human_oversight=oversight
    )
    path = tmp_path / "system-manifest.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    return path


def _approve(priv: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "approve",
            "--system-id",
            SYS,
            "--approver",
            "qa@example.com",
            "--key",
            str(priv),
            "--output",
            "json",
            *extra,
        ],
    )


def _resume(token: str, pub: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "resume",
            "--system-id",
            SYS,
            "--approval-token",
            token,
            "--pub-key",
            str(pub),
            *extra,
        ],
    )


def _approve_and_resume(tmp_path, keys, *role_args: str) -> str:
    priv, pub = keys
    _halt(tmp_path)
    res = _approve(priv, *role_args)
    assert res.exit_code == 0, res.output
    token = json.loads(res.stdout)["token"]
    res = _resume(token, pub, "--key", str(priv))
    assert res.exit_code == 0, res.output
    return token


def _verify(log: Path, *extra: str):
    return runner.invoke(
        app, ["verify", str(log), "--kind", "oversight-log", "--output", "json", *extra]
    )


def _three_entries(tmp_path, keys) -> Path:
    """approve, resume, then a second halt and approve: three signed entries."""
    priv, _ = keys
    _approve_and_resume(tmp_path, keys)
    _halt(tmp_path)
    assert _approve(priv).exit_code == 0
    assert len(_lines(tmp_path)) == 3
    return _log(tmp_path)


def test_approve_entry_names_role(tmp_path, keys):
    _manifest(tmp_path, "Compliance Officer", "Operator")
    _halt(tmp_path)
    res = _approve(keys[0], "--role", "Operator")
    assert res.exit_code == 0, res.output
    assert json.loads(res.stdout)["role"] == "Operator"
    (entry,) = _entries(tmp_path)
    p = entry["payload"]
    assert p["event"] == "approval_minted"
    assert (p["role"], p["role_declared"], p["approver"]) == (
        "Operator",
        True,
        "qa@example.com",
    )


def test_resume_entry_names_role_from_token(tmp_path, keys):
    _manifest(tmp_path, "Operator")
    _approve_and_resume(tmp_path, keys, "--role", "Operator")
    _, resume = (e["payload"] for e in _entries(tmp_path))
    assert resume["event"] == "resume_granted"
    assert (resume["role"], resume["role_declared"]) == ("Operator", True)
    assert resume["system_id"] == SYS
    assert load_state(tmp_path / "state", SYS) == SystemState.RUNNING


def test_role_not_declared_in_manifest_exits_2(tmp_path, keys):
    _manifest(tmp_path, "Operator")
    _halt(tmp_path)
    res = _approve(keys[0], "--role", "Janitor")
    assert res.exit_code == 2
    assert "token" not in res.output
    assert not _log(tmp_path).exists()


def test_role_required_when_manifest_declares_roles(tmp_path, keys):
    _manifest(tmp_path, "Operator")
    _halt(tmp_path)
    res = _approve(keys[0])
    assert res.exit_code == 2
    assert not _log(tmp_path).exists()


def test_legacy_manifest_without_oversight_block_behaves_as_before(tmp_path, keys):
    _manifest(tmp_path)  # no human_oversight block
    _approve_and_resume(tmp_path, keys)
    for entry in _entries(tmp_path):
        assert entry["payload"]["role"] is None
        assert entry["payload"]["role_declared"] is False


def test_token_without_role_still_resumes(tmp_path, keys):
    priv, pub = keys
    _halt(tmp_path)
    record = state_record(tmp_path / "state", SYS)
    token, payload = halt._mint_token(
        system_id=SYS,
        commit_ref="abc123",
        halted_at=record["changed_at"],
        approver="old@example.com",
        key_path=priv,
        role=None,
    )
    assert "role" not in payload
    res = _resume(token, pub, "--key", str(priv))
    assert res.exit_code == 0, res.output
    assert _entries(tmp_path)[0]["payload"]["role"] is None


def test_log_is_signed_and_verifies_with_pub_key(tmp_path, keys):
    _approve_and_resume(tmp_path, keys)
    res = _verify(_log(tmp_path), "--pub-key", str(keys[1]))
    assert res.exit_code == 0, res.output
    out = json.loads(res.stdout)
    assert out["status"] == "verified"
    assert "count=2" in out["detail"]


def test_unsigned_entries_reported_unsigned(tmp_path, keys):
    priv, pub = keys
    _halt(tmp_path)
    token = json.loads(_approve(priv).stdout)["token"]
    # Drop the signed approval line so the log is only the unsigned resume.
    _log(tmp_path).unlink()
    res = _resume(token, pub)  # no --key, no default key, no env key
    assert res.exit_code == 0, res.output
    assert "written unsigned" in res.output
    res = _verify(_log(tmp_path), "--pub-key", str(pub))
    assert res.exit_code == 1
    assert json.loads(res.stdout)["status"] == "unsigned"


def test_edit_entry_fails_verify(tmp_path, keys):
    log = _three_entries(tmp_path, keys)
    lines = _lines(tmp_path)
    entry = json.loads(lines[0])
    entry["payload"]["approver"] = "mallory@example.com"
    lines[0] = json.dumps(entry, sort_keys=True)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = _verify(log, "--pub-key", str(keys[1]))
    assert res.exit_code == 1
    assert json.loads(res.stdout)["status"] == "invalid"


def test_delete_entry_fails_verify(tmp_path, keys):
    log = _three_entries(tmp_path, keys)
    log.write_text("\n".join(_lines(tmp_path)[1:]) + "\n", encoding="utf-8")
    res = _verify(log, "--pub-key", str(keys[1]))
    assert res.exit_code == 1
    assert json.loads(res.stdout)["status"] == "invalid"


def test_reorder_entries_fails_verify(tmp_path, keys):
    log = _three_entries(tmp_path, keys)
    a, b, c = _lines(tmp_path)
    log.write_text("\n".join([a, c, b]) + "\n", encoding="utf-8")
    res = _verify(log, "--pub-key", str(keys[1]))
    assert res.exit_code == 1
    assert json.loads(res.stdout)["status"] == "invalid"


def test_append_failure_blocks_resume_and_keeps_halt(tmp_path, keys):
    priv, pub = keys
    _halt(tmp_path)
    token = json.loads(_approve(priv).stdout)["token"]
    _log(tmp_path).unlink()
    _log(tmp_path).mkdir()  # the log path is now a directory: append fails
    res = _resume(token, pub, "--key", str(priv))
    assert res.exit_code == 2
    assert load_state(tmp_path / "state", SYS) == SystemState.HALTED_PENDING_REVIEW


def test_log_never_contains_key_material_or_token(tmp_path, keys):
    token = _approve_and_resume(tmp_path, keys)
    text = _log(tmp_path).read_text(encoding="utf-8")
    assert "PRIVATE KEY" not in text
    assert "BEGIN" not in text
    assert token not in text
    assert token.split(".")[1] not in text
    assert "token_sha256" in text


def test_verify_unknown_kind_still_lists_oversight_log(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}", encoding="utf-8")
    res = runner.invoke(app, ["verify", str(f), "--kind", "nope"])
    assert res.exit_code == 2
    assert "oversight-log" in res.output
