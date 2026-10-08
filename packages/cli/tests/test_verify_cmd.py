"""SU-3b: `opencomplai verify` dispatches by kind and tells unsigned from tampered."""

from __future__ import annotations

import json
import re
from pathlib import Path

from opencomplai_cli.commands import verify as verify_mod
from opencomplai_cli.main import app, keys_rotate_cmd
from opencomplai_core import signing
from opencomplai_core.models import ScanResult, ScanStatusArtifact
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()


def _artifact() -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="uuid-1",
        system_id="test-sys",
        commit_ref="abc123",
        result=ScanResult.PASS,
        rationale_hash="sha256:def",
        duration_ms=10,
    )


def _write(tmp_path: Path, artifact: ScanStatusArtifact, name: str = "a.json") -> Path:
    p = tmp_path / name
    p.write_text(artifact.model_dump_json(), encoding="utf-8")
    return p


def _signed(tmp_path: Path, key_dir_name: str = "keys") -> tuple[Path, Path]:
    key_dir = tmp_path / key_dir_name
    generate_keypair(key_dir)
    art = _artifact()
    art.signature = signing.sign_artifact(art, key_dir / "signing.key")
    return _write(tmp_path, art), key_dir / "signing.pub"


def _run(path: Path, *args: str):
    return runner.invoke(app, ["verify", str(path), *args])


def test_signed_artifact_verifies(tmp_path):
    path, pub = _signed(tmp_path)
    res = _run(path, "--pub-key", str(pub))
    assert res.exit_code == 0
    assert "verified" in res.output


def test_unsigned_reported_distinctly(tmp_path, monkeypatch):
    path = _write(tmp_path, _artifact())

    def boom(*a, **k):
        raise AssertionError("verify_artifact must not be called")

    monkeypatch.setattr(signing, "verify_artifact", boom)
    # No key file at all: still reported as unsigned, not as a missing key.
    res = _run(path, "--pub-key", str(tmp_path / "none.pub"))
    assert res.exit_code == 1
    assert "unsigned" in res.output
    assert "INVALID" not in res.output


def test_tampered_artifact_exits_1(tmp_path):
    path, pub = _signed(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["system_id"] = "someone-else"
    path.write_text(json.dumps(data), encoding="utf-8")
    res = _run(path, "--pub-key", str(pub))
    assert res.exit_code == 1
    assert "INVALID" in res.output


def test_wrong_key_exits_1(tmp_path):
    path, _ = _signed(tmp_path)
    generate_keypair(tmp_path / "other")
    res = _run(path, "--pub-key", str(tmp_path / "other" / "signing.pub"))
    assert res.exit_code == 1
    assert "INVALID" in res.output


def test_missing_file_exits_2(tmp_path):
    assert _run(tmp_path / "nope.json").exit_code == 2


def test_unknown_kind_exits_2_lists_kinds(tmp_path):
    res = _run(_write(tmp_path, _artifact()), "--kind", "bogus")
    assert res.exit_code == 2
    assert "artifact" in res.output


def test_json_output_status_values(tmp_path):
    path, pub = _signed(tmp_path)
    ok = json.loads(_run(path, "--pub-key", str(pub), "-o", "json").output)
    assert ok["status"] == "verified"
    unsigned = _write(tmp_path, _artifact(), "u.json")
    res = _run(unsigned, "-o", "json")
    assert res.exit_code == 1
    assert json.loads(res.output)["status"] == "unsigned"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["commit_ref"] = "zzz"
    path.write_text(json.dumps(data), encoding="utf-8")
    bad = json.loads(_run(path, "--pub-key", str(pub), "-o", "json").output)
    assert bad["status"] == "invalid"


def test_register_kind_dispatches(tmp_path):
    verify_mod.register_kind(
        "dummy", lambda p, k: verify_mod.VerifyResult("dummy", "verified", "ok")
    )
    try:
        res = _run(_write(tmp_path, _artifact()), "--kind", "dummy", "-o", "json")
        assert res.exit_code == 0
        assert json.loads(res.output)["kind"] == "dummy"
    finally:
        verify_mod._KINDS.pop("dummy", None)


def test_docstring_paths_point_at_existing_page():
    root = Path(__file__).resolve().parents[3]
    files = [("keys_rotate_cmd", keys_rotate_cmd.__doc__ or "")]
    ds_keys = root / "dashboard-saas/packages/dashboard_db/src/dashboard_db/keys.py"
    # dashboard-saas/ is stripped from the public projection.
    if ds_keys.exists():
        files.append(("dashboard_db.keys", ds_keys.read_text(encoding="utf-8")))
    for name, text in files:
        m = re.search(r"docs/\S*key-management\.md", text)
        assert m, name
        assert (root / m.group(0)).is_file(), f"{name} points at {m.group(0)}"
