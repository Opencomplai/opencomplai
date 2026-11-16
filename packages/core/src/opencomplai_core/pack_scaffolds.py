"""Fill-in scaffolds a pack ships under `packs/<KEY>/scaffolds/`.

`scaffolds.json` maps a document id to `{"title", "target", "probe", "file"}`
or, instead of `file`, `"shared": "<family>/<name>.md"`. `file` sits beside the
JSON; `shared` resolves under `probes/scaffolds/`. `target` is the
repo-relative path the document is written to.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opencomplai_core import pack_registry

SCAFFOLDS_FILE = "scaffolds.json"
_SHARED_DIR = Path(__file__).resolve().parent / "probes" / "scaffolds"


def _scaffolds_dir(key: str) -> Path:
    return pack_registry.pack_dir(key) / "scaffolds"


def list_scaffolds(key: str) -> dict[str, dict[str, Any]]:
    """Document id -> entry for the pack; empty when it ships no scaffolds."""
    path = _scaffolds_dir(key) / SCAFFOLDS_FILE
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: cannot read scaffolds: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: scaffolds must be a JSON object")
    return data


def _source_path(key: str, doc: str, entry: dict[str, Any]) -> Path:
    has_file = "file" in entry
    has_shared = "shared" in entry
    if has_file == has_shared:
        raise ValueError(
            f"{key} scaffold {doc!r}: give exactly one of 'file' and 'shared'"
        )
    if has_file:
        return _scaffolds_dir(key) / entry["file"]
    return _SHARED_DIR / entry["shared"]


def scaffold_text(key: str, doc: str) -> str:
    """Text of one document. KeyError for an unknown id, ValueError for a bad
    entry or a missing file."""
    entries = list_scaffolds(key)
    if doc not in entries:
        raise KeyError(doc)
    path = _source_path(key, doc, entries[doc])
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{key} scaffold {doc!r}: cannot read {path}: {exc}") from exc


def write_scaffolds(
    key: str, docs: list[str], output_dir: Path, force: bool = False
) -> list[tuple[str, str]]:
    """Write each document to `<output_dir>/<target>`.

    Returns (path, "created" | "skipped"); an existing file is skipped unless
    `force`. All texts are read before anything is written.
    """
    entries = list_scaffolds(key)
    plan = []
    for doc in docs:
        if doc not in entries:
            raise KeyError(doc)
        target = Path(output_dir) / entries[doc]["target"]
        plan.append((target, scaffold_text(key, doc)))
    results: list[tuple[str, str]] = []
    for path, text in plan:
        if path.exists() and not force:
            results.append((str(path), "skipped"))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        results.append((str(path), "created"))
    return results
