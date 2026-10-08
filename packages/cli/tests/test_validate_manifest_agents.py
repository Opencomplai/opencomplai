"""validate-manifest and init deep-check the optional agent_inventory block."""

from __future__ import annotations

import io
import json

import pytest
from opencomplai_cli import main
from rich.console import Console
from typer.testing import CliRunner


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run the CLI in a temp dir; returns run(*args) -> (exit, stdout, stderr)."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")

    out, err = io.StringIO(), io.StringIO()
    for name, buffer in (("console", out), ("err_console", err)):
        monkeypatch.setattr(
            main, name, Console(file=buffer, width=300, color_system=None)
        )

    def run(*args: str) -> tuple[int, str, str]:
        for buffer in (out, err):
            buffer.seek(0)
            buffer.truncate()
        result = CliRunner().invoke(main.app, list(args))
        return result.exit_code, out.getvalue(), err.getvalue()

    return run


def _agent(id: str, parent: str | None = None, **extra) -> dict:
    return {"id": id, "name": id, "parent_id": parent, **extra}


def _manifest(cli, tmp_path, agents: list[dict] | None) -> str:
    path = tmp_path / "system-manifest.json"
    code, _, _ = cli(
        "init",
        "--system-id",
        "agent-sys",
        "--intended-purpose",
        "support agent",
        "--output",
        str(path),
    )
    assert code == 0
    data = json.loads(path.read_text())
    if agents is not None:
        data["agent_inventory"] = {"agents": agents}
    path.write_text(json.dumps(data))
    return str(path)


def test_valid_inventory_passes(cli, tmp_path):
    path = _manifest(cli, tmp_path, [_agent("root"), _agent("child", "root")])
    code, out, _ = cli("validate-manifest", path)
    assert code == 0
    assert "Agents declared:       2" in out


def test_dangling_parent_exits_2_with_id(cli, tmp_path):
    path = _manifest(cli, tmp_path, [_agent("lonely", "ghost")])
    code, _, err = cli("validate-manifest", path)
    assert code == 2
    assert "lonely" in err
    assert "dangling parent" in err


def test_cycle_exits_2_with_id(cli, tmp_path):
    path = _manifest(cli, tmp_path, [_agent("selfie", "selfie")])
    code, _, err = cli("validate-manifest", path)
    assert code == 2
    assert "selfie" in err
    loop = [_agent("a", "c"), _agent("b", "a"), _agent("c", "b")]
    code, _, err = cli("validate-manifest", _manifest(cli, tmp_path, loop))
    assert code == 2
    assert "cycle" in err


def test_delegation_depth_exceeded_exits_2(cli, tmp_path):
    agents = [
        _agent("r", delegation={"max_depth": 1}),
        _agent("m", "r"),
        _agent("leaf", "m"),
    ]
    code, _, err = cli("validate-manifest", _manifest(cli, tmp_path, agents))
    assert code == 2
    assert "'r'" in err
    assert "max_depth" in err
    agents[0]["delegation"]["max_depth"] = 2
    code, _, _ = cli("validate-manifest", _manifest(cli, tmp_path, agents))
    assert code == 0


def test_unknown_tool_ref_exits_2(cli, tmp_path):
    agents = [_agent("a", mandate={"permitted_actions": ["tool:ghost"]})]
    code, _, err = cli("validate-manifest", _manifest(cli, tmp_path, agents))
    assert code == 2
    assert "ghost" in err


def test_no_inventory_output_unchanged(cli, tmp_path):
    code, out, _ = cli("validate-manifest", _manifest(cli, tmp_path, None))
    assert code == 0
    assert "Agents declared" not in out


def test_init_extras_bad_inventory_exits_2_and_writes_nothing(cli, tmp_path):
    extras = tmp_path / "extras.json"
    extras.write_text(
        json.dumps({"agent_inventory": {"agents": [_agent("a", "ghost")]}})
    )
    out_file = tmp_path / "bad-manifest.json"
    code, _, err = cli(
        "init",
        "--system-id",
        "agent-sys",
        "--intended-purpose",
        "support agent",
        "--section-extras-file",
        str(extras),
        "--output",
        str(out_file),
    )
    assert code == 2
    assert "dangling parent" in err
    assert not out_file.exists()
