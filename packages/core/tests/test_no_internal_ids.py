"""Shipped package files (wheels, sdists, PyPI metadata) carry no planning ids."""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
INTERNAL_ID = re.compile(r"\bSU-[0-9A-Z][0-9A-Za-z-]*")


def _shipped_files() -> list[Path]:
    files = [
        p
        for p in _REPO.glob("packages/*/src/**/*")
        if p.is_file() and "__pycache__" not in p.parts
    ]
    files += _REPO.glob("packages/*/README.md")
    files += _REPO.glob("packages/*/pyproject.toml")
    return sorted(files)


def test_shipped_package_files_carry_no_internal_ids():
    files = _shipped_files()
    models = _REPO / "packages/core/src/opencomplai_core/models.py"
    assert models in files
    hits = []
    for path in files:
        text = path.read_bytes().decode("utf-8", "ignore")
        for n, line in enumerate(text.splitlines(), 1):
            for found in INTERNAL_ID.findall(line):
                hits.append(f"{path.relative_to(_REPO).as_posix()}:{n}: {found}")
    assert hits == []


def test_id_pattern_matches_known_shapes_only():
    assert INTERNAL_ID.findall("SU-14a SU-F0b SU-2 SU-135a") == [
        "SU-14a",
        "SU-F0b",
        "SU-2",
        "SU-135a",
    ]
    assert INTERNAL_ID.findall("ISSU-1 su-2 SU- SUSE") == []
