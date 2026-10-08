"""Tests for the enterprise-to-public sync gate (scripts/verify-oss.sh).

The sync tooling is private-repo only, so these skip in the public projection.
Forbidden literals are built at runtime so this file passes its own gate.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VERIFY = ROOT / "scripts" / "verify-oss.sh"
CONFIG = ROOT / "scripts" / "oss-config.sh"

pytestmark = pytest.mark.skipif(
    not VERIFY.exists(), reason="sync tooling is private-repo only"
)
needs_gitleaks = pytest.mark.skipif(
    shutil.which("gitleaks") is None, reason="gitleaks not installed"
)

BASH = shutil.which("bash") or "bash"
CHECKER = "packages/cli/src/opencomplai_cli/data/checker-local.html"
# Shape gitleaks actually flags in the real file (line 154): a questionnaire
# field id after the word "key:".
CHECKER_LINE = (
    "{ke" + 'y:"e2_' + 'modifications",label:"Do you (or a"}\n'
)  # runtime-built


def _verify(tree: Path, path: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        [BASH, VERIFY.as_posix(), tree.as_posix()],
        capture_output=True,
        text=True,
        env=env,
    )


def _tree(root: Path) -> Path:
    out = root / "out"
    out.mkdir()
    (out / "README.md").write_text("hello\n")
    return out


@needs_gitleaks
def test_clean_tree_passes_with_scanner(tmp_path):
    r = _verify(_tree(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


@needs_gitleaks
def test_planted_secret_fails(tmp_path):
    out = _tree(tmp_path)
    key = "AKIA" + "QYLPMN5HHHFPZAM2"
    (out / "leak.py").write_text(f'aws_access_key_id = "{key}"\n')
    r = _verify(out)
    assert r.returncode != 0
    assert "gitleaks found secrets" in r.stderr


def test_planted_plan_file_fails(tmp_path):
    for rel in ("PLAN/x.md", "docs/PLAN/x.md"):
        base = tmp_path / rel.replace("/", "_")
        base.mkdir()
        out = _tree(base)
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        (out / rel).write_text("x\n")
        r = _verify(out)
        assert r.returncode != 0, rel
        assert "PLAN" in r.stderr, rel


def test_planted_ledger_name_fails(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    out = _tree(a)
    (out / "HANDOFF.md").write_text("x\n")
    r = _verify(out)
    assert r.returncode != 0
    assert "HANDOFF.md" in r.stderr

    b = tmp_path / "b"
    b.mkdir()
    out = _tree(b)
    (out / "notes.md").write_text("see logs/" + "autonomous" + "-exec/x\n")
    r = _verify(out)
    assert r.returncode != 0
    assert "notes.md" in r.stderr


def test_no_scanner_fails(tmp_path):
    usr_bin = str(Path(BASH).parent)
    # the only PATH entry is the shell's own bin dir; gitleaks must not live there
    assert not (Path(usr_bin) / "gitleaks").exists()
    assert not (Path(usr_bin) / "gitleaks.exe").exists()
    assert not (Path(usr_bin) / "trufflehog").exists()
    r = _verify(_tree(tmp_path), path=usr_bin)
    assert r.returncode != 0
    assert "no secret scanner" in r.stderr


@needs_gitleaks
def test_checker_version_allowlisted_any_checkout_path(tmp_path):
    for name in ("one", "two"):
        base = tmp_path / name
        base.mkdir()
        out = _tree(base)
        f = out / CHECKER
        f.parent.mkdir(parents=True)
        f.write_text(CHECKER_LINE)
        r = _verify(out)
        assert r.returncode == 0, r.stdout + r.stderr

    base = tmp_path / "elsewhere"
    base.mkdir()
    out = _tree(base)
    (out / "other.html").write_text(CHECKER_LINE)
    r = _verify(out)
    assert r.returncode != 0


def test_docs_update_plan_stripped_by_denylist():
    for p in ("DOCS-UPDATE-PLAN.md", "scripts/gitleaks.toml", ".gitleaksignore"):
        r = subprocess.run(
            [BASH, "-c", f'source "{CONFIG.as_posix()}"; oss_is_private "{p}"'],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, p


def test_unrated_security_pages_stay_private(tmp_path):
    def private(p: str) -> int:
        return subprocess.run(
            [BASH, "-c", f'source "{CONFIG.as_posix()}"; oss_is_private "{p}"'],
            capture_output=True,
            text=True,
        ).returncode

    assert private("docs/security/risk-register.md") == 0
    assert private("docs/security/vulnerability-management.md") == 0
    assert private("docs/security/ai-inventory.md") == 1

    out = _tree(tmp_path)
    page = out / "docs" / "security" / "risk-register.md"
    page.parent.mkdir(parents=True)
    page.write_text("# Risk register\n")
    r = _verify(out)
    assert r.returncode != 0
    assert "private file found in output: docs/security/risk-register.md" in r.stderr
