"""Static and gated checks for the wheel and PyPI release smoke scripts."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import tempfile
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
LIB = SCRIPTS / "smoke_lib.sh"
WHEEL = SCRIPTS / "smoke_wheel_install.sh"
RELEASE = SCRIPTS / "smoke_pypi_release.sh"
BASH = shutil.which("bash")

needs_bash = pytest.mark.skipif(BASH is None, reason="needs bash")

WHEEL_STEPS = ["version", "init", "check", "verify"]
RELEASE_STEPS = [
    "install",
    "version",
    "init",
    "check",
    "verify",
    "propose",
    "accept",
    "check-scan",
    "export",
    "verify-export",
    "verify-tamper",
    "export-sign",
    "verify-package",
]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _network_reason() -> str | None:
    if not BASH:
        return "needs bash"
    if not shutil.which("uv"):
        return "needs uv"
    if not (shutil.which("python") or shutil.which("python3")):
        return "needs python"
    try:
        socket.create_connection(("pypi.org", 443), timeout=3).close()
    except OSError:
        return "needs network access to pypi.org"
    return None


def _live_gate() -> str | None:
    if os.environ.get("OPENCOMPLAI_RUN_WHEEL_SMOKE") != "1":
        return "OPENCOMPLAI_RUN_WHEEL_SMOKE not set"
    return _network_reason()


@needs_bash
def test_scripts_parse():
    for script in (LIB, WHEEL, RELEASE):
        r = subprocess.run([BASH, "-n", str(script)], capture_output=True, text=True)
        assert r.returncode == 0, f"{script.name}: {r.stderr}"


def test_wheel_smoke_names_its_steps():
    text = _text(WHEEL)
    assert "smoke_lib.sh" in text
    for name in WHEEL_STEPS:
        assert re.search(rf"smoke_\w+ {re.escape(name)}\b", text), name


def test_release_smoke_names_its_steps():
    text = _text(RELEASE)
    assert "smoke_lib.sh" in text
    for name in RELEASE_STEPS:
        assert re.search(rf"smoke_\w+ {re.escape(name)}\b", text), name


@needs_bash
def test_smoke_step_failure_names_the_step():
    def run(cmd: str):
        return subprocess.run(
            [
                BASH,
                "-c",
                f"set -euo pipefail; source '{LIB.as_posix()}'; smoke_step demo {cmd}",
            ],
            capture_output=True,
            text=True,
        )

    bad = run("false")
    assert bad.returncode != 0
    assert "step=demo" in bad.stderr
    assert run("true").returncode == 0


@needs_bash
@pytest.mark.parametrize("args", [[], ["not-a-version"]])
def test_release_smoke_rejects_bad_version(args):
    env = {**os.environ, "SMOKE_PIP_ARGS": "--index-url http://127.0.0.1:9/none"}
    r = subprocess.run(
        [BASH, str(RELEASE), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )
    assert r.returncode == 2
    assert "usage" in (r.stdout + r.stderr).lower()


def test_wheel_smoke_runs_against_local_wheels():
    reason = _live_gate()
    if reason:
        pytest.skip(reason)
    r = subprocess.run(
        [BASH, str(WHEEL)], capture_output=True, text=True, timeout=1800, cwd=ROOT
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "Wheel install smoke test passed." in r.stdout


def test_release_smoke_runs_against_local_wheels():
    """Builds the four wheels locally and installs them by path.

    The index still supplies third-party dependencies, so this needs network.
    """
    reason = _live_gate()
    if reason:
        pytest.skip(reason)
    version = tomllib.loads(
        (ROOT / "packages/sdk-python/pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    with tempfile.TemporaryDirectory() as dist:
        for pkg in ("core", "cli", "ai", "sdk-python"):
            subprocess.run(
                ["uv", "build", f"packages/{pkg}", "--out-dir", dist],
                cwd=ROOT,
                check=True,
                capture_output=True,
                timeout=900,
            )
        env = {
            **os.environ,
            # Direct wheel paths, so a same-version release on the index cannot win.
            "SMOKE_PIP_ARGS": " ".join(
                w.as_posix() for w in sorted(Path(dist).glob("*.whl"))
            ),
            "SMOKE_INSTALL_ATTEMPTS": "1",
            "SMOKE_INSTALL_WAIT": "0",
        }
        r = subprocess.run(
            [BASH, str(RELEASE), version],
            capture_output=True,
            text=True,
            env=env,
            timeout=1800,
            cwd=ROOT,
        )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "SMOKE PASS" in r.stdout
