"""Guards that the test suite stays green in the projected public tree."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[2]


def test_workflow_reading_tests_skip_in_public_shaped_tree(tmp_path: Path) -> None:
    tests = tmp_path / "packages" / "cli" / "tests"
    tests.mkdir(parents=True)
    for name in ("test_install_scripts.py", "test_precommit_hooks_pin.py"):
        shutil.copy(_HERE / name, tests / name)
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for name in ("ci.yml", "actionlint.yml", "dco.yml"):
        (workflows / name).write_text("name: x\n", encoding="utf-8")
    ids = [
        "packages/cli/tests/test_install_scripts.py"
        "::test_install_workflow_runs_both_os_and_version",
        "packages/cli/tests/test_install_scripts.py"
        "::test_install_workflow_lints_both_scripts",
        "packages/cli/tests/test_precommit_hooks_pin.py"
        "::test_try_repo_workflow_runs_try_repo",
    ]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider",
            "--rootdir", str(tmp_path), *ids,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:]
    assert "3 skipped" in proc.stdout, proc.stdout[-3000:]


def test_public_ci_pytest_command_collects_without_errors() -> None:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", "packages/core", "packages/cli",
            "packages/sdk-python", "--collect-only", "-q", "-p", "no:cacheprovider",
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stdout[-3000:]
