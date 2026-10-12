"""SU-10b: `check` stamps the four provenance fields before signing."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest
from opencomplai_cli import main
from opencomplai_cli.check_signing import stamp_artifact
from opencomplai_cli.main import app
from opencomplai_cli.publish import envelope_signature, prepare_scan_status_artifact
from opencomplai_core.json_schemas import SCHEMA_VERSION
from opencomplai_core.models import ScanStatusArtifact, SystemManifest
from opencomplai_core.rules import RULE_SET_VERSION
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.signing import generate_keypair, sign_artifact, verify_artifact
from typer.testing import CliRunner

runner = CliRunner()
SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "dashboard-saas"
    / "schemas"
    / "first_scan_status.schema.json"
)
_PROVENANCE = ("rule_set_version", "cli_version", "schema_version", "manifest_sha256")


@pytest.fixture
def signed_check(tmp_path, monkeypatch):
    """Run `check --sign` in tmp_path; return (artifact dict, manifest, pubkey)."""
    monkeypatch.chdir(tmp_path)
    for var in ("OPENCOMPLAI_API_URL", "OPENCOMPLAI_VAULT_URL", "SIGNING_KEY_PRIVATE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    # No enclosing repo may leak into the tree stamps (the golden tests do the same).
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="prov-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["check", "--manifest", str(manifest), "--sign"])
    assert result.exit_code == 0, result.output
    raw = json.loads((tmp_path / "compliance-artifact.json").read_text("utf-8"))
    return raw, manifest, key_dir / "signing.pub"


def test_check_stamps_provenance_before_signing(signed_check):
    raw, _, pub = signed_check
    assert all(raw.get(k) for k in _PROVENANCE)
    assert raw["rule_set_version"] == RULE_SET_VERSION
    assert raw["schema_version"] == SCHEMA_VERSION
    artifact = ScanStatusArtifact.model_validate(raw)
    assert verify_artifact(artifact, pub) is True
    # The signature covers the stamps: change one and it no longer verifies.
    tampered = artifact.model_copy(update={"rule_set_version": "0.0.0"})
    assert verify_artifact(tampered, pub) is False


def test_signature_survives_push_with_provenance(signed_check, tmp_path):
    raw, _, pub = signed_check
    prepared = prepare_scan_status_artifact(raw, repo_dir=tmp_path)
    assert all(prepared[k] == raw[k] for k in _PROVENANCE)
    assert raw["signature"]
    signature = envelope_signature(raw, prepared)
    assert signature == raw["signature"]
    # The surviving signature must still cover the provenance fields.
    pushed = ScanStatusArtifact.model_validate({**prepared, "signature": signature})
    assert verify_artifact(pushed, pub) is True


def test_stamped_artifact_validates_against_widened_schema(signed_check, tmp_path):
    if not SCHEMA.exists():
        pytest.skip("dashboard-saas schema not present")
    raw, _, _ = signed_check
    prepared = prepare_scan_status_artifact(raw, commit_env={"GITHUB_SHA": "c" * 40})
    jsonschema.validate(prepared, json.loads(SCHEMA.read_text("utf-8")))


def test_manifest_sha256_matches_file_bytes(signed_check):
    raw, manifest, _ = signed_check
    lf_bytes = manifest.read_bytes().replace(b"\r\n", b"\n")
    assert raw["manifest_sha256"] == hashlib.sha256(lf_bytes).hexdigest()


def test_manifest_sha256_is_line_ending_independent():
    base = ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="a" * 40,
        result="pass",
        rationale_hash="r",
        duration_ms=1,
    )
    now = datetime(2030, 1, 1, tzinfo=UTC)
    lf = stamp_artifact(base, now=now, manifest_bytes=b'{\n  "a": 1\n}')
    crlf = stamp_artifact(base, now=now, manifest_bytes=b'{\r\n  "a": 1\r\n}')
    assert lf.manifest_sha256 == crlf.manifest_sha256
    assert stamp_artifact(base, now=now).manifest_sha256 is None


# --- CL-A1: tree_sha256 / tree_dirty / content-based input_digest -------------

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
_FILES = {"a.py": "print('a')\n", "pkg/b.py": "B = 1\n", ".gitignore": "ignored.txt\n"}
_NOW = datetime(2030, 1, 1, tzinfo=UTC)


def _git(path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=path, check=True, capture_output=True,
    )  # fmt: skip


def _git_repo(path: Path, files: dict[str, str] = _FILES) -> Path:
    path.mkdir(parents=True)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_bytes(text.encode("utf-8"))
    _git(path, "init", "-q")
    _git(path, "add", "--", *files)
    _git(path, "commit", "-q", "-m", "init")
    return path


def _bare_artifact() -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id="s",
        commit_ref="a" * 40,
        result="pass",
        rationale_hash="r",
        duration_ms=1,
    )


def _stamp(repo: Path) -> ScanStatusArtifact:
    return stamp_artifact(_bare_artifact(), now=_NOW, repo_root=repo)


@needs_git
def test_tree_sha256_same_tree_two_directories(tmp_path):
    one = _stamp(_git_repo(tmp_path / "one"))
    two = _stamp(_git_repo(tmp_path / "deeper" / "two"))
    assert one.tree_sha256 is not None
    assert len(one.tree_sha256) == 64
    assert one.tree_sha256 == two.tree_sha256


@needs_git
def test_modified_tracked_file_changes_tree_and_sets_dirty(tmp_path):
    repo = _git_repo(tmp_path / "repo")
    clean = _stamp(repo)
    (repo / "a.py").write_bytes(b"print('changed')\n")
    dirty = _stamp(repo)
    assert clean.tree_dirty is False
    assert dirty.tree_dirty is True
    assert dirty.tree_sha256 != clean.tree_sha256


@needs_git
def test_untracked_file_marks_dirty_and_changes_digest(tmp_path):
    repo = _git_repo(tmp_path / "repo")
    clean = _stamp(repo)
    (repo / "ignored.txt").write_bytes(b"secret\n")
    ignored = _stamp(repo)
    assert (ignored.tree_sha256, ignored.tree_dirty) == (
        clean.tree_sha256,
        False,
    )
    (repo / "new.py").write_bytes(b"NEW = 1\n")
    untracked = _stamp(repo)
    assert untracked.tree_dirty is True
    assert untracked.tree_sha256 != clean.tree_sha256


@needs_git
def test_clean_tree_reports_dirty_false(tmp_path):
    stamped = _stamp(_git_repo(tmp_path / "repo"))
    assert stamped.tree_dirty is False
    assert stamped.model_dump(mode="json")["tree_dirty"] is False


def test_fields_absent_outside_git_repo(signed_check, tmp_path, monkeypatch):
    raw, _, _ = signed_check
    assert "tree_sha256" not in raw
    assert "tree_dirty" not in raw
    bare = tmp_path / "bare"
    bare.mkdir()
    stamped = _stamp(bare)
    assert stamped.tree_sha256 is None
    assert stamped.tree_dirty is None


@needs_git
def test_fields_absent_when_git_missing(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "repo")

    def _no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr("opencomplai_cli.provenance.subprocess.run", _no_git)
    stamped = _stamp(repo)
    assert stamped.tree_sha256 is None
    assert stamped.tree_dirty is None
    dumped = stamped.model_dump(mode="json")
    assert "tree_sha256" not in dumped
    assert "tree_dirty" not in dumped


def test_new_fields_omitted_when_none_kept_when_set():
    base = _bare_artifact()
    dumped = base.model_dump(mode="json")
    assert "tree_sha256" not in dumped
    assert "tree_dirty" not in dumped
    kept = base.model_copy(update={"tree_sha256": "c" * 64, "tree_dirty": False})
    dumped = kept.model_dump(mode="json")
    assert dumped["tree_sha256"] == "c" * 64
    assert dumped["tree_dirty"] is False


@needs_git
def test_tree_fields_are_covered_by_signature(tmp_path):
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    stamped = _stamp(_git_repo(tmp_path / "repo"))
    signed = stamped.model_copy(
        update={"signature": sign_artifact(stamped, key_dir / "signing.key")}
    )
    assert verify_artifact(signed, key_dir / "signing.pub") is True
    tampered = signed.model_copy(update={"tree_sha256": "d" * 64})
    assert verify_artifact(tampered, key_dir / "signing.pub") is False
    flipped = signed.model_copy(update={"tree_dirty": True})
    assert verify_artifact(flipped, key_dir / "signing.pub") is False


@needs_git
def test_check_in_git_repo_stamps_and_signs(tmp_path, monkeypatch):
    repo = _git_repo(tmp_path / "repo")
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.chdir(out)
    for var in ("OPENCOMPLAI_API_URL", "OPENCOMPLAI_VAULT_URL", "SIGNING_KEY_PRIVATE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="prov-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "check", "--manifest", str(manifest), "--sign",
            "--repo-root", str(repo), "--output-dir", str(out),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    raw = json.loads((out / "compliance-artifact.json").read_text("utf-8"))
    assert re.fullmatch(r"[0-9a-f]{64}", raw["tree_sha256"])
    assert raw["tree_dirty"] is False
    assert raw["tree_sha256"] == _stamp(repo).tree_sha256
    artifact = ScanStatusArtifact.model_validate(raw)
    assert verify_artifact(artifact, key_dir / "signing.pub") is True
    assert prepare_scan_status_artifact(raw, repo_dir=repo) == raw


def _scan_tree(root: Path, extra: str = "") -> Path:
    root.mkdir(parents=True)
    (root / "requirements.txt").write_bytes(b"face_recognition\n")
    (root / "src").mkdir()
    (root / "src" / "face.py").write_bytes(f"import face_recognition\n{extra}".encode())
    return root


def test_input_digest_same_tree_two_directories(tmp_path):
    one = run_scan("s", "c" * 40, _scan_tree(tmp_path / "one"), "chatbot")
    two = run_scan("s", "c" * 40, _scan_tree(tmp_path / "x" / "two"), "chatbot")
    assert one.input_digest == two.input_digest
    assert one.input_digest.startswith("sha256:")


def test_input_digest_changes_with_content(tmp_path):
    one = run_scan("s", "c" * 40, _scan_tree(tmp_path / "one"), "chatbot")
    two = run_scan("s", "c" * 40, _scan_tree(tmp_path / "two", "X = 1\n"), "chatbot")
    assert one.input_digest != two.input_digest
