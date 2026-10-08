"""`opencomplai incident` signed log, state wiring, templates and `verify --kind incident-log`."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

import pytest
from opencomplai_cli.main import app
from opencomplai_core import gap_probes
from opencomplai_core.models import SystemState
from opencomplai_core.signing import generate_keypair
from opencomplai_core.system_state_store import load_state, save_state
from typer.testing import CliRunner

runner = CliRunner()
SYS = "sys-1"
SECRET = "PRIVATE-NARRATIVE-DO-NOT-LOG"


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setattr("opencomplai_cli.main._SIGNING_KEY", tmp_path / "none.key")
    monkeypatch.setattr("opencomplai_cli.main._SIGNING_PUB", tmp_path / "none.pub")


def _inc(monkeypatch, now: str, *args: str):
    monkeypatch.setenv("OPENCOMPLAI_NOW", now)
    return runner.invoke(app, ["incident", *args])


def _declare(monkeypatch, *extra: str, now: str = "2026-03-01T10:00:00Z"):
    return _inc(
        monkeypatch,
        now,
        "declare",
        "--system-id",
        SYS,
        "--description",
        SECRET,
        *extra,
    )


def _keys(tmp_path: Path) -> tuple[Path, Path]:
    generate_keypair(tmp_path / "keys")
    return tmp_path / "keys" / "signing.key", tmp_path / "keys" / "signing.pub"


def _state(tmp_path: Path) -> SystemState:
    return load_state(tmp_path / "state", SYS)


def _log(tmp_path: Path) -> Path:
    return tmp_path / "incident-log.json"


def _signed_chain(tmp_path: Path, monkeypatch) -> Path:
    """declare, classify, close with a key: three signed entries."""
    key, _ = _keys(tmp_path)
    assert _declare(monkeypatch, "--key", str(key)).exit_code == 0
    res = _inc(
        monkeypatch,
        "2026-03-01T11:00:00Z",
        "classify",
        "--id",
        "INC-0001",
        "--class",
        "death",
        "--key",
        str(key),
    )
    assert res.exit_code == 0
    res = _inc(
        monkeypatch,
        "2026-03-01T12:00:00Z",
        "close",
        "--id",
        "INC-0001",
        "--note",
        SECRET,
        "--key",
        str(key),
    )
    assert res.exit_code == 0, res.output
    return _log(tmp_path)


def _verify(log: Path, pub: Path | None = None):
    args = ["verify", str(log), "--kind", "incident-log"]
    if pub is not None:
        args += ["--pub-key", str(pub)]
    return runner.invoke(app, args)


def test_declare_and_close_cli_drive_state(tmp_path: Path, monkeypatch):
    assert _declare(monkeypatch).exit_code == 0
    assert _state(tmp_path) == SystemState.INCIDENT_MODE
    res = _inc(
        monkeypatch, "2026-03-01T11:00:00Z", "close", "--id", "INC-0001", "--note", "x"
    )
    assert res.exit_code == 0, res.output
    assert _state(tmp_path) == SystemState.RUNNING


def test_declare_while_halted_exits_1_and_log_has_entry(tmp_path: Path, monkeypatch):
    save_state(
        tmp_path / "state",
        SYS,
        SystemState.HALTED_PENDING_REVIEW,
        reason="x",
        commit_ref="c",
    )
    res = _declare(monkeypatch)
    assert res.exit_code == 1
    assert "Invalid transition" in res.stderr
    assert _state(tmp_path) == SystemState.HALTED_PENDING_REVIEW
    events = [
        json.loads(x)["payload"]["event"]
        for x in _log(tmp_path).read_text().splitlines()
    ]
    assert events == ["incident_declared", "transition_rejected"]


def test_close_without_open_incident_state_exits_1_and_log_has_entry(
    tmp_path: Path, monkeypatch
):
    assert _declare(monkeypatch).exit_code == 0
    save_state(tmp_path / "state", SYS, SystemState.RUNNING, reason="x", commit_ref="c")
    res = _inc(
        monkeypatch, "2026-03-01T11:00:00Z", "close", "--id", "INC-0001", "--note", "x"
    )
    assert res.exit_code == 1
    events = [
        json.loads(x)["payload"]["event"]
        for x in _log(tmp_path).read_text().splitlines()
    ]
    assert events[-2:] == ["incident_closed", "transition_rejected"]


def test_log_failure_exits_2_and_state_unchanged(tmp_path: Path, monkeypatch):
    _log(tmp_path).mkdir()
    res = _declare(monkeypatch)
    assert res.exit_code == 2
    assert _state(tmp_path) == SystemState.RUNNING
    assert not (tmp_path / "incident-register.json").exists()


def test_verify_kind_incident_log_verified_with_pub_key(tmp_path: Path, monkeypatch):
    log = _signed_chain(tmp_path, monkeypatch)
    res = _verify(log, tmp_path / "keys" / "signing.pub")
    assert res.exit_code == 0, res.output
    assert "verified" in res.stdout
    assert "count=3" in res.stdout


def test_unsigned_log_reported_unsigned(tmp_path: Path, monkeypatch):
    res = _declare(monkeypatch)
    assert res.exit_code == 0
    assert "unsigned" in res.stderr
    out = _verify(_log(tmp_path))
    assert out.exit_code == 1
    assert out.stdout.startswith("unsigned")


def test_edit_entry_fails_verify(tmp_path: Path, monkeypatch):
    log = _signed_chain(tmp_path, monkeypatch)
    lines = log.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["payload"]["system_id"] = "other"
    lines[0] = json.dumps(entry, sort_keys=True)
    log.write_text("\n".join(lines) + "\n")
    res = _verify(log, tmp_path / "keys" / "signing.pub")
    assert res.exit_code == 1
    assert "INVALID" in res.stdout


def test_delete_entry_fails_verify(tmp_path: Path, monkeypatch):
    log = _signed_chain(tmp_path, monkeypatch)
    lines = log.read_text().splitlines()
    del lines[1]
    log.write_text("\n".join(lines) + "\n")
    res = _verify(log, tmp_path / "keys" / "signing.pub")
    assert res.exit_code == 1
    assert "INVALID" in res.stdout


def test_reorder_entries_fails_verify(tmp_path: Path, monkeypatch):
    log = _signed_chain(tmp_path, monkeypatch)
    lines = log.read_text().splitlines()
    lines[0], lines[1] = lines[1], lines[0]
    log.write_text("\n".join(lines) + "\n")
    res = _verify(log, tmp_path / "keys" / "signing.pub")
    assert res.exit_code == 1
    assert "INVALID" in res.stdout


def test_log_entry_has_no_free_text_fields(tmp_path: Path, monkeypatch):
    log = _signed_chain(tmp_path, monkeypatch)
    assert SECRET not in log.read_text()
    assert SECRET in (tmp_path / "incident-register.json").read_text()


def test_log_never_contains_key_material(tmp_path: Path, monkeypatch):
    log = _signed_chain(tmp_path, monkeypatch)
    key, _ = _keys(tmp_path)
    body = [x for x in key.read_text().splitlines() if x and "-----" not in x]
    text = log.read_text()
    assert "PRIVATE KEY" not in text
    for line in body:
        assert line not in text


def test_template_command_renders_authority_report(tmp_path: Path, monkeypatch):
    assert _declare(monkeypatch).exit_code == 0
    res = runner.invoke(
        app, ["incident", "template", "--kind", "authority", "--id", "INC-0001"]
    )
    assert res.exit_code == 0, res.output
    assert "DRAFT TEMPLATE: not legally reviewed" in res.stdout
    assert "INC-0001" in res.stdout
    assert SECRET in res.stdout
    out = tmp_path / "notice.md"
    res = runner.invoke(
        app,
        [
            "incident",
            "template",
            "--kind",
            "downstream",
            "--id",
            "INC-0001",
            "--party",
            "Acme",
            "--party-kind",
            "deployer",
            "--output",
            str(out),
        ],
    )
    assert res.exit_code == 0, res.output
    assert "Acme" in out.read_text()


def test_template_unknown_kind_exits_2(tmp_path: Path, monkeypatch):
    assert _declare(monkeypatch).exit_code == 0
    base = ["incident", "template", "--id"]
    assert runner.invoke(app, [*base, "INC-0001", "--kind", "nope"]).exit_code == 2
    assert runner.invoke(app, [*base, "INC-9999", "--kind", "authority"]).exit_code == 2
    assert (
        runner.invoke(app, [*base, "INC-0001", "--kind", "downstream"]).exit_code == 2
    )


def test_default_log_name_matches_incident_probe(tmp_path: Path, monkeypatch):
    assert _declare(monkeypatch).exit_code == 0
    patterns = gap_probes._PROBE_PATTERNS["serious_incident_log"]
    name = _log(tmp_path).name
    assert any(fnmatch.fnmatch(name, pat) for pat in patterns)
