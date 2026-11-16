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
    path = tmp_path / f"m-{expires_at}.json".replace(":", "_")
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
    assert data["expiring_mandates"] == []
    assert set(data) == {
        "system_id",
        "notice",
        "findings",
        "expired_mandates",
        "expiring_mandates",
        "exit_code",
    }


def _two_agents(tmp_path: Path, first: str | None, second: str | None) -> str:
    """The orchestrator and the summariser each get a mandate with the given expiry."""
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for agent, expires_at in zip(
        m["agent_inventory"]["agents"], (first, second), strict=True
    ):
        mandate = agent.setdefault("mandate", {"permitted_actions": []})
        if expires_at is not None:
            mandate["expires_at"] = expires_at
    path = tmp_path / f"m2-{first}-{second}.json".replace(":", "_")
    path.write_text(json.dumps(m), encoding="utf-8")
    return str(path)


def test_expiring_line_follows_the_expired_lines(tmp_path):
    path = _two_agents(tmp_path, "2026-11-10", "2026-10-10")
    human = _run("check", "-m", path)
    assert human.exit_code == 0, human.output
    lines = human.output.splitlines()
    expired = (
        "[declared] expired_mandate: agent 'summariser' mandate expired "
        "(expires_at 2026-10-10)"
    )
    expiring = (
        "[declared] expiring_mandate: agent 'orchestrator' mandate expires "
        "within 30 days (expires_at 2026-11-10)"
    )
    assert lines.index(expired) < lines.index(expiring)
    assert lines.index(expiring) < next(
        i for i, ln in enumerate(lines) if ln.startswith("0 finding(s)")
    )
    data = json.loads(_run("check", "-m", path, "-o", "json").output)
    assert data["expiring_mandates"] == [
        {"id": "orchestrator", "expires_at": "2026-11-10"}
    ]
    assert data["expired_mandates"] == [
        {"id": "summariser", "expires_at": "2026-10-10"}
    ]
    assert data["findings"] == []
    assert data["exit_code"] == 0


def test_expiring_lines_keep_inventory_order_and_use_the_utc_day(tmp_path):
    # The orchestrator is listed first and expires later: order is the inventory's,
    # not by date. Its expiry is the evening of 2026-11-10 in UTC, which is 2026-11-11
    # at +05:00, so only the UTC day keeps it inside the 30-day window.
    first = "2026-11-11T01:00:00+05:00"
    second = "2026-10-20"
    path = _two_agents(tmp_path, first, second)
    human = _run("check", "-m", path)
    assert human.exit_code == 0, human.output
    lines = [ln for ln in human.output.splitlines() if "expiring_mandate" in ln]
    assert lines == [
        "[declared] expiring_mandate: agent 'orchestrator' mandate expires "
        f"within 30 days (expires_at {first})",
        "[declared] expiring_mandate: agent 'summariser' mandate expires "
        f"within 30 days (expires_at {second})",
    ]
    data = json.loads(_run("check", "-m", path, "-o", "json").output)
    assert data["expiring_mandates"] == [
        {"id": "orchestrator", "expires_at": first},
        {"id": "summariser", "expires_at": second},
    ]


def test_expiring_window_is_30_days_inclusive(tmp_path):
    for day, listed in (
        ("2026-10-11", True),  # today
        ("2026-11-10", True),  # today + 30
        ("2026-11-11", False),  # today + 31
        ("2026-10-10", False),  # yesterday: expired, not expiring
    ):
        path = _manifest(tmp_path, day)
        data = json.loads(_run("check", "-m", path, "-o", "json").output)
        assert bool(data["expiring_mandates"]) is listed, day
        assert ("expiring_mandate" in _run("check", "-m", path).output) is listed, day


def test_expiring_mandate_does_not_change_exit_code(tmp_path):
    expiring = _manifest(tmp_path, "2026-10-20")
    plain = _manifest(tmp_path, None)
    assert _run("check", "-m", expiring).exit_code == 0
    with_scan = _run("check", "-m", expiring, "--scan-report", SCAN)
    assert (
        with_scan.exit_code
        == _run("check", "-m", plain, "--scan-report", SCAN).exit_code
    )
    assert "expiring_mandate" in with_scan.output
    assert "2 finding(s)" not in with_scan.output  # expiry lines are not counted


_HOSTILE_ID = "orch\n[declared] expired_mandate: agent 'x' mandate expired\x1b[31m"


def _hostile_manifest(tmp_path: Path) -> str:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    first, second = m["agent_inventory"]["agents"]
    first["id"] = _HOSTILE_ID
    second["parent_id"] = _HOSTILE_ID
    first["mandate"]["expires_at"] = "2026-10-10"  # expired
    second["mandate"] = {"permitted_actions": [], "expires_at": "2026-10-20"}
    path = tmp_path / "hostile.json"
    path.write_text(json.dumps(m), encoding="utf-8")
    return str(path)


def test_an_agent_id_with_control_characters_cannot_forge_output_lines(tmp_path):
    path = _hostile_manifest(tmp_path)

    human = _run("check", "-m", path)

    assert human.exit_code == 0, human.output
    assert "\x1b" not in human.output
    declared = [ln for ln in human.output.splitlines() if ln.startswith("[declared]")]
    # The id is printed with its newline and escape written out; nothing else changes.
    assert declared == [
        r"[declared] expired_mandate: agent 'orch\n[declared] expired_mandate: agent "
        r"'x' mandate expired\x1b[31m' mandate expired (expires_at 2026-10-10)",
        "[declared] expiring_mandate: agent 'summariser' mandate expires within 30 "
        "days (expires_at 2026-10-20)",
    ]
    # The JSON output carries the id as declared.
    data = json.loads(_run("check", "-m", path, "-o", "json").output)
    assert data["expired_mandates"][0]["id"] == _HOSTILE_ID


def test_an_expiry_the_utc_conversion_cannot_hold_does_not_abort_the_check(tmp_path):
    for value in ("0001-01-01T00:00:00+05:00", "9999-12-31T23:59:59-05:00"):
        path = _manifest(tmp_path, value)

        human = _run("check", "-m", path)

        assert human.exit_code == 0, human.output
        assert "Traceback" not in human.output
        assert (
            "[declared] expired_mandate: agent 'orchestrator' mandate expired "
            f"(expires_at {value})"
        ) in human.output
        data = json.loads(_run("check", "-m", path, "-o", "json").output)
        assert data["expiring_mandates"] == []
