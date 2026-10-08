"""`verify --expect` keys, log anchors and empty logs (SU-G7h)."""

from __future__ import annotations

import json
from pathlib import Path

import opencomplai_cli.main as main_module
import pytest
from opencomplai_cli.main import app
from opencomplai_core.models import ScanResult, ScanStatusArtifact
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain, generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
TS = "2026-03-01T10:00:00+00:00"
GENESIS = "sha256:" + "0" * 64
KINDS = [
    ("oversight-log", SigningDomain.OVERSIGHT_LOG),
    ("incident-log", SigningDomain.INCIDENT_LOG),
    ("agent-log", SigningDomain.AGENT_LOG),
]


@pytest.fixture(autouse=True)
def keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setattr(main_module, "_SIGNING_PUB", tmp_path / "none" / "signing.pub")
    generate_keypair(tmp_path / "keys")
    return tmp_path / "keys"


def _make_log(tmp_path: Path, domain, n: int, keys: Path) -> Path:
    path = tmp_path / "log.jsonl"
    log = SignedLog(path, domain)
    for i in range(n):
        log.append(
            {"event": "e", "n": i},
            ts=TS,
            private_pem=(keys / "signing.key").read_bytes(),
        )
    return path


def _v(path: Path, kind: str, keys: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "verify",
            str(path),
            "--kind",
            kind,
            "--pub-key",
            str(keys / "signing.pub"),
            "--output",
            "json",
            *extra,
        ],
    )


def _status(res) -> dict:
    return json.loads(res.stdout.strip().splitlines()[-1])


def _anchor(path: Path, domain) -> tuple[str, int]:
    log = SignedLog(path, domain)
    return log.head(), len(log.entries())


@pytest.mark.parametrize(("kind", "domain"), KINDS)
def test_unsupported_expect_key_exits_2(tmp_path, keys, kind, domain):
    path = _make_log(tmp_path, domain, 3, keys)
    res = _v(path, kind, keys, "--expect", "now=2026-01-01T00:00:00Z")
    assert res.exit_code == 2
    assert "does not support" in res.output


def test_unsupported_expect_key_exits_2_artifact(tmp_path):
    art = ScanStatusArtifact(
        install_id="uuid-1",
        system_id="test-sys",
        commit_ref="abc123",
        result=ScanResult.PASS,
        rationale_hash="sha256:def",
        duration_ms=10,
    )
    p = tmp_path / "a.json"
    p.write_text(art.model_dump_json(), encoding="utf-8")
    assert runner.invoke(app, ["verify", str(p)]).exit_code == 1  # unsigned
    res = runner.invoke(app, ["verify", str(p), "--expect", "head=x"])
    assert res.exit_code == 2
    assert "does not support" in res.output


@pytest.mark.parametrize(("kind", "domain"), KINDS)
def test_log_kinds_enforce_head_and_count(tmp_path, keys, kind, domain):
    path = _make_log(tmp_path, domain, 3, keys)
    head, count = _anchor(path, domain)
    assert count == 3
    ok = _v(path, kind, keys, "--expect", f"head={head}", "--expect", "count=3")
    assert ok.exit_code == 0, ok.output
    assert _status(ok)["status"] == "verified"
    for flag in ("count=2", "count=4", f"head={GENESIS}"):
        res = _v(path, kind, keys, "--expect", flag)
        assert res.exit_code == 1, (flag, res.output)
        out = _status(res)
        assert out["status"] == "invalid"
        assert "does not match" in out["detail"]
        assert out["detail"].endswith(f"head={head} count=3")


@pytest.mark.parametrize(("kind", "domain"), KINDS)
def test_truncated_log_fails_against_recorded_head(tmp_path, keys, kind, domain):
    path = _make_log(tmp_path, domain, 3, keys)
    head, _ = _anchor(path, domain)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(lines[:2]), encoding="utf-8")
    # The documented ceiling: no anchor, no detection.
    assert _v(path, kind, keys).exit_code == 0
    assert _v(path, kind, keys, "--expect", f"head={head}").exit_code == 1
    assert _v(path, kind, keys, "--expect", "count=3").exit_code == 1
    path.write_text("", encoding="utf-8")
    assert _v(path, kind, keys, "--expect", f"head={head}").exit_code == 1


@pytest.mark.parametrize(("kind", "domain"), KINDS)
@pytest.mark.parametrize("content", ["", " \n\t\n"])
@pytest.mark.parametrize(
    "extra",
    [
        (),
        ("--expect", "count=0"),
        ("--expect", "count=0", "--expect", f"head={GENESIS}"),
    ],
)
def test_empty_log_is_not_verified(tmp_path, keys, kind, domain, content, extra):
    path = tmp_path / "empty.jsonl"
    path.write_text(content, encoding="utf-8")
    res = _v(path, kind, keys, *extra)
    assert res.exit_code == 1, res.output
    out = _status(res)
    assert out["status"] == "invalid"
    assert "empty log" in out["detail"]


@pytest.mark.parametrize(("kind", "domain"), KINDS)
@pytest.mark.parametrize(
    "extra",
    [
        ("--expect", "count=abc"),
        ("--expect", "count=-1"),
        ("--expect", "count="),
        ("--expect", "head=a", "--expect", "head=b"),
    ],
)
def test_expect_count_and_duplicate_keys_exit_2(tmp_path, keys, kind, domain, extra):
    path = _make_log(tmp_path, domain, 1, keys)
    assert _v(path, kind, keys, *extra).exit_code == 2


def test_agents_verify_log_command_rejects_empty_log(tmp_path, keys):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    res = runner.invoke(app, ["agents", "verify-log", str(empty), "-o", "json"])
    assert res.exit_code == 1
    assert json.loads(res.stdout)["status"] == "invalid"
    res = runner.invoke(app, ["agents", "verify-log", str(empty)])
    assert res.exit_code == 1
    assert "INVALID: empty log" in res.output
    one = _make_log(tmp_path, SigningDomain.AGENT_LOG, 1, keys)
    pub = str(keys / "signing.pub")
    res = runner.invoke(app, ["agents", "verify-log", str(one), "--pub-key", pub])
    assert res.exit_code == 0, res.output
