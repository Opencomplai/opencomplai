"""Pin the pre-commit hooks to the CLI version of their own revision (SU-116).

A consumer's ``rev:`` only controls behaviour if each hook installs the exact CLI
version of that tag. The pin is stamped at release time; these tests fail when a
release bump forgets it.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import opencomplai_cli
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOOKS = _REPO_ROOT / ".pre-commit-hooks.yaml"
_PYPROJECT = _REPO_ROOT / "packages" / "cli" / "pyproject.toml"
_JOURNEY = _REPO_ROOT / "docs" / "src" / "getting-started" / "deployment-journey.md"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "pre-commit-hooks.yml"
_STAMP = "Stamp opencomplai-cli==<version> into .pre-commit-hooks.yaml at release time."


def _version() -> str:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["version"]


def _pins() -> list[str]:
    text = _HOOKS.read_text(encoding="utf-8")
    return re.findall(r"^\s*additional_dependencies:\s*(.*?)\s*$", text, re.MULTILINE)


def test_every_hook_pins_cli_to_current_version() -> None:
    text = _HOOKS.read_text(encoding="utf-8")
    hook_count = len(re.findall(r"^- id:", text, re.MULTILINE))
    pins = _pins()
    assert hook_count >= 2, _STAMP
    assert len(pins) == hook_count, _STAMP
    expected = f'["opencomplai-cli=={_version()}"]'
    for pin in pins:
        assert pin == expected, f"{pin!r} != {expected!r}. {_STAMP}"


def test_hook_pin_matches_pyproject_and_journey_rev() -> None:
    version = _version()
    pin_versions = {re.search(r"==([^\"\]]+)", p).group(1) for p in _pins()}
    assert pin_versions == {version}, _STAMP
    assert opencomplai_cli.__version__ == version, _STAMP
    journey = _JOURNEY.read_text(encoding="utf-8")
    assert f"rev: v{version}" in journey, (
        f"deployment-journey.md rev is not v{version}. {_STAMP}"
    )


@pytest.mark.skipif(
    not _WORKFLOW.is_file(),
    reason="pre-commit-hooks.yml is not projected to the public tree",
)
def test_try_repo_workflow_runs_try_repo() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "pre-commit try-repo" in text
    assert "opencomplai-quick-scan" in text
    assert '".pre-commit-hooks.yaml"' in text, (
        "path filter must name .pre-commit-hooks.yaml"
    )
    assert "opencomplai-check" not in text, (
        "opencomplai-check needs a manifest; not a try-repo target"
    )
    assert text.count('"setup.py"') == 2, (
        "the pull_request and push path filters must both name setup.py"
    )


def _copy_repo_root(dst: Path) -> None:
    # Flat-layout discovery only looks at top-level names, so empty directories
    # reproduce the failure without copying the repo.
    dst.mkdir()
    for entry in _REPO_ROOT.iterdir():
        if entry.is_dir():
            if not entry.name.startswith("."):
                (dst / entry.name).mkdir()
        elif not entry.name.startswith(".env"):
            shutil.copy2(entry, dst / entry.name)


def _build_wheel(src: Path, out: Path) -> subprocess.CompletedProcess[str]:
    if importlib.util.find_spec("setuptools") is not None:
        cmd = [
            sys.executable,
            "-I",
            "-c",
            "import setuptools.build_meta as b, sys; "
            "print(b.__legacy__.build_wheel(sys.argv[1]))",
            str(out),
        ]
    else:
        uv = shutil.which("uv")
        assert uv, "neither setuptools nor uv is available to build the repo root"
        cmd = [uv, "build", "--wheel", "--out-dir", str(out), str(src)]
    return subprocess.run(
        cmd, cwd=src, capture_output=True, text=True, timeout=300, check=False
    )


def test_repo_root_builds_as_a_hook_repository(tmp_path: Path) -> None:
    src, out = tmp_path / "repo", tmp_path / "dist"
    _copy_repo_root(src)
    out.mkdir()
    proc = _build_wheel(src, out)
    assert proc.returncode == 0, proc.stderr[-800:]
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1, wheels
    assert wheels[0].name.startswith("opencomplai_pre_commit_hooks-"), wheels[0].name
    with zipfile.ZipFile(wheels[0]) as z:
        stray = [n for n in z.namelist() if ".dist-info/" not in n]
    assert not stray, stray


def test_hook_entries_are_cli_console_scripts() -> None:
    entries = re.findall(
        r"^\s*entry:\s*(\S+)", _HOOKS.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert len(entries) >= 2, entries
    scripts = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))["project"][
        "scripts"
    ]
    for entry in entries:
        assert entry in scripts, f"{entry!r} is not a console script of the CLI"
