"""Write the Homebrew resource blocks for the opencomplai formula from a pip report.

``brew update-python-resources`` only considers releases uploaded more than 24 hours ago (it runs pip
with ``--uploaded-prior-to=P1D``), and our own packages are always newer than that on release day, so
it fails then. This script does the same job from ``pip install --dry-run --report`` and keeps the
protection the 24-hour rule gives: it refuses when a third-party package in the report is younger than
``--min-age-hours``. Our own packages (opencomplai, opencomplai-cli, opencomplai-core) are exempt.

Usage, with the Python the formula uses (3.12):

    python -m pip install --dry-run --ignore-installed --report report.json opencomplai==X.Y.Z
    python packaging/homebrew/resources.py report.json formula.rb

The formula is rewritten in place: the ``# RESOURCES:`` marker, or the resource blocks already there,
are replaced by one block per package in the report (the formula's own package excluded), in name order,
each with the sdist url and sha256 from PyPI. Nothing is written if a package has no sdist or is too young.

Environment (tests only): HOMEBREW_PYPI_BASE, default https://pypi.org/pypi.
Exit codes: 0 written, 1 refused, 2 bad usage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

OWN = {"opencomplai", "opencomplai-cli", "opencomplai-core"}
MARKER = "  # RESOURCES: generated at release by brew update-python-resources\n"
BLOCK_RE = re.compile(r'(?:^  resource "[^"]+" do\n(?:    .*\n)+?  end\n\n?)+', re.M)


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def packages(report: dict) -> list[tuple[str, str]]:
    found = {
        (norm(i["metadata"]["name"]), i["metadata"]["version"])
        for i in report["install"]
    }
    return sorted(p for p in found if p[0] != "opencomplai")


def sdist(base: str, name: str, version: str) -> dict | None:
    with urllib.request.urlopen(f"{base}/{name}/{version}/json", timeout=60) as resp:
        doc = json.load(resp)
    found = [u for u in doc.get("urls") or [] if u.get("packagetype") == "sdist"]
    return found[0] if found else None


def render(blocks: list[str], formula: str) -> str:
    body = "\n".join(blocks)
    if MARKER in formula:
        return formula.replace(MARKER, body, 1)
    if not BLOCK_RE.search(formula):
        raise ValueError(
            "the formula has neither the RESOURCES marker nor resource blocks"
        )
    return BLOCK_RE.sub(lambda _m: body + "\n", formula, count=1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", type=Path)
    ap.add_argument("formula", type=Path)
    ap.add_argument("--min-age-hours", type=float, default=24.0)
    ap.add_argument("--now", help="ISO timestamp to measure age from (tests only)")
    args = ap.parse_args(argv)

    base = os.environ.get("HOMEBREW_PYPI_BASE", "https://pypi.org/pypi").rstrip("/")
    now = dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(dt.UTC)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    formula = args.formula.read_bytes().decode("utf-8")

    blocks: list[str] = []
    problems: list[str] = []
    for name, version in packages(report):
        entry = sdist(base, name, version)
        if entry is None:
            problems.append(f"{name}=={version}: no sdist on PyPI")
            continue
        up = dt.datetime.fromisoformat(
            str(entry["upload_time_iso_8601"]).replace("Z", "+00:00")
        )
        age = (now - up).total_seconds() / 3600
        own = name in OWN
        print(
            f"{name}=={version:<10} {'own' if own else 'third-party':<11} {age:8.1f} h  {entry['filename']}"
        )
        if not own and age < args.min_age_hours:
            problems.append(f"{name}=={version}: third-party, uploaded {age:.1f} h ago")
        blocks.append(
            f'  resource "{name}" do\n    url "{entry["url"]}"\n    sha256 "{entry["digests"]["sha256"]}"\n  end\n'
        )
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    try:
        out = render(blocks, formula)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    args.formula.write_bytes(out.encode("utf-8"))
    print(f"wrote {len(blocks)} resource blocks to {args.formula}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
