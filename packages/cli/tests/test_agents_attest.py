"""`opencomplai agents attest` and `opencomplai verify --kind agent-attestation`."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import opencomplai_cli.main as main_module
import pytest
from opencomplai_cli.commands import agents_attest
from opencomplai_cli.main import app
from opencomplai_core.agent_attestation import mandate_sha256
from opencomplai_core.agent_inventory import (
    AgentInventory,
    AgentMandate,
    AgentSpec,
    AgentTool,
)
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
NOW = datetime(2026, 6, 1, 12, 0, 0, 123456, tzinfo=UTC)
MANDATE = AgentMandate(permitted_actions=["tool:search"], limits={"max": 3})


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    keys = tmp_path / "keys"
    generate_keypair(keys)
    monkeypatch.setattr(main_module, "_SIGNING_KEY", keys / "signing.key")
    monkeypatch.setattr(main_module, "_SIGNING_PUB", keys / "signing.pub")
    monkeypatch.setattr(agents_attest, "_now", lambda: NOW)
    monkeypatch.chdir(tmp_path)
    return keys


def _manifest(
    tmp_path: Path, agents: list[AgentSpec] | None = None, inventory=True
) -> Path:
    path = tmp_path / "system-manifest.json"
    res = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "att-sys",
            "--intended-purpose",
            "support bot",
            "--output",
            str(path),
        ],
    )
    assert res.exit_code == 0, res.output
    if inventory:
        agents = agents or [
            AgentSpec(
                id="a1",
                name="Agent One",
                tools=[AgentTool(name="search", kind="function")],
                mandate=MANDATE,
            ),
            AgentSpec(id="nomandate", name="No mandate"),
        ]
        data = json.loads(path.read_text(encoding="utf-8"))
        data["agent_inventory"] = AgentInventory(agents=agents).model_dump(
            mode="json", exclude_none=True
        )
        path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _attest(tmp_path: Path, *extra: str, agent="a1", manifest: Path | None = None):
    manifest = manifest or _manifest(tmp_path)
    return runner.invoke(
        app,
        [
            "agents",
            "attest",
            "--manifest",
            str(manifest),
            "--agent-id",
            agent,
            "--issuer",
            "Example Issuer",
            "--out",
            str(tmp_path / "att.json"),
            *extra,
        ],
    )


def _verify(tmp_path: Path, *extra: str, path: Path | None = None):
    return runner.invoke(
        app,
        [
            "verify",
            str(path or tmp_path / "att.json"),
            "--kind",
            "agent-attestation",
            *extra,
        ],
    )


def _load(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "att.json").read_text(encoding="utf-8"))


def test_attest_writes_signed_file(tmp_path):
    res = _attest(tmp_path)
    assert res.exit_code == 0, res.output
    att = _load(tmp_path)
    assert att["agent_id"] == "a1"
    assert att["system_id"] == "att-sys"
    assert att["mandate_sha256"] == mandate_sha256(MANDATE)
    assert att["issued_at"] == "2026-06-01T12:00:00Z"
    assert att["expires_at"] == "2026-07-01T12:00:00Z"
    assert att["signature"]
    assert att["key_id"] in res.output
    assert "BEGIN" not in res.output


def test_attest_then_verify_round_trip(tmp_path):
    assert _attest(tmp_path).exit_code == 0
    res = _verify(tmp_path)
    assert res.exit_code == 0, res.output
    assert "verified" in res.output


def test_verify_expired_exits_1(tmp_path):
    _attest(tmp_path, "--valid-days", "1")
    res = _verify(tmp_path, "--expect", "now=2026-06-02T12:00:00Z")
    assert res.exit_code == 1
    assert "expired" in res.output


def test_verify_tampered_exits_1(tmp_path):
    _attest(tmp_path)
    att = _load(tmp_path)
    att["expires_at"] = "2099-01-01T00:00:00Z"
    (tmp_path / "att.json").write_text(json.dumps(att), encoding="utf-8")
    res = _verify(tmp_path)
    assert res.exit_code == 1
    assert "signature" in res.output


def test_verify_mandate_mismatch_exits_1(tmp_path):
    _attest(tmp_path)
    res = _verify(tmp_path, "--expect", "mandate_sha256=sha256:" + "0" * 64)
    assert res.exit_code == 1
    assert "mandate_mismatch" in res.output


def test_verify_mandate_match_exits_0(tmp_path):
    _attest(tmp_path)
    res = _verify(tmp_path, "--expect", f"mandate_sha256={mandate_sha256(MANDATE)}")
    assert res.exit_code == 0, res.output


def test_verify_unsigned_reported_distinctly(tmp_path):
    _attest(tmp_path)
    att = _load(tmp_path)
    att["signature"] = None
    (tmp_path / "att.json").write_text(json.dumps(att), encoding="utf-8")
    res = _verify(tmp_path)
    assert res.exit_code == 1
    assert "unsigned" in res.output
    assert "INVALID" not in res.output


def test_verify_wrong_public_key_exits_1(tmp_path):
    _attest(tmp_path)
    other = tmp_path / "other"
    generate_keypair(other)
    res = _verify(tmp_path, "--pub-key", str(other / "signing.pub"))
    assert res.exit_code == 1
    assert "key_id" in res.output


def test_attest_unknown_agent_exits_2(tmp_path):
    res = _attest(tmp_path, agent="ghost")
    assert res.exit_code == 2
    assert "a1" in res.output
    assert not (tmp_path / "att.json").exists()


def test_attest_agent_without_mandate_exits_2(tmp_path):
    res = _attest(tmp_path, agent="nomandate")
    assert res.exit_code == 2
    assert "no mandate" in res.output


def test_attest_no_key_exits_2_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "_SIGNING_KEY", tmp_path / "missing.key")
    res = _attest(tmp_path)
    assert res.exit_code == 2
    assert not (tmp_path / "att.json").exists()


def test_attest_invalid_inventory_exits_2(tmp_path):
    bad = [
        AgentSpec(id="a1", name="A", parent_id="ghost", mandate=MANDATE),
    ]
    res = _attest(tmp_path, manifest=_manifest(tmp_path, bad))
    assert res.exit_code == 2
    assert "dangling parent" in res.output


def test_attest_without_inventory_exits_2(tmp_path):
    res = _attest(tmp_path, manifest=_manifest(tmp_path, inventory=False))
    assert res.exit_code == 2


def test_attest_refuses_overwrite(tmp_path):
    assert _attest(tmp_path).exit_code == 0
    before = (tmp_path / "att.json").read_bytes()
    assert _attest(tmp_path).exit_code == 2
    assert (tmp_path / "att.json").read_bytes() == before


def test_attest_output_is_reproducible(tmp_path):
    manifest = _manifest(tmp_path)
    assert _attest(tmp_path, manifest=manifest).exit_code == 0
    first = (tmp_path / "att.json").read_bytes()
    (tmp_path / "att.json").unlink()
    assert _attest(tmp_path, manifest=manifest).exit_code == 0
    assert (tmp_path / "att.json").read_bytes() == first


def test_verify_malformed_expect_exits_2(tmp_path):
    _attest(tmp_path)
    assert _verify(tmp_path, "--expect", "nonsense").exit_code == 2
    assert _verify(tmp_path, "--expect", "now=yesterday").exit_code == 2


def test_expect_does_not_leak_between_calls(tmp_path):
    _attest(tmp_path)
    assert (
        _verify(tmp_path, "--expect", "mandate_sha256=sha256:" + "0" * 64).exit_code
        == 1
    )
    assert _verify(tmp_path).exit_code == 0


def test_verify_non_object_json_exits_2(tmp_path):
    bad = tmp_path / "list.json"
    bad.write_text("[]", encoding="utf-8")
    assert _verify(tmp_path, path=bad).exit_code == 2


def test_verify_unknown_kind_lists_agent_attestation(tmp_path):
    res = runner.invoke(app, ["verify", str(tmp_path / "x.json"), "--kind", "nope"])
    assert res.exit_code == 2
    assert "agent-attestation" in res.output


def test_readme_row_present_for_agents_group():
    readme = Path(__file__).resolve().parents[1] / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "`agents`" in text
    assert "attest" in text
