"""Structure and behaviour guards for scripts/install.sh and scripts/install.ps1."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SH = _REPO_ROOT / "scripts" / "install.sh"
_PS1 = _REPO_ROOT / "scripts" / "install.ps1"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "install-scripts.yml"
_DOC = _REPO_ROOT / "docs" / "src" / "getting-started" / "installation.md"

_needs_workflow = pytest.mark.skipif(
    not _WORKFLOW.is_file(),
    reason="install-scripts.yml is not projected to the public tree",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code(path: Path) -> str:
    """Script text without comments, so needles cannot match header docs."""
    text = re.sub(r"<#.*?#>", "", _text(path), flags=re.S)
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def test_install_sh_wraps_uv_with_python_floor() -> None:
    text = _code(_SH)
    assert "set -euo pipefail" in text
    assert re.search(r'^PY="\$\{OPENCOMPLAI_PYTHON:-3\.11\}"', text, re.M)
    assert re.search(r'^ARGS=\(--python "\$PY"', text, re.M)
    assert re.search(r'^uv tool install "\$\{ARGS\[@\]\}"', text, re.M)
    assert re.search(r"^\s*--install-uv\)", text, re.M)
    assert "sudo" not in text
    assert "| sh" not in text
    assert "| bash" not in text


def test_install_sh_fails_clearly_without_uv(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    proc = subprocess.run(
        [bash, str(_SH)],
        env={"PATH": str(tmp_path), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "uv" in proc.stdout + proc.stderr


def test_install_ps1_wraps_uv_with_python_floor() -> None:
    text = _code(_PS1)
    assert "$ErrorActionPreference = 'Stop'" in text
    assert "else { '3.11' }" in text
    assert re.search(
        r"^\$toolArgs = @\('tool', 'install', '--python', \$Python", text, re.M
    )
    assert re.search(r"^& uv @toolArgs", text, re.M)
    assert re.search(r"\[switch\]\$InstallUv", text)
    assert "Invoke-Expression" not in text
    assert "iex" not in text.lower().split()


@_needs_workflow
def test_install_workflow_runs_both_os_and_version() -> None:
    text = _text(_WORKFLOW)
    for needle in (
        "ubuntu-22.04",
        "windows-latest",
        "scripts/install.sh",
        "scripts/install.ps1",
        "opencomplai --version",
    ):
        assert needle in text, needle


@_needs_workflow
def test_install_workflow_lints_both_scripts() -> None:
    jobs = yaml.safe_load(_text(_WORKFLOW))["jobs"]
    steps = [
        (j["runs-on"], s.get("run", "")) for j in jobs.values() for s in j["steps"]
    ]
    assert any("shellcheck scripts/install.sh" in run for _, run in steps)
    assert any(
        runner == "windows-latest"
        and "Invoke-ScriptAnalyzer" in run
        and "scripts/install.ps1" in run
        and "exit 1" in run
        for runner, run in steps
    )


def test_install_sh_parses_with_bash_n() -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    proc = subprocess.run(
        [bash, "-n", str(_SH)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr


def test_install_ps1_parses_with_powershell_parser() -> None:
    ps = shutil.which("powershell.exe") or shutil.which("pwsh")
    if ps is None:
        pytest.skip("PowerShell not available")
    cmd = (
        "$e=$null; [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{_PS1}',[ref]$null,[ref]$e) | Out-Null; if($e){{$e; exit 1}}"
    )
    proc = subprocess.run(
        [ps, "-NoProfile", "-Command", cmd], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not proc.stderr.strip()


def test_installation_doc_describes_install_scripts() -> None:
    text = _text(_DOC)
    for needle in ("install.sh", "install.ps1", "OPENCOMPLAI_PYTHON", "3.11"):
        assert needle in text, needle
