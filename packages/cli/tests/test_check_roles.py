from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_core.control_identity import make_control_id
from typer.testing import CliRunner

from .test_controls_sync import _FakeVault

SESSION = {
    "checker_version": "checker-test",
    "session_id": "abcdef12-0000-0000-0000-000000000000",
    "completed_at": "2026-01-01T00:00:00+00:00",
    "obligation_ids": ["deployer_high_risk"],
}


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
        "SIGNING_KEY_PRIVATE",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")

    def _run(*args: str):
        r = CliRunner().invoke(main.app, list(args))
        assert r.exit_code == 0, r.output
        return " ".join(r.output.split())

    _run(
        "init",
        "--system-id",
        "roles-sys",
        "--intended-purpose",
        "customer support chatbot for an online shop",
    )
    return _run


def _set(**fields: object) -> None:
    p = Path("system-manifest.json")
    m = json.loads(p.read_text())
    m.update(fields)
    p.write_text(json.dumps(m, indent=2))


def test_check_human_output_lists_all_roles(run):
    _set(
        operator_role="provider",
        operator_roles=["provider", "deployer"],
        checker_session=SESSION,
    )
    assert "roles=provider, deployer" in run("check")


def test_primary_role_still_printed_and_in_manifest(run):
    _set(operator_role="provider", checker_session=SESSION)
    out = run("check")
    assert "role=provider" in out
    assert "roles=" not in out
    assert json.loads(Path("system-manifest.json").read_text())["operator_role"] == (
        "provider"
    )


def test_no_session_output_unchanged(run):
    _set(operator_role="provider")
    out = run("check", "--with-gaps")
    assert "No checker session in manifest" in out
    assert "role=" not in out
    assert "roles=" not in out
    assert "Not applicable to this session" not in out


def test_check_with_gaps_controls_block_has_no_na_article(run, monkeypatch):
    monkeypatch.setenv("OPENCOMPLAI_VAULT_URL", "http://fake-vault.invalid")
    vault = _FakeVault()
    monkeypatch.setattr(main, "_vault_request", vault)
    _set(operator_role="deployer", checker_session=SESSION)
    out = run("check", "--with-gaps")
    artifact = json.loads(Path("compliance-artifact.json").read_text())
    na = artifact["gap_report"]["not_applicable"]
    assert na
    assert "Not applicable to this session" in out
    na_ids = {make_control_id("oss-default", "roles-sys", a) for a in na}
    items = {r["control_id"] for r in artifact["controls"]["items"]}
    sent = set(vault.controls["roles-sys"])
    assert items == sent
    assert not na_ids & (items | sent)
