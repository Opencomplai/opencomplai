"""Manifest of report files the tool itself wrote into the scanned folder.

The scan tree digest leaves out a fixed set of tool-written names (see
``classification_proposal.is_tool_written_path``). Report files with other
names (junit, sarif, a summary, ``--output-file``) would change the digest and
make a confirmed classification proposal read stale on the next run. This
module keeps ``.opencomplai/written-files.json``, a map of repo-relative posix
path to content hash, so the digest can drop a listed file for as long as its
content still equals what the tool recorded.

Trust: the manifest is a freshness hint, not a security boundary.
Anyone who can edit the tree can list a file they just edited. It only stops
the tool's own report files from staling a proposal. A missing or corrupt
manifest reads as empty, which is the 0.12.0 behaviour.

Pure module: no clock, no network.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from opencomplai_core.classification_proposal import (
    WRITTEN_FILES_MANIFEST,
    is_tool_written_path,
)

# ponytail: private import, promote _content_hash to public if a third caller appears.
from opencomplai_core.tree_digest import _content_hash

_SCHEMA_VERSION = 1


def load_written_files(repo_root: Path) -> dict[str, str]:
    """Recorded ``{rel_posix_path: sha256}``; ``{}`` for any problem. Never raises."""
    try:
        doc = json.loads(
            (repo_root / WRITTEN_FILES_MANIFEST).read_text(encoding="utf-8-sig")
        )
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict) or doc.get("schema_version") != _SCHEMA_VERSION:
        return {}
    files = doc.get("files")
    if not isinstance(files, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in files.items()
    ):
        return {}
    return dict(files)


def record_written_file(repo_root: Path, file: Path) -> None:
    """Record ``file``'s current content hash. Best effort; never raises."""
    try:
        root = repo_root.resolve()
        target = file.resolve()
        if not target.is_file():
            return
        rel = target.relative_to(root).as_posix()
        if is_tool_written_path(rel):
            return  # the digest already skips it by name; listing it only dirties the tree
        files = load_written_files(root)
        files[rel] = _content_hash(target)
        doc = {"schema_version": _SCHEMA_VERSION, "files": files}
        dest = root / WRITTEN_FILES_MANIFEST
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(doc, indent=2, sort_keys=True) + "\n")
            os.replace(tmp, dest)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    except (OSError, ValueError):
        return  # not under the root, or unwritable: recording must never fail the command


def unchanged_written_paths(repo_root: Path) -> frozenset[str]:
    """Listed paths whose current content hash equals the recorded one."""
    root = repo_root.resolve()
    return frozenset(
        rel
        for rel, recorded in load_written_files(root).items()
        if _inside(root, rel)
        and (root / rel).is_file()
        and _content_hash(root / rel) == recorded
    )


def _inside(root: Path, rel: str) -> bool:
    """True when manifest key ``rel`` is a relative path that stays under ``root``."""
    p = Path(rel)
    if p.is_absolute() or p.drive or ".." in p.parts:
        return False
    try:
        (root / p).resolve().relative_to(root)
    except (OSError, ValueError):
        return False
    return True
