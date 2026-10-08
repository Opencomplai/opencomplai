"""Guards on the enterprise CI: pinned actions, permissions, locked installs, governance files.

Line-based regex only. The module skips in the public tree, whose own
``.github/`` differs and which has no ``scripts/gitleaks.toml`` (private,
stripped by the projection). The DCO behaviour tests run the workflow step's own
shell text over a throwaway git repo; a missing ``bash`` or ``git`` fails them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[3]
_WORKFLOWS = _REPO / ".github" / "workflows"

if not (_REPO / "scripts" / "gitleaks.toml").is_file():
    pytest.skip(
        "enterprise-only CI guard (public tree has no scripts/gitleaks.toml)",
        allow_module_level=True,
    )

_FILES = sorted(_WORKFLOWS.glob("*.yml"))
_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)(.*)$")


def _lines(path: Path) -> list[tuple[int, str]]:
    return list(enumerate(path.read_text(encoding="utf-8").splitlines(), start=1))


def test_all_actions_pinned_to_full_sha() -> None:
    bad = []
    for f in _FILES:
        for n, line in _lines(f):
            m = _USES.match(line)
            if not m:
                continue
            ref, rest = m.groups()
            if ref.startswith(("./", "docker://")):
                continue
            if not re.search(r"@[0-9a-f]{40}$", ref) or not rest.strip().startswith(
                "# "
            ):
                bad.append(f"{f.name}:{n}: {line.strip()}")
    assert not bad, (
        "actions must be pinned to a 40-hex SHA with a trailing '# tag' comment:\n"
        + "\n".join(bad)
    )


def test_every_workflow_declares_permissions() -> None:
    missing = [
        f.name
        for f in _FILES
        if not re.search(r"^permissions:", f.read_text(encoding="utf-8"), re.M)
    ]
    assert not missing, f"no top-level permissions: in {missing}"


def test_no_write_all_permissions() -> None:
    bad = [
        f"{f.name}:{n}"
        for f in _FILES
        for n, line in _lines(f)
        if re.match(r"^\s*permissions:\s*write-all", line)
    ]
    assert not bad, f"write-all permissions at {bad}"


def test_actionlint_config_has_no_ignores() -> None:
    text = (_REPO / ".github" / "actionlint.yaml").read_text(encoding="utf-8")
    code = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    assert not [ln for ln in code if re.match(r"\s*(ignore|paths):", ln)], (
        "actionlint config must carry no ignores"
    )


def test_uv_sync_is_locked() -> None:
    bad = [
        f"{f.name}:{n}"
        for f in _FILES
        for n, line in _lines(f)
        if re.search(r"\buv sync\b", line) and "--locked" not in line
    ]
    assert not bad, f"uv sync without --locked at {bad}"


def test_codeowners_default_rule() -> None:
    rules = [
        ln.split()
        for ln in (_REPO / ".github" / "CODEOWNERS")
        .read_text(encoding="utf-8")
        .splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    assert any(r[0] == "*" and len(r) > 1 and r[1].startswith("@") for r in rules), (
        "no '* @owner' default rule"
    )


def test_dco_and_secret_scan_workflows_exist() -> None:
    for name in ("dco.yml", "secret-scan.yml"):
        path = _WORKFLOWS / name
        assert path.is_file(), f"{name} is missing"
        for n, line in _lines(path):
            m = _USES.match(line)
            assert not m or m.group(1).startswith("actions/checkout@"), (
                f"{name}:{n} uses a third-party action"
            )
    scan = (_WORKFLOWS / "secret-scan.yml").read_text(encoding="utf-8")
    assert "--config scripts/gitleaks.toml" in scan
    assert "--gitleaks-ignore-path" not in scan


def test_public_allowlist_ships_governance_files() -> None:
    text = (_REPO / "scripts" / "oss-config.sh").read_text(encoding="utf-8")
    for p in (".github/CODEOWNERS", ".github/workflows/dco.yml"):
        assert f'"{p}"' in text, f"{p} not in PUBLIC_GITHUB_ALLOWLIST"


# --- DCO script behaviour ----------------------------------------------------


def _dco_run_text() -> str:
    wf = yaml.safe_load((_WORKFLOWS / "dco.yml").read_text(encoding="utf-8"))
    steps = [
        s for job in wf["jobs"].values() for s in job["steps"] if s.get("id") == "dco"
    ]
    assert len(steps) == 1
    return steps[0]["run"]


def _git(repo: Path, env: dict[str, str], *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def dco_repo(tmp_path: Path):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": str(cfg),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Dev One",
        "GIT_AUTHOR_EMAIL": "dev@example.test",
        "GIT_COMMITTER_NAME": "Dev One",
        "GIT_COMMITTER_EMAIL": "dev@example.test",
    }
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, env, "init", "-q")

    def commit(message: str) -> str:
        _git(repo, env, "commit", "-q", "--allow-empty", "-m", message)
        return _git(repo, env, "rev-parse", "HEAD")

    base = commit("base")
    signed = commit("signed change\n\nSigned-off-by: Dev One <dev@example.test>")
    unsigned = commit("unsigned change")
    # Resolve bash from PATH: on Windows a bare "bash" makes CreateProcess pick System32's WSL bash first.
    bash = shutil.which("bash")
    assert bash, "bash not found on PATH"
    script = tmp_path / "dco.sh"
    script.write_bytes(_dco_run_text().replace("\r\n", "\n").encode("utf-8"))

    def run(base_sha: str, head_sha: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [bash, "--noprofile", "--norc", "-eo", "pipefail", script.as_posix()],
            cwd=repo,
            env={**env, "BASE_SHA": base_sha, "HEAD_SHA": head_sha},
            capture_output=True,
            text=True,
        )

    return (
        run,
        base,
        signed,
        unsigned,
        lambda sha: _git(repo, env, "rev-parse", "--short", sha),
    )


def test_dco_script_passes_signed_off_commit(dco_repo) -> None:
    run, base, signed, _unsigned, _short = dco_repo
    done = run(base, signed)
    assert done.returncode == 0, done.stdout + done.stderr


def test_dco_script_flags_unsigned_commit(dco_repo) -> None:
    run, _base, signed, unsigned, short = dco_repo
    done = run(signed, unsigned)
    assert done.returncode == 1, done.stdout + done.stderr
    assert short(unsigned) in done.stdout + done.stderr


# --- ci-python.yml mypy gate + coverage report -------------------------------


def _python_checks_steps() -> list[dict]:
    wf = yaml.safe_load((_WORKFLOWS / "ci-python.yml").read_text(encoding="utf-8"))
    return wf["jobs"]["python-checks"]["steps"]


def test_ci_python_defines_mypy_gate_and_coverage_steps() -> None:
    steps = _python_checks_steps()
    names = [s.get("name") for s in steps]
    after = names.index("Test / sdk-python")
    by_name = {s["name"]: s for s in steps if "name" in s}

    gate = by_name["Types / mypy baseline gate"]
    cov = by_name["Coverage / core + sdk (report only)"]
    assert names.index(gate["name"]) > after
    assert names.index(cov["name"]) > after
    for step in (gate, cov):
        assert step.get("if") == "${{ !cancelled() }}", step["name"]

    assert "mypy_gate.py --check" in gate["run"]
    baseline = json.loads(
        (_REPO / "tools" / "mypy-gate" / "baseline.json").read_text(encoding="utf-8")
    )
    assert f"--with mypy=={baseline['mypy_version']}" in gate["run"], (
        "CI must pin the mypy version the baseline was recorded with"
    )
    assert "--cov-report" in cov["run"]
    assert "--cov-fail-under" not in cov["run"]
