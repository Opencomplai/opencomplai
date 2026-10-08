"""
HALT-WIRE: wiring the halt/resume gate to the CLI.

`check` persists HALTED_PENDING_REVIEW on a trap or an unresolved HIGH-risk
corroboration gap; `docs generate` refuses while halted; `approve`/`resume`
mint and verify a signed HITL approval token to bring the system back to
RUNNING. Every test isolates the state file to tmp_path via
OPENCOMPLAI_STATE_DIR so this suite never touches the real ~/.opencomplai,
and forces the local-fallback path (no OPENCOMPLAI_API_URL) the same way
test_docs_generate_wiring.py does.
"""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from opencomplai_core.models import SystemState
from opencomplai_core.signing import generate_keypair
from opencomplai_core.system_state_store import load_state, save_state, state_record
from typer.testing import CliRunner

runner = CliRunner()


def _isolate(tmp_path: Path, monkeypatch) -> Path:
    """Chdir to tmp_path, force the local-fallback path, and point the
    HALT-WIRE state store at an isolated directory."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(state_dir))
    return state_dir


def _write_manifest(tmp_path: Path, system_id: str, intended_purpose: str) -> Path:
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


# ---------------------------------------------------------------------------
# (1) check trap -> persisted halt
# ---------------------------------------------------------------------------


def test_check_local_trap_persists_halted_state(tmp_path, monkeypatch):
    """FINDING 48.2: a real manifest + `--change-context model_retrain` trips
    EU_AIA_ART25_MODIFICATION_TRAP through the actual local engine (no
    mocking of the result mapping) and exits 4."""
    state_dir = _isolate(tmp_path, monkeypatch)
    manifest_file = _write_manifest(tmp_path, "halt-sys-1", "customer support chatbot")

    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--change-context",
            "model_retrain",
        ],
    )
    assert result.exit_code == 4, result.output

    assert load_state(state_dir, "halt-sys-1") == SystemState.HALTED_PENDING_REVIEW
    record = state_record(state_dir, "halt-sys-1")
    assert record is not None
    assert record["reason"] == "trap_detected"


def test_check_local_unrecognized_change_context_does_not_trip_trap(
    tmp_path, monkeypatch
):
    """A --change-context value outside the risk-engine's recognized set
    (model_retrain | purpose_change | capability_extension) must not trip
    the trap -- confirms the CLI mirrors the risk-engine's exact keyword set
    rather than trapping on any non-empty value."""
    state_dir = _isolate(tmp_path, monkeypatch)
    manifest_file = _write_manifest(tmp_path, "halt-sys-1b", "customer support chatbot")

    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--change-context",
            "refactor",
        ],
    )
    assert result.exit_code == 0, result.output
    assert load_state(state_dir, "halt-sys-1b") == SystemState.RUNNING


# ---------------------------------------------------------------------------
# (2) docs generate refuses while halted
# ---------------------------------------------------------------------------


def test_docs_generate_refuses_while_halted(tmp_path, monkeypatch):
    state_dir = _isolate(tmp_path, monkeypatch)
    save_state(
        state_dir,
        "halt-sys-2",
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="HEAD",
    )

    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "docs",
            "generate",
            "--system-id",
            "halt-sys-2",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 4, result.output
    assert "HALTED_PENDING_REVIEW" in result.output
    assert "halt-sys-2" in result.output
    assert not list(output_dir.glob("dossier_*.json"))
    assert load_state(state_dir, "halt-sys-2") == SystemState.HALTED_PENDING_REVIEW


# ---------------------------------------------------------------------------
# (3) approve + resume flow: docs generate works again afterwards
# ---------------------------------------------------------------------------


def test_approve_then_resume_unblocks_docs_generate(tmp_path, monkeypatch):
    state_dir = _isolate(tmp_path, monkeypatch)
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    priv_key, pub_key = key_dir / "signing.key", key_dir / "signing.pub"

    save_state(
        state_dir,
        "halt-sys-3",
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="HEAD",
    )

    approve_result = runner.invoke(
        app,
        [
            "approve",
            "--system-id",
            "halt-sys-3",
            "--approver",
            "qa@example.com",
            "--key",
            str(priv_key),
            "--output",
            "json",
        ],
    )
    assert approve_result.exit_code == 0, approve_result.output
    token = json.loads(approve_result.stdout)["token"]
    assert token.count(".") == 1

    resume_result = runner.invoke(
        app,
        [
            "resume",
            "--system-id",
            "halt-sys-3",
            "--approval-token",
            token,
            "--pub-key",
            str(pub_key),
        ],
    )
    assert resume_result.exit_code == 0, resume_result.output
    assert load_state(state_dir, "halt-sys-3") == SystemState.RUNNING

    output_dir = tmp_path / "out"
    docs_result = runner.invoke(
        app,
        [
            "docs",
            "generate",
            "--system-id",
            "halt-sys-3",
            "--output-dir",
            str(output_dir),
        ],
    )
    assert docs_result.exit_code == 0, docs_result.output
    assert list(output_dir.glob("dossier_*.json"))


def test_resume_accepts_token_from_file(tmp_path, monkeypatch):
    """`--approval-token @path` reads the token from a file (documented in
    the command help as an alternative to pasting the raw token)."""
    state_dir = _isolate(tmp_path, monkeypatch)
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    priv_key, pub_key = key_dir / "signing.key", key_dir / "signing.pub"

    save_state(
        state_dir,
        "halt-sys-3b",
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="HEAD",
    )
    approve_result = runner.invoke(
        app,
        [
            "approve",
            "--system-id",
            "halt-sys-3b",
            "--approver",
            "qa@example.com",
            "--key",
            str(priv_key),
            "--output",
            "json",
        ],
    )
    assert approve_result.exit_code == 0, approve_result.output
    token = json.loads(approve_result.stdout)["token"]

    token_file = tmp_path / "token.txt"
    token_file.write_text(token)

    resume_result = runner.invoke(
        app,
        [
            "resume",
            "--system-id",
            "halt-sys-3b",
            "--approval-token",
            f"@{token_file}",
            "--pub-key",
            str(pub_key),
        ],
    )
    assert resume_result.exit_code == 0, resume_result.output
    assert load_state(state_dir, "halt-sys-3b") == SystemState.RUNNING


# ---------------------------------------------------------------------------
# (4) resume rejects invalid tokens and leaves state halted
# ---------------------------------------------------------------------------


def test_resume_rejects_tampered_token(tmp_path, monkeypatch):
    state_dir = _isolate(tmp_path, monkeypatch)
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    priv_key, pub_key = key_dir / "signing.key", key_dir / "signing.pub"

    save_state(
        state_dir,
        "halt-sys-4",
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="HEAD",
    )
    approve_result = runner.invoke(
        app,
        [
            "approve",
            "--system-id",
            "halt-sys-4",
            "--approver",
            "qa@example.com",
            "--key",
            str(priv_key),
            "--output",
            "json",
        ],
    )
    assert approve_result.exit_code == 0, approve_result.output
    token = json.loads(approve_result.stdout)["token"]

    payload_b64, _, sig_b64 = token.partition(".")
    tampered_token = f"{payload_b64}x.{sig_b64}"

    resume_result = runner.invoke(
        app,
        [
            "resume",
            "--system-id",
            "halt-sys-4",
            "--approval-token",
            tampered_token,
            "--pub-key",
            str(pub_key),
        ],
    )
    assert resume_result.exit_code == 2, resume_result.output
    assert load_state(state_dir, "halt-sys-4") == SystemState.HALTED_PENDING_REVIEW


def test_resume_rejects_wrong_pub_key(tmp_path, monkeypatch):
    state_dir = _isolate(tmp_path, monkeypatch)
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    priv_key = key_dir / "signing.key"

    other_key_dir = tmp_path / "other-keys"
    generate_keypair(other_key_dir)
    wrong_pub_key = other_key_dir / "signing.pub"

    save_state(
        state_dir,
        "halt-sys-5",
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="HEAD",
    )
    approve_result = runner.invoke(
        app,
        [
            "approve",
            "--system-id",
            "halt-sys-5",
            "--approver",
            "qa@example.com",
            "--key",
            str(priv_key),
            "--output",
            "json",
        ],
    )
    assert approve_result.exit_code == 0, approve_result.output
    token = json.loads(approve_result.stdout)["token"]

    resume_result = runner.invoke(
        app,
        [
            "resume",
            "--system-id",
            "halt-sys-5",
            "--approval-token",
            token,
            "--pub-key",
            str(wrong_pub_key),
        ],
    )
    assert resume_result.exit_code == 2, resume_result.output
    assert load_state(state_dir, "halt-sys-5") == SystemState.HALTED_PENDING_REVIEW


def test_resume_rejects_token_for_different_system(tmp_path, monkeypatch):
    state_dir = _isolate(tmp_path, monkeypatch)
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    priv_key, pub_key = key_dir / "signing.key", key_dir / "signing.pub"

    save_state(
        state_dir,
        "halt-sys-6a",
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="HEAD",
    )
    save_state(
        state_dir,
        "halt-sys-6b",
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="HEAD",
    )
    approve_result = runner.invoke(
        app,
        [
            "approve",
            "--system-id",
            "halt-sys-6a",
            "--approver",
            "qa@example.com",
            "--key",
            str(priv_key),
            "--output",
            "json",
        ],
    )
    assert approve_result.exit_code == 0, approve_result.output
    token_for_a = json.loads(approve_result.stdout)["token"]

    # Token was minted for halt-sys-6a; using it to resume halt-sys-6b must
    # fail even though both are HALTED_PENDING_REVIEW and share a keypair.
    resume_result = runner.invoke(
        app,
        [
            "resume",
            "--system-id",
            "halt-sys-6b",
            "--approval-token",
            token_for_a,
            "--pub-key",
            str(pub_key),
        ],
    )
    assert resume_result.exit_code == 2, resume_result.output
    assert load_state(state_dir, "halt-sys-6b") == SystemState.HALTED_PENDING_REVIEW
    assert load_state(state_dir, "halt-sys-6a") == SystemState.HALTED_PENDING_REVIEW


def test_resume_when_not_halted_is_a_noop_exit_0(tmp_path, monkeypatch):
    state_dir = _isolate(tmp_path, monkeypatch)
    result = runner.invoke(
        app,
        [
            "resume",
            "--system-id",
            "never-halted-sys",
            "--approval-token",
            "not-a-real-token",
        ],
    )
    assert result.exit_code == 0, result.output
    assert load_state(state_dir, "never-halted-sys") == SystemState.RUNNING


# ---------------------------------------------------------------------------
# (5) approve refuses on a non-halted system
# ---------------------------------------------------------------------------


def test_approve_refuses_when_not_halted(tmp_path, monkeypatch):
    state_dir = _isolate(tmp_path, monkeypatch)
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    priv_key = key_dir / "signing.key"

    result = runner.invoke(
        app,
        [
            "approve",
            "--system-id",
            "running-sys",
            "--approver",
            "qa@example.com",
            "--key",
            str(priv_key),
        ],
    )
    assert result.exit_code == 2, result.output
    assert state_record(state_dir, "running-sys") is None


# ---------------------------------------------------------------------------
# (6) approve honours SIGNING_KEY_PRIVATE (SU-3a)
# ---------------------------------------------------------------------------


def _halt(state_dir: Path, system_id: str) -> None:
    save_state(
        state_dir,
        system_id,
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="HEAD",
    )


def test_approve_with_env_key_and_no_key_file(tmp_path, monkeypatch):
    import base64

    from opencomplai_cli import main

    state_dir = _isolate(tmp_path, monkeypatch)
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    env_key = base64.b64encode((key_dir / "signing.key").read_bytes()).decode()
    monkeypatch.setenv("SIGNING_KEY_PRIVATE", env_key)
    monkeypatch.setattr(main, "_SIGNING_KEY", tmp_path / "missing" / "signing.key")
    _halt(state_dir, "halt-env")

    approved = runner.invoke(
        app,
        [
            *["approve", "--system-id", "halt-env", "--approver", "qa@example.com"],
            *["--output", "json"],
        ],
    )
    assert approved.exit_code == 0, approved.output
    token = json.loads(approved.stdout)["token"]

    resumed = runner.invoke(
        app,
        [
            *["resume", "--system-id", "halt-env", "--approval-token", token],
            *["--pub-key", str(key_dir / "signing.pub")],
        ],
    )
    assert resumed.exit_code == 0, resumed.output
    assert load_state(state_dir, "halt-env") == SystemState.RUNNING


def test_approve_without_any_key_exits_2(tmp_path, monkeypatch):
    from opencomplai_cli import main

    state_dir = _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setattr(main, "_SIGNING_KEY", tmp_path / "missing" / "signing.key")
    _halt(state_dir, "halt-nokey")

    result = runner.invoke(
        app, ["approve", "--system-id", "halt-nokey", "--approver", "qa@example.com"]
    )
    assert result.exit_code == 2, result.output
    assert load_state(state_dir, "halt-nokey") == SystemState.HALTED_PENDING_REVIEW


def test_approve_explicit_missing_key_beats_env(tmp_path, monkeypatch):
    import base64

    state_dir = _isolate(tmp_path, monkeypatch)
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setenv(
        "SIGNING_KEY_PRIVATE",
        base64.b64encode((key_dir / "signing.key").read_bytes()).decode(),
    )
    _halt(state_dir, "halt-explicit")

    result = runner.invoke(
        app,
        [
            *["approve", "--system-id", "halt-explicit", "--approver"],
            *["qa@example.com", "--key", str(tmp_path / "nope.key")],
        ],
    )
    assert result.exit_code == 2, result.output
