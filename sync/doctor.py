#!/usr/bin/env python3
"""Environment verification script for Opencomplai contributors."""

import subprocess
import sys
from pathlib import Path
from shutil import which

CHECKS = []
FAILURES: list[str] = []


def check(name: str):
    """Decorator to register an environment check function."""

    def decorator(fn):
        CHECKS.append((name, fn))
        return fn

    return decorator


@check("Python >= 3.11")
def check_python() -> None:
    """Verify Python version meets the minimum requirement."""
    assert sys.version_info >= (3, 11), f"Found Python {sys.version_info}"


@check("uv installed")
def check_uv() -> None:
    """Verify uv is available in PATH."""
    result = subprocess.run(["uv", "--version"], capture_output=True)
    assert result.returncode == 0, "uv not found in PATH"


@check("pytest available")
def check_pytest() -> None:
    """Verify pytest is available."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--version"], capture_output=True
    )
    assert result.returncode == 0, "pytest not available"


@check("ruff available")
def check_ruff() -> None:
    """Verify ruff is available in PATH."""
    result = subprocess.run(["ruff", "--version"], capture_output=True)
    assert result.returncode == 0, "ruff not found in PATH"


@check("Node.js >= 20")
def check_node() -> None:
    """Verify Node.js version meets the minimum requirement."""
    result = subprocess.run(["node", "--version"], capture_output=True, text=True)
    assert result.returncode == 0, "node not found in PATH"
    version = result.stdout.strip().lstrip("v")
    major = int(version.split(".")[0])
    assert major >= 20, f"Node.js 20+ required, found v{version}"


@check("pnpm installed")
def check_pnpm() -> None:
    """Verify pnpm is available in PATH."""
    pnpm = which("pnpm")
    assert pnpm is not None, "pnpm not found in PATH"
    result = subprocess.run([pnpm, "--version"], capture_output=True)
    assert result.returncode == 0, "pnpm not found in PATH"


@check("packages/core importable")
def check_core() -> None:
    """Verify opencomplai_core is importable."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import opencomplai_core; print(opencomplai_core.__version__)",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, "opencomplai_core not importable"


@check("packages/sdk-python importable")
def check_sdk() -> None:
    """Verify the opencomplai SDK is importable."""
    result = subprocess.run(
        [sys.executable, "-c", "import opencomplai; print(opencomplai.__version__)"],
        capture_output=True,
    )
    assert result.returncode == 0, "opencomplai SDK not importable"


@check("gateway-api node_modules installed")
def check_gateway_node_modules() -> None:
    """Verify gateway-api Node.js dependencies are installed."""
    node_modules = Path("services/gateway-api/node_modules")
    assert node_modules.exists(), (
        "services/gateway-api/node_modules not found. "
        "Run: cd services/gateway-api && pnpm install"
    )


if __name__ == "__main__":
    print("Opencomplai environment check\n")
    all_passed = True
    for name, fn in CHECKS:
        try:
            fn()
            print(f"  [OK]   {name}")
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            all_passed = False

    print()
    if all_passed:
        print("All checks passed.")
        sys.exit(0)
    else:
        print("Some checks failed. See above for details.")
        sys.exit(1)
