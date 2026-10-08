"""Every ```python fence in docs/src must at least parse.

A syntax slip in a published example is copied straight into users' code, so
the docs tree is walked and each fence goes through ``ast.parse``. Pseudo-code
or deliberate fragments go in ``_ALLOWLIST`` with a one-line reason; the stale
check keeps that list honest. docs/src is vendored into the public tree, so the
tests run there too.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS_SRC = _REPO_ROOT / "docs" / "src"
_FENCE = re.compile(r"```python\n(.*?)```", re.S)

#: "relative/path.md#N" (N is the 1-based fence index in that file) -> reason it
#: is not valid Python. Empty today: all fences parse.
_ALLOWLIST: dict[str, str] = {}


def _fences() -> dict[str, str]:
    out: dict[str, str] = {}
    for md in sorted(_DOCS_SRC.rglob("*.md")):
        rel = md.relative_to(_DOCS_SRC).as_posix()
        for i, block in enumerate(
            _FENCE.findall(md.read_text(encoding="utf-8")), start=1
        ):
            out[f"{rel}#{i}"] = block
    return out


def _parses(block: str) -> bool:
    try:
        ast.parse(block)
    except SyntaxError:
        return False
    return True


def test_docs_python_fences_parse():
    failed = [
        key
        for key, block in _fences().items()
        if key not in _ALLOWLIST and not _parses(block)
    ]
    assert not failed, "python fences that do not parse: " + ", ".join(failed)


def test_allowlist_has_no_stale_entries():
    fences = _fences()
    stale = [key for key in _ALLOWLIST if key not in fences or _parses(fences[key])]
    assert not stale, "allowlist entries that are gone or now parse: " + ", ".join(
        stale
    )


def test_docs_dir_has_python_fences():
    assert len(_fences()) >= 20
