"""Tests for `opencomplai agents` (inventory, check, report): offline only."""

from __future__ import annotations

import json
import re
import socket
from pathlib import Path

import opencomplai_cli.main as main_module
import pytest
from opencomplai_cli.main import app
from opencomplai_core.agent_responsibility import get_responsibilities
from typer.testing import CliRunner

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures" / "agents"
MANIFEST = str(FIXTURES / "sample-manifest.json")
SCAN = str(FIXTURES / "sample-scan-report.json")
_MET = re.compile(r"\bMet\b")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)

    def boom(*_a, **_k):
        raise AssertionError("agents commands must stay offline")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(main_module, "_vault_request", boom)


def _run(*args: str):
    return runner.invoke(app, ["agents", *args])


def _clean_scan(tmp_path: Path) -> str:
    """The sample scan with every declared thing detected (OpenAI SDK, MCP)."""
    scan = json.loads(Path(SCAN).read_text())
    scan["evidence"][1]["token_label"] = "openai"
    scan["evidence"].append(
        {
            **scan["evidence"][0],
            "evidence_id": "ev2",
            "category": "mcp_server",
            "token_label": "mcp",
        }
    )
    scan["findings"].append(
        {
            **scan["findings"][0],
            "finding_id": "f2",
            "signal_category": "mcp_server",
            "evidence_ids": ["ev2"],
        }
    )
    path = tmp_path / "clean-scan.json"
    path.write_text(json.dumps(scan))
    return str(path)


def _invalid_manifest(tmp_path: Path) -> str:
    m = json.loads(Path(MANIFEST).read_text())
    m["agent_inventory"]["agents"][1]["parent_id"] = "ghost"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(m))
    return str(path)


def test_agents_group_registered():
    assert "agents" in {g.name for g in main_module.app.registered_groups}


def test_commands_run_offline_on_sample_manifest():
    for cmd in (["inventory"], ["report"], ["check"]):
        result = _run(*cmd, "-m", MANIFEST)
        assert result.exit_code == 0, result.output
    # With a scan report supplied the commands are still local-only.
    assert _run("check", "-m", MANIFEST, "--scan-report", SCAN).exit_code == 1


def test_inventory_lists_agents():
    result = _run("inventory", "-m", MANIFEST)
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert lines[0].startswith("- orchestrator")
    assert "ticket-search" in lines[0]
    assert lines[1].startswith("  - summariser")
    data = json.loads(_run("inventory", "-m", MANIFEST, "-o", "json").output)
    assert [a["id"] for a in data["agents"]] == ["orchestrator", "summariser"]


def test_inventory_without_block_exits_0(tmp_path):
    m = json.loads(Path(MANIFEST).read_text())
    del m["agent_inventory"]
    path = tmp_path / "m.json"
    path.write_text(json.dumps(m))
    result = _run("inventory", "-m", str(path))
    assert result.exit_code == 0
    assert "no agent inventory declared" in result.output


def test_check_exits_1_on_undeclared_detected_framework():
    # The sample scan sees an SDK (llamaindex) the manifest does not declare.
    result = _run("check", "-m", MANIFEST, "--scan-report", SCAN)
    assert result.exit_code == 1
    assert "[detected] detected_not_declared: llamaindex" in result.output
    assert "not a compliance verdict" in result.output


def test_check_exits_0_when_declaration_and_scan_agree(tmp_path):
    result = _run("check", "-m", MANIFEST, "--scan-report", _clean_scan(tmp_path))
    assert result.exit_code == 0, result.output


def test_check_exits_2_on_invalid_inventory(tmp_path):
    result = _run("check", "-m", _invalid_manifest(tmp_path))
    assert result.exit_code == 2
    assert "summariser" in result.output
    assert _run("check", "-m", str(tmp_path / "missing.json")).exit_code == 2


def test_check_never_emits_met(tmp_path):
    for scan in (None, SCAN, _clean_scan(tmp_path)):
        extra = ["--scan-report", scan] if scan else []
        for fmt in ("human", "json"):
            out = _run("check", "-m", MANIFEST, *extra, "-o", fmt).output
            assert not _MET.search(out), out
            assert "not a compliance verdict" in out


def test_report_lists_responsibilities_with_review_flag():
    expected = {r.id for r in get_responsibilities()}
    data = json.loads(_run("report", "-m", MANIFEST, "--format", "json").output)
    rows = data["responsibility_map"]["reference_rows"]
    assert {r["id"] for r in rows} == expected
    assert all(r["needs_founder_review"] is True and r["confidence"] for r in rows)
    md = _run("report", "-m", MANIFEST).output
    flagged = [ln for ln in md.splitlines() if "needs_founder_review: true" in ln]
    assert len(flagged) == len(expected)
    assert not _MET.search(md)


def test_report_writes_output_file(tmp_path):
    out = tmp_path / "agents.md"
    result = _run("report", "-m", MANIFEST, "--output", str(out))
    assert result.exit_code == 0
    assert result.output == ""
    assert out.read_text(encoding="utf-8").startswith(
        "# Agent report: sys-agents-sample"
    )
