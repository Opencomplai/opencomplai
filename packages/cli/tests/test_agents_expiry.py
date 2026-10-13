"""`agents check` lists expired mandates; the exit status is unchanged."""

from __future__ import annotations

import json
import socket
from datetime import date
from pathlib import Path

import opencomplai_cli.commands.agents as agents_module
import opencomplai_cli.main as main_module
import pytest
from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures" / "agents"
MANIFEST = FIXTURES / "sample-manifest.json"
SCAN = str(FIXTURES / "sample-scan-report.json")
_TODAY = date(2026, 10, 11)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)

    def boom(*_a, **_k):
        raise AssertionError("agents commands must stay offline")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(main_module, "_vault_request", boom)
    monkeypatch.setattr(agents_module, "_today", lambda: _TODAY)


def _run(*args: str):
    return runner.invoke(app, ["agents", *args])


def _manifest(tmp_path: Path, expires_at: str | None) -> str:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mandate = m["agent_inventory"]["agents"][0]["mandate"]
    if expires_at is not None:
        mandate["expires_at"] = expires_at
    path = tmp_path / f"m-{expires_at}.json"
    path.write_text(json.dumps(m), encoding="utf-8")
    return str(path)


def test_check_lists_expired_mandate_with_injected_today(tmp_path):
    path = _manifest(tmp_path, "2026-10-10")
    human = _run("check", "-m", path)
    assert human.exit_code == 0, human.output
    lines = human.output.splitlines()
    want = (
        "[declared] expired_mandate: agent 'orchestrator' mandate expired "
        "(expires_at 2026-10-10)"
    )
    assert want in lines
    assert lines.index(want) < next(
        i for i, ln in enumerate(lines) if ln.startswith("0 finding(s)")
    )
    data = json.loads(_run("check", "-m", path, "-o", "json").output)
    assert data["expired_mandates"] == [
        {"id": "orchestrator", "expires_at": "2026-10-10"}
    ]
    assert data["findings"] == []
    assert data["exit_code"] == 0


def test_expired_mandate_does_not_change_exit_code(tmp_path):
    expired = _manifest(tmp_path, "2026-10-10")
    plain = _manifest(tmp_path, None)
    assert _run("check", "-m", plain).exit_code == 0
    assert _run("check", "-m", expired).exit_code == 0
    with_scan = _run("check", "-m", expired, "--scan-report", SCAN)
    assert with_scan.exit_code == 1
    assert "expired_mandate" in with_scan.output
    assert _run("check", "-m", plain, "--scan-report", SCAN).exit_code == 1
    assert "2 finding(s)" not in with_scan.output  # expiry lines are not counted


def test_expiry_day_itself_is_not_expired(tmp_path):
    path = _manifest(tmp_path, "2026-10-11")
    assert "expired_mandate" not in _run("check", "-m", path).output
    assert (
        json.loads(_run("check", "-m", path, "-o", "json").output)["expired_mandates"]
        == []
    )


def test_no_expiry_is_never_listed(tmp_path):
    path = _manifest(tmp_path, None)
    assert "expired_mandate" not in _run("check", "-m", path).output


def test_expired_mandates_key_present_and_empty_when_none(tmp_path):
    data = json.loads(
        _run("check", "-m", _manifest(tmp_path, None), "-o", "json").output
    )
    assert data["expired_mandates"] == []
    assert set(data) == {
        "system_id",
        "notice",
        "findings",
        "expired_mandates",
        "exit_code",
    }
