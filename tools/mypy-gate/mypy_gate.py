#!/usr/bin/env python3
"""
mypy_gate.py -- ratchet gate for mypy errors in the two typed packages.

``core`` and ``sdk-python`` ship ``py.typed`` but carry known type errors. This
records each package's error count in ``baseline.json`` and fails when a count
goes UP; a count that goes down prints a reminder to lower the baseline.

Usage (run from anywhere; mypy must be importable by the running interpreter):
    python tools/mypy-gate/mypy_gate.py            # same as --check
    python tools/mypy-gate/mypy_gate.py --check
    python tools/mypy-gate/mypy_gate.py --update   # rewrite baseline.json

Counts depend on the mypy version, so baseline.json records it and CI pins the
same one (``uv run --with mypy==<version>``). Stdlib only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
BASELINE = _HERE / "baseline.json"
PACKAGES = {
    "core": _REPO / "packages" / "core",
    "sdk-python": _REPO / "packages" / "sdk-python",
}

_FOUND = re.compile(r"^Found (\d+) errors? in \d+ files?", re.M)
_SUCCESS = re.compile(r"^Success: no issues found", re.M)


def parse_error_count(output: str) -> int:
    """Read mypy's summary line. Raises ValueError when there is none (a crash)."""
    if m := _FOUND.search(output):
        return int(m.group(1))
    if _SUCCESS.search(output):
        return 0
    raise ValueError(f"no mypy summary line in output: {output[-300:]!r}")


def _mypy(args: list[str], cwd: Path) -> str:
    done = subprocess.run(
        [sys.executable, "-m", "mypy", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return done.stdout + done.stderr


def run(pkg_dir: Path) -> int:
    """mypy error count for one package, using the package's own config."""
    return parse_error_count(_mypy([], pkg_dir))


def mypy_version() -> str:
    m = re.search(r"mypy (\d+(?:\.\d+)+)", _mypy(["--version"], _REPO))
    if not m:
        raise ValueError("could not read the mypy version")
    return m.group(1)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    unknown = [a for a in args if a not in ("--check", "--update")]
    if unknown or len(set(args)) > 1:
        print("usage: mypy_gate.py [--check | --update]", file=sys.stderr)
        return 2
    counts = {name: run(path) for name, path in PACKAGES.items()}

    if "--update" in args:
        data = {**counts, "mypy_version": mypy_version()}
        BASELINE.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"baseline updated: {data}")
        return 0

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    failed = False
    for name, count in counts.items():
        allowed = baseline[name]
        print(
            f"{name}: {count} mypy errors (baseline {allowed}, delta {count - allowed:+d})"
        )
        if count > allowed:
            failed = True
        elif count < allowed:
            print(f"{name}: below baseline -- lower it with: mypy_gate.py --update")
    if failed:
        print("mypy gate FAILED: new type errors exceed the recorded baseline")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
