"""Tests for the enterprise-to-public sync gate (scripts/verify-oss.sh).

The sync tooling is private-repo only, so these skip in the public projection.
Forbidden literals are built at runtime so this file passes its own gate.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
VERIFY = ROOT / "scripts" / "verify-oss.sh"
CONFIG = ROOT / "scripts" / "oss-config.sh"
ALLOWLIST = ROOT / "scripts" / "oss-public-path-allowlist.txt"

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


def _private(p: str) -> int:
    return subprocess.run(
        [BASH, "-c", f'source "{CONFIG.as_posix()}"; oss_is_private "{p}"'],
        capture_output=True,
        text=True,
    ).returncode


def test_oss_is_private_allowlisted_github_is_public():
    for p in (
        ".github/CODEOWNERS",
        ".github/ISSUE_TEMPLATE/bug-report.yml",
        ".github/pull_request_template.md",
        ".github/workflows/dco.yml",
    ):
        assert _private(p) == 1, p


def test_oss_is_private_unlisted_github_stays_private():
    assert _private(".github/workflows/internal-only.yml") == 0
    assert _private(".github/dependabot.yml") == 0


def test_oss_is_private_overlay_maps_to_dot_github():
    assert _private("oss-public/.github/workflows/actionlint.yml") == 1
    assert _private("oss-public/README.md") == 0


def test_oss_is_private_dashboard_saas_stays_private():
    assert _private("dashboard-saas/x") == 0


def test_oss_is_private_held_back_workflows_stay_private():
    for p in (
        ".github/workflows/ci.yml",
        "oss-public/.github/workflows/ci.yml",
        ".github/workflows/dashboard-saas-ci.yml",
    ):
        assert _private(p) == 0, p


@pytest.mark.parametrize("manifest", ["pnpm-lock.yaml", "package-lock.json"])
def test_private_path_in_build_manifest_fails(tmp_path, manifest):
    # The stderr assertions are the proof: on a host without a secret scanner
    # verify-oss.sh fails for that reason too, so returncode alone is vacuous.
    private = "dashboard" + "-saas/"  # runtime-built so this file passes its own gate
    bad = tmp_path / "bad"
    bad.mkdir()
    out = _tree(bad)
    (out / manifest).write_text(f"link: {private}app\n")
    r = _verify(out)
    assert r.returncode != 0
    assert "referenced in build manifest" in r.stderr
    assert manifest in r.stderr

    good = tmp_path / "good"
    good.mkdir()
    out = _tree(good)
    (out / manifest).write_text("link: packages/cli\n")
    r = _verify(out)
    assert "referenced in build manifest" not in r.stderr


# Runtime-built so the gate's own tests do not rely on being allowlisted for these.
PRIV_TEXT = "dashboard" + "-saas/"
PLAN_TEXT = "PLA" + "N/"
ALLOWLISTED = "packages/cli/tests/test_publish.py"


def _out(root: Path, name: str, files: dict[str, str]) -> Path:
    base = root / name
    base.mkdir()
    out = _tree(base)
    for rel, text in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    return out


@pytest.mark.parametrize("text", [PRIV_TEXT + "services/web", PLAN_TEXT + "x.md"])
def test_private_path_text_fails(tmp_path, text):
    r = _verify(_out(tmp_path, "t", {"notes.md": f"see {text}\n"}))
    assert r.returncode != 0
    assert "private path text" in r.stderr
    assert "in: notes.md" in r.stderr


def test_private_path_text_in_allowlisted_file_passes(tmp_path):
    text = f"see {PRIV_TEXT}x and {PLAN_TEXT}y\n"
    r = _verify(_out(tmp_path, "t", {ALLOWLISTED: text}))
    assert "private path text" not in r.stderr


def test_plan_text_needs_a_non_name_character_before_it(tmp_path):
    near = "DOCS-UPDATE-" + PLAN_TEXT + "x"
    r = _verify(_out(tmp_path, "near", {"notes.md": f"see {near}\n"}))
    assert "private path text" not in r.stderr
    for i, before in enumerate(("", "(", " ", "docs/")):
        out = _out(tmp_path, f"hit{i}", {"n.md": f"{before}{PLAN_TEXT}x\n"})
        r = _verify(out)
        assert "private path text" in r.stderr, repr(before)


def test_missing_allowlist_fails(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("verify-oss.sh", "oss-config.sh", "gitleaks.toml"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    r = subprocess.run(
        [BASH, (scripts / "verify-oss.sh").as_posix(), _tree(tmp_path).as_posix()],
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
    assert "allowlist missing" in r.stderr


def _scripts_copy(root: Path, allowlist: str | None, setting: str | None = None):
    scripts = root / "scripts"
    scripts.mkdir()
    for name in ("verify-oss.sh", "oss-config.sh", "gitleaks.toml"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    if setting is not None:
        config = scripts / "oss-config.sh"
        config.write_text(
            config.read_text().replace(
                'PUBLIC_PATH_ALLOWLIST="oss-public-path-allowlist.txt"',
                f'PUBLIC_PATH_ALLOWLIST="{setting}"',
            )
        )
    if allowlist is not None:
        (scripts / "oss-public-path-allowlist.txt").write_text(allowlist)
    return scripts


def _run_copy(scripts: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, (scripts / "verify-oss.sh").as_posix(), out.as_posix()],
        capture_output=True,
        text=True,
    )


def test_an_empty_allowlist_setting_prints_the_missing_allowlist_failure(tmp_path):
    scripts = _scripts_copy(tmp_path, allowlist=None, setting="")
    r = _run_copy(scripts, _tree(tmp_path))
    assert r.returncode != 0
    assert "allowlist missing" in r.stderr


def test_a_stale_allowlist_entry_is_warned_about(tmp_path):
    scripts = _scripts_copy(tmp_path, "docs/gone.md  # no longer there\n")
    r = _run_copy(scripts, _tree(tmp_path))
    assert "stale public-path allowlist entry (no hit): docs/gone.md" in r.stderr


def test_a_live_allowlist_entry_is_not_stale(tmp_path):
    scripts = _scripts_copy(tmp_path, "notes.md  # kept on purpose\n")
    out = _tree(tmp_path)
    (out / "notes.md").write_text(f"see {PRIV_TEXT}x\n")
    r = _run_copy(scripts, out)
    assert "stale" not in r.stderr
    assert "private path text" not in r.stderr


def test_a_utf16_text_file_cannot_pass_the_private_path_scan(tmp_path):
    out = _tree(tmp_path)
    (out / "notes.md").write_bytes(f"see {PRIV_TEXT}x\n".encode("utf-16"))
    r = _verify(out)
    assert r.returncode != 0
    assert "UTF-16 text file cannot be scanned" in r.stderr
    assert "notes.md" in r.stderr


def test_a_binary_looking_file_is_still_scanned(tmp_path):
    out = _tree(tmp_path)
    (out / "data.bin").write_bytes(b"\x00\x01" + f"see {PRIV_TEXT}x".encode() + b"\x00")
    r = _verify(out)
    assert "private path text" in r.stderr
    assert "in: data.bin" in r.stderr


def test_allowlist_and_handoff_scanner_test_are_private():
    assert _private("scripts/oss-public-path-allowlist.txt") == 0
    assert _private("packages/core/tests/test_handoff_flag_scanner.py") == 0


def test_every_allowlist_entry_exists_and_names_a_private_path():
    patterns = [
        re.compile(re.escape(PRIV_TEXT)),
        re.compile("(^|[^A-Za-z0-9_-])" + PLAN_TEXT, re.M),
    ]
    lines = [
        line
        for line in ALLOWLIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    for line in lines:
        assert re.fullmatch(r"\S+  # \S.*", line), f"needs '  # <reason>': {line!r}"
    entries = [line.split()[0] for line in lines]
    assert entries == sorted(entries)
    assert len(entries) == len(set(entries))
    for rel in entries:
        f = ROOT / rel
        assert f.is_file(), rel
        text = f.read_text(encoding="utf-8")
        assert any(p.search(text) for p in patterns), f"{rel}: no private path text"


def test_hermes_context_file_is_private():
    text = CONFIG.read_text(encoding="utf-8")
    block = text.split("PRIVATE_FILES=(", 1)[1].split("\n)", 1)[0]
    assert ".hermes.md" in block
