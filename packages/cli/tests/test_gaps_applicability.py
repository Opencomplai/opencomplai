"""`gaps` projects a recorded checker session's applicability (E-1)."""

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
        "applic-sys",
        "--intended-purpose",
        "credit scoring for loan applications",
    )
    assert result.exit_code == 0, result.output
    return run


def _gaps_payload(run) -> dict:
    result = run("gaps", "--output", "json")
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)["payload"]


def test_gaps_json_lists_not_applicable_for_a_deployer_manifest(cli):
    path = Path("system-manifest.json")
    manifest = json.loads(path.read_text())
    manifest["operator_role"] = "deployer"
    manifest["checker_session"] = {
        "checker_version": "checker-test",
        "session_id": "sess-cli",
        "completed_at": "2026-09-18T00:00:00+00:00",
        "obligation_ids": ["deployer_general", "ai_literacy"],
    }
    path.write_text(json.dumps(manifest, indent=2))

    payload = _gaps_payload(cli)
    assert payload["not_applicable"]["Art. 9"]
    assert "Art. 9" not in {row["article"] for row in payload["articles"]}


def test_gaps_json_without_session_has_no_not_applicable_key(cli):
    payload = _gaps_payload(cli)
    assert "not_applicable" not in payload
    assert "Art. 9" in {row["article"] for row in payload["articles"]}
