"""Report files written into the scanned folder keep a confirmed proposal confirmed.

`check` (--report-junit, --sarif-output, --summary-md, --output-dir) and `scan`
(--output-file, --sarif-output) write report files into the scanned tree. Each
one is recorded in `.opencomplai/written-files.json`, so the scan digest drops it
while its content is unchanged and the confirmed classification stays confirmed.
Every case runs the real commands under tmp_path.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_cli.inputs import load_manifest
from opencomplai_cli.main import app
from opencomplai_cli.provenance import record_written_files
from opencomplai_core.classification_proposal import (
    PROPOSAL_FILENAME,
    build_proposal_document,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.scan_engine import run_scan
from opencomplai_core.signing import generate_keypair
from opencomplai_core.written_files import load_written_files
from typer.testing import CliRunner

runner = CliRunner()
PURPOSE = "customer support chatbot"
ROW = "confirmed_proposal:employment"
_CHECK = ("--scan", "--fail-on", "major")
_SCREEN = (
    "from sklearn.ensemble import RandomForestClassifier\n\n\n"
    "def screen(applicants):\n"
    "    ranked = rank_candidates(applicants)\n"
    "    return ranked\n"
)
_SCAN_COMMON = (
    "--ai-model",
    "codebert-onnx",
    "--no-emit-evidence",
    "--no-ocignore-bootstrap",
)


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


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "prop-sys",
            "--intended-purpose",
            PURPOSE,
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


def _employment_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    for name in ("a", "b", "c"):
        (repo / "src" / f"{name}.py").write_text(_SCREEN, encoding="utf-8")
    return repo


def _tree(repo: Path) -> str:
    """The code digest `scan --propose` would store for this tree."""
    return run_scan("prop-sys", "HEAD", repo, PURPOSE).source_tree_sha256


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


def _confirmed(tmp_path: Path, repo: Path, manifest_path: Path) -> None:
    """A confirmed employment proposal pinned to the tree as it is now."""
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
        proposal={"proposed_annex_iii_area": 4, "proposed_area_name": "employment"},
        scan_tree_sha256=_tree(repo),
    )
    proposal = repo / PROPOSAL_FILENAME
    proposal.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    _confirm(tmp_path, repo, manifest_path, proposal)


def _check(
    tmp_path: Path, manifest_path: Path, repo: Path, *extra: str, out: str = "out"
) -> tuple[int, dict, str | None]:
    """Run `check --scan --fail-on major`; return (exit code, artifact, status)."""
    out_dir = tmp_path / out  # absolute `out` wins
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--output-dir",
            str(out_dir),
            *_CHECK,
            *extra,
        ],
    )
    assert result.exit_code in (0, 1), result.output
    artifact = json.loads(
        (out_dir / "compliance-artifact.json").read_text(encoding="utf-8")
    )
    sidecar = json.loads((out_dir / "scan-report.json").read_text(encoding="utf-8"))
    return result.exit_code, artifact, sidecar.get("proposal_status")


def _scan(tmp_path: Path, manifest_path: Path, repo: Path, *extra: str):
    result = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            *_SCAN_COMMON,
            *extra,
        ],
    )
    assert result.exit_code == 0, result.output
    return result


@pytest.mark.parametrize(
    ("flag", "name"),
    [
        ("--report-junit", "r.xml"),
        ("--sarif-output", "r.sarif"),
        ("--summary-md", "r.md"),
        ("--output-dir", "oc-out"),  # excluded by name already: regression guard
    ],
)
def test_check_writers_keep_confirmed(tmp_path: Path, flag: str, name: str) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest)
    target = repo / name
    if flag == "--output-dir":
        extra, out = (), str(target)
    else:
        extra, out = (flag, str(target)), "out"
    for _ in range(3):
        code, artifact, status = _check(tmp_path, manifest, repo, *extra, out=out)
        assert ROW in artifact["scan_summary"]["discrepancies"]
        assert code == 1
        assert status == "confirmed"
    assert target.exists()


@pytest.mark.parametrize(
    ("flag", "name"),
    [
        ("--output-file", "scan.json"),
        ("--output-file", "scan.md"),
        ("--sarif-output", "scan.sarif"),
    ],
)
def test_scan_writers_keep_confirmed(tmp_path: Path, flag: str, name: str) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest)
    target = repo / name
    for _ in range(2):
        _scan(tmp_path, manifest, repo, flag, str(target))
        assert target.exists()
    code, artifact, status = _check(tmp_path, manifest, repo)
    assert ROW in artifact["scan_summary"]["discrepancies"]
    assert code == 1
    assert status == "confirmed"


def test_scan_propose_output_file_confirms(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _employment_repo(tmp_path)
    report = repo / "scan.json"
    for _ in range(2):
        _scan(tmp_path, manifest, repo, "--propose", "--output-file", str(report))
    assert report.exists()
    _confirm(tmp_path, repo, manifest, repo / PROPOSAL_FILENAME)
    code, artifact, status = _check(tmp_path, manifest, repo)
    assert ROW in artifact["scan_summary"]["discrepancies"]
    assert code == 1
    assert status == "confirmed"


def test_edited_report_makes_it_stale(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest)
    junit = repo / "r.xml"
    for _ in range(2):
        _, _, status = _check(tmp_path, manifest, repo, "--report-junit", str(junit))
        assert status == "confirmed"
    with junit.open("a", encoding="utf-8") as fh:
        fh.write("<!-- edited by hand -->\n")
    code, artifact, status = _check(tmp_path, manifest, repo, out="after")
    assert status == "stale"
    assert ROW not in artifact["scan_summary"]["discrepancies"]
    assert code == 0  # a stale proposal never changes a verdict (E-6)


def test_proposal_made_before_the_report_still_confirms(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest)  # no report in the tree yet
    junit = repo / "r.xml"
    _check(tmp_path, manifest, repo, "--report-junit", str(junit))
    assert junit.exists()
    code, artifact, status = _check(tmp_path, manifest, repo, out="later")
    assert ROW in artifact["scan_summary"]["discrepancies"]
    assert code == 1
    assert status == "confirmed"


def test_record_helper_skips_and_never_raises(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    inside = repo / "r.xml"
    inside.write_text("<testsuite/>\n", encoding="utf-8")
    outside = tmp_path / "outside.xml"
    outside.write_text("<testsuite/>\n", encoding="utf-8")

    record_written_files(repo, None, repo / "missing.xml", outside)
    assert load_written_files(repo) == {}
    assert not (repo / ".opencomplai").exists()

    record_written_files(repo, inside)
    assert list(load_written_files(repo)) == ["r.xml"]

    def _boom(root: Path, file: Path) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("opencomplai_core.written_files.record_written_file", _boom)
    record_written_files(repo, inside, outside)  # swallowed, no exception


def _git(path: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=path, check=True, capture_output=True,
    )  # fmt: skip


@pytest.mark.skipif(shutil.which("git") is None, reason="git not on PATH")
def test_plain_check_leaves_no_manifest_and_tree_stays_clean(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    (repo / ".gitignore").write_text("oc-out/\n", encoding="utf-8")
    _git(repo, "init", "-q")
    (repo / ".ocignore").write_text("# none\n", encoding="utf-8")  # no bootstrap
    _git(repo, "add", "--", "app.py", ".gitignore", ".ocignore")
    _git(repo, "commit", "-q", "-m", "init")
    for _ in range(2):
        _, artifact, _ = _check(tmp_path, manifest, repo, out=str(repo / "oc-out"))
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
        ).stdout
        assert artifact["tree_dirty"] is False, status
        assert not (repo / ".opencomplai" / "written-files.json").exists()


def test_report_flag_records_only_the_report(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _check(tmp_path, manifest, repo, "--report-junit", str(repo / "r.xml"))
    assert list(load_written_files(repo)) == ["r.xml"]
