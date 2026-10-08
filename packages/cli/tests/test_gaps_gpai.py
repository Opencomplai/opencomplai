"""`gaps` reads GPAI artifact probes only for a recorded GPAI checker session (SU-135a)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from typer.testing import CliRunner


@pytest.fixture
def cli(tmp_path, monkeypatch):
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

    def run(*args: str):
        return CliRunner().invoke(main.app, list(args))

    result = run(
        "init",
        "--system-id",
        "gpai-sys",
        "--intended-purpose",
        "general-purpose language model",
    )
    assert result.exit_code == 0, result.output
    return run


def _art_53(run, tmp_path: Path) -> dict:
    empty = tmp_path / "empty-repo"
    empty.mkdir()
    result = run("gaps", "--output", "json", "--repo-root", str(empty))
    assert result.exit_code == 0, result.output
    rows = json.loads(result.stdout)["payload"]["articles"]
    return next(row for row in rows if row["article"] == "Art. 53")


def test_gaps_json_gpai_session_has_artifact_row_for_art_53(cli, tmp_path):
    path = Path("system-manifest.json")
    manifest = json.loads(path.read_text())
    manifest["operator_role"] = "provider"
    manifest["checker_session"] = {
        "checker_version": "checker-test",
        "session_id": "sess-gpai",
        "completed_at": "2026-09-18T00:00:00+00:00",
        "obligation_ids": ["gpai_provider"],
    }
    path.write_text(json.dumps(manifest, indent=2))

    row = _art_53(cli, tmp_path)
    assert row["status"] == "missing"
    assert row["source"] == "artifact"


def test_gaps_json_without_session_keeps_obligation_row_for_art_53(cli, tmp_path):
    row = _art_53(cli, tmp_path)
    assert row["status"] == "unverified"
    assert row["source"] == "obligation"
