"""validate-manifest checks the optional human_oversight block; gaps reads it."""

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


def _manifest(cli, tmp_path, block: dict | None, **extra) -> str:
    path = tmp_path / "system-manifest.json"
    code, _, _ = cli(
        "init",
        "--system-id",
        "oversight-sys",
        "--intended-purpose",
        "credit scoring",
        "--output",
        str(path),
    )
    assert code == 0
    data = json.loads(path.read_text())
    if block is not None:
        data["human_oversight"] = block
    data.update(extra)
    path.write_text(json.dumps(data))
    return str(path)


def _role(name: str, **extra) -> dict:
    return {"role": name, "training_ref": "docs/training.md", **extra}


def test_valid_block_prints_summary(cli, tmp_path):
    block = {"roles": [_role("A", can_intervene=True), _role("B")]}
    code, out, err = cli("validate-manifest", _manifest(cli, tmp_path, block))
    assert code == 0
    assert "human_oversight:       2 role(s), 1 can intervene" in out
    assert "Warning" not in err


def test_duplicate_roles_exit_2(cli, tmp_path):
    block = {"roles": [_role("Officer"), _role("officer ")]}
    code, _, err = cli("validate-manifest", _manifest(cli, tmp_path, block))
    assert code == 2
    assert "duplicate oversight role" in err


def test_empty_roles_exit_2(cli, tmp_path):
    code, _, _ = cli("validate-manifest", _manifest(cli, tmp_path, {"roles": []}))
    assert code == 2


def test_no_intervening_role_warns_on_stderr_exit_0(cli, tmp_path):
    block = {"roles": [_role("Observer")]}
    code, out, err = cli("validate-manifest", _manifest(cli, tmp_path, block))
    assert code == 0
    assert "Warning: human_oversight: no declared role can intervene" in err
    assert "Warning" not in out


def test_json_output_stays_parseable_with_warnings(cli, tmp_path):
    block = {"roles": [_role("Observer")]}
    path = _manifest(cli, tmp_path, block)
    code, out, err = cli("validate-manifest", path, "--output", "json")
    assert code == 0
    assert json.loads(out)["human_oversight"]["roles"][0]["role"] == "Observer"
    assert "no declared role can intervene" in err


def test_legacy_only_manifest_output_unchanged(cli, tmp_path):
    path = _manifest(
        cli, tmp_path, None, human_oversight_measures=["A human reviews decisions"]
    )
    code, out, err = cli("validate-manifest", path)
    assert code == 0
    assert "human_oversight" not in out
    assert "Warning" not in err


def _art14(cli, path: str, repo: str) -> dict:
    code, out, _ = cli(
        "gaps", "--manifest", path, "--repo-root", repo, "--output", "json"
    )
    assert code == 0, out
    rows = json.loads(out)["payload"]["articles"]
    return next(r for r in rows if r["article"] == "Art. 14")


def test_gaps_reads_block_into_art14_row(cli, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    block = {"roles": [_role("A", can_intervene=True)]}
    row = _art14(cli, _manifest(cli, tmp_path, block), str(repo))
    assert row["source"] == "manifest"
    assert row["status"] == "partial"
    plain = _art14(cli, _manifest(cli, tmp_path, None), str(repo))
    assert plain["source"] != "manifest"
