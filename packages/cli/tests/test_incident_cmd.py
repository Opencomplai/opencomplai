"""`opencomplai incident` command group: lifecycle, injected clock, exports, misuse."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

DECLARED = "2026-03-01T10:00:00Z"
AWARE = "2026-03-01T08:00:00Z"


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("OPENCOMPLAI_NOW", "2026-03-01T12:00:00Z")
    monkeypatch.chdir(tmp_path)  # default manifest path must not leak in from the repo
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setattr("opencomplai_cli.main._SIGNING_KEY", tmp_path / "no.key")


def _run(reg: Path, *args: str):
    return runner.invoke(app, ["incident", *args, "--file", str(reg)])


def _declare(reg: Path, cls: str | None = None):
    args = [
        "declare",
        "--system-id",
        "sys-1",
        "--description",
        "leak",
        "--aware-at",
        AWARE,
        "--declared-at",
        DECLARED,
    ]
    if cls:
        args += ["--class", cls]
    return _run(reg, *args)


def _status(reg: Path, *extra: str) -> dict:
    res = _run(reg, "status", "--output", "json", *extra)
    assert res.exit_code == 0, res.output
    return json.loads(res.stdout)["incidents"][0]


def test_declare_classify_notify_close_lifecycle(tmp_path: Path):
    reg = tmp_path / "r.json"
    res = _declare(reg)
    assert res.exit_code == 0
    assert "INC-0001" in res.stdout
    assert (
        _run(
            reg, "classify", "--id", "INC-0001", "--class", "critical_infrastructure"
        ).exit_code
        == 0
    )
    assert _status(reg)["state"] == "open"
    res = _run(
        reg, "notify", "--id", "INC-0001", "--party", "MA", "--kind", "authority"
    )
    assert res.exit_code == 0, res.output
    assert _status(reg)["state"] == "met"
    res = _run(reg, "close", "--id", "INC-0001", "--note", "fixed")
    assert res.exit_code == 0, res.output
    row = _status(reg)
    assert row["state"] == "met"
    assert row["closed"] is True


def test_status_overdue_then_met_with_injected_clock(tmp_path: Path, monkeypatch):
    reg = tmp_path / "r.json"
    _declare(reg, "critical_infrastructure")  # due 2026-03-03T08:00Z
    monkeypatch.setenv("OPENCOMPLAI_NOW", "2026-03-04T00:00:00Z")
    assert _status(reg)["state"] == "overdue"
    monkeypatch.setenv("OPENCOMPLAI_NOW", "2026-03-02T00:00:00Z")
    assert _status(reg)["state"] == "open"
    res = _run(
        reg,
        "notify",
        "--id",
        "INC-0001",
        "--party",
        "MA",
        "--kind",
        "authority",
        "--sent-at",
        "2026-03-02T09:00:00Z",
    )
    assert res.exit_code == 0
    monkeypatch.setenv("OPENCOMPLAI_NOW", "2026-03-04T00:00:00Z")
    assert _status(reg)["state"] == "met"


def test_unclassified_status_warns_no_clock(tmp_path: Path):
    reg = tmp_path / "r.json"
    _declare(reg)
    res = _run(reg, "status")
    assert res.exit_code == 0
    assert "no_clock" in res.stdout
    assert "unclassified" in res.stderr


def test_validation_errors_exit_2_and_leave_register_untouched(tmp_path: Path):
    reg = tmp_path / "r.json"
    _declare(reg)
    _run(
        reg,
        "close",
        "--id",
        "INC-0001",
        "--note",
        "done",
        "--closed-at",
        "2026-03-02T00:00:00Z",
    )
    before = reg.read_bytes()
    bad = [
        ["classify", "--id", "INC-9", "--class", "death"],
        [
            "declare",
            "--system-id",
            "s",
            "--description",
            "x",
            "--aware-at",
            DECLARED,
            "--declared-at",
            AWARE,
        ],
        ["close", "--id", "INC-0001", "--note", "again"],
        [
            "notify",
            "--id",
            "INC-0001",
            "--party",
            "MA",
            "--kind",
            "authority",
            "--sent-at",
            "junk",
        ],
        ["declare", "--system-id", "s", "--description", "x", "--declared-at", "junk"],
    ]
    for args in bad:
        res = _run(reg, *args)
        assert res.exit_code == 2, (args, res.output)
        assert reg.read_bytes() == before


def test_export_markdown_and_json_are_deterministic(tmp_path: Path):
    reg = tmp_path / "r.json"
    _declare(reg, "death")
    for fmt in ("md", "json"):
        outs = []
        for name in ("a", "b"):
            out = tmp_path / f"{name}.{fmt}"
            res = _run(
                reg, "export", "--id", "INC-0001", "--format", fmt, "--output", str(out)
            )
            assert res.exit_code == 0, res.output
            outs.append(out.read_bytes())
        assert outs[0] == outs[1]
        assert b"2026-03-11T08:00:00Z" in outs[0]
    res = _run(reg, "export", "--id", "INC-0001")
    assert res.exit_code == 0
    assert "# Incident INC-0001" in res.stdout


def test_status_lists_pending_manifest_contacts(tmp_path: Path):
    reg = tmp_path / "r.json"
    _declare(reg, "death")
    man = tmp_path / "m.json"
    man.write_text(
        json.dumps(
            {
                "system_id": "sys-1",
                "incident_contacts": [
                    {"kind": "authority", "party": "MA"},
                    {"kind": "deployer", "party": "Acme"},
                ],
            }
        )
    )
    _run(reg, "notify", "--id", "INC-0001", "--party", "ma", "--kind", "authority")
    assert _status(reg, "--manifest", str(man))["pending_contacts"] == ["Acme"]
    man.write_text("{bad")
    res = _run(reg, "status", "--manifest", str(man))
    assert res.exit_code == 0
    assert "unreadable" in res.stderr


def test_incident_group_is_registered_and_help_lists_subcommands():
    res = runner.invoke(app, ["incident", "--help"])
    assert res.exit_code == 0
    for sub in ("declare", "classify", "notify", "close", "status", "export"):
        assert sub in res.stdout


def test_declare_drives_state_to_incident_mode(tmp_path: Path):
    _declare(tmp_path / "r.json", "death")
    records = json.loads((tmp_path / "state" / "system-state.json").read_text())
    assert records["sys-1"]["state"] == "incident_mode"
