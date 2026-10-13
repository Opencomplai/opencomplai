"""A recorded report file does not stale a confirmed classification proposal.

`check --scan` accepts a proposal digest recorded by 0.12.0 (the legacy value)
or the manifest-aware one. A report file the tool wrote and listed in
`.opencomplai/written-files.json` keeps the proposal current until its content
changes. Everything is offline and runs under tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli import main, proposal_gate
from opencomplai_cli.inputs import load_manifest
from opencomplai_cli.main import app
from opencomplai_core.classification_proposal import (
    PROPOSAL_FILENAME,
    WRITTEN_FILES_MANIFEST,
    build_proposal_document,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.signing import generate_keypair
from opencomplai_core.written_files import record_written_file
from typer.testing import CliRunner

runner = CliRunner()
PURPOSE = "customer support chatbot"
JUNIT = "<testsuite tests='1'/>\n"


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch) -> None:
    """Own cwd, state dir and HOME; no signing key or API anywhere."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "SIGNING_KEY_PRIVATE",
        "OPENCOMPLAI_TRUSTED_KEY_IDS",
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        monkeypatch.delenv(var, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home / "missing")
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "missing" / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "missing" / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "missing" / "signing.pub")


def _manifest(tmp_path: Path, purpose: str = PURPOSE) -> Path:
    path = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "prop-sys",
            "--intended-purpose",
            purpose,
            "--output",
            str(path),
        ],
    )
    assert result.exit_code == 0, result.output
    return path


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('hello')\n", encoding="utf-8")
    return repo


def _tree(repo: Path) -> str:
    """The code digest `scan --propose` would store for this tree."""
    return run_scan("prop-sys", "HEAD", repo, PURPOSE).source_tree_sha256


def _write_proposal(
    repo: Path, manifest_path: Path, area: int = 4, tree: str | None = None
) -> Path:
    manifest = load_manifest(manifest_path)
    doc = build_proposal_document(
        system_id=manifest.system_id,
        commit_ref="HEAD",
        scanner_version="0.0.0",
        scan_input_digest="sha256:" + "ab" * 32,
        scan_report_hash="sha256:" + "cd" * 32,
        manifest_fingerprint=fingerprint_manifest(manifest),
        declared_purpose=manifest.intended_purpose,
        area="employment",
        confidence="medium",
        evidence=[{"location": "src/a.py:5", "file": "src/a.py", "line": 5}],
        minority_evidence=[],
        prohibited_signals=[],
        proposal={"proposed_annex_iii_area": area, "proposed_area_name": "employment"},
        scan_tree_sha256=tree,
    )
    path = repo / PROPOSAL_FILENAME
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _confirm(tmp_path: Path, repo: Path, manifest_path: Path, proposal: Path) -> None:
    """Confirm with the real `accept --proposal --yes`; never a hand-built record."""
    generate_keypair(tmp_path / "keys")
    result = runner.invoke(
        app,
        [
            "accept",
            "--manifest",
            str(manifest_path),
            "--accepted-by",
            "dpo@example.test",
            "--repo-root",
            str(repo),
            "--proposal",
            str(proposal),
            "--yes",
            "--key",
            str(tmp_path / "keys" / "signing.key"),
        ],
    )
    assert result.exit_code == 0, result.output


def _confirmed(
    tmp_path: Path,
    repo: Path,
    manifest_path: Path,
    area: int = 4,
    tree: str | None = None,
) -> Path:
    proposal = _write_proposal(repo, manifest_path, area, tree)
    _confirm(tmp_path, repo, manifest_path, proposal)
    return proposal


def _invoke_check(
    tmp_path: Path, manifest_path: Path, repo: Path, *extra: str, out: str = "out"
):
    return runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--output-dir",
            str(tmp_path / out),
            *extra,
        ],
    )


def _check(
    tmp_path: Path, manifest_path: Path, repo: Path, *extra: str, out: str = "out"
) -> tuple[int, dict, Path]:
    out_dir = tmp_path / out
    result = _invoke_check(tmp_path, manifest_path, repo, *extra, out=out)
    assert result.exit_code in (0, 1), result.output
    artifact = json.loads(
        (out_dir / "compliance-artifact.json").read_text(encoding="utf-8")
    )
    return result.exit_code, artifact, out_dir


def _status(artifact_dir: Path) -> str:
    sidecar = json.loads((artifact_dir / "scan-report.json").read_text("utf-8"))
    return sidecar["proposal_status"]


def _junit(repo: Path, text: str = JUNIT) -> Path:
    path = repo / "junit.xml"
    path.write_text(text, encoding="utf-8")
    return path


def _check_status(
    tmp_path: Path, manifest: Path, repo: Path, out: str
) -> tuple[int, str]:
    code, _, out_dir = _check(
        tmp_path, manifest, repo, "--scan", "--fail-on", "major", out=out
    )
    return code, _status(out_dir)


def test_legacy_digest_proposal_still_confirms(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    junit = _junit(repo)
    legacy = _tree(repo)  # no manifest yet: the 0.12.0 value
    _confirmed(tmp_path, repo, manifest, tree=legacy)
    record_written_file(repo, junit)
    code, status = _check_status(tmp_path, manifest, repo, "a")
    assert status == "confirmed"
    assert code == 1


def test_recorded_report_file_does_not_stale_confirmed_proposal(
    tmp_path: Path,
) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest, tree=_tree(repo))
    junit = _junit(repo)
    # Control: the same file, not recorded, stales the proposal as in 0.12.0.
    code, status = _check_status(tmp_path, manifest, repo, "a")
    assert (code, status) == (0, "stale")
    record_written_file(repo, junit)
    code, status = _check_status(tmp_path, manifest, repo, "b")
    assert (code, status) == (1, "confirmed")


def test_listed_report_file_edited_makes_proposal_stale(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest, tree=_tree(repo))
    junit = _junit(repo)
    record_written_file(repo, junit)
    assert _check_status(tmp_path, manifest, repo, "a") == (1, "confirmed")
    _junit(repo, "<testsuite failures='3'/>\n")
    assert _check_status(tmp_path, manifest, repo, "b") == (0, "stale")


def test_corrupt_manifest_behaves_like_0_12_0(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest, tree=_tree(repo))
    _junit(repo)
    path = repo / WRITTEN_FILES_MANIFEST
    path.parent.mkdir(exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert _check_status(tmp_path, manifest, repo, "a") == (0, "stale")


def test_gate_accepts_either_digest_directly(tmp_path: Path) -> None:
    manifest_path, repo = _manifest(tmp_path), _repo(tmp_path)
    manifest = load_manifest(manifest_path)
    aware, legacy, other = "a" * 64, "b" * 64, "c" * 64
    _confirmed(tmp_path, repo, manifest_path, tree=legacy)
    status = proposal_gate.proposal_status
    assert status(manifest, repo, aware, legacy_tree_sha256=legacy) == "confirmed"
    assert status(manifest, repo, aware) == "stale"  # 0.12.0 behaviour
    assert status(manifest, repo, other, legacy_tree_sha256=aware) == "stale"
    _confirmed(tmp_path, repo, manifest_path, tree=aware)
    assert status(manifest, repo, aware, legacy_tree_sha256=legacy) == "confirmed"
    assert status(manifest, repo, aware) == "confirmed"
    assert status(manifest, repo, other, legacy_tree_sha256=legacy) == "stale"
    area = proposal_gate.confirmed_proposal_area(
        manifest, repo, other, legacy_tree_sha256=aware
    )
    assert area == 4
