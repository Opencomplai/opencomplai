"""Content digest over a set of files, independent of where the tree lives."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from pathlib import Path

_UNREADABLE = b"<unreadable>"


def _content_hash(path: Path) -> str:
    try:
        if path.is_symlink():
            data = os.readlink(path).encode("utf-8", "surrogateescape")
        else:
            data = path.read_bytes().replace(b"\r\n", b"\n")
    except OSError:  # missing, a directory, or unreadable
        data = _UNREADABLE
    return hashlib.sha256(data).hexdigest()


def tree_digest(items: Iterable[tuple[str, Path]]) -> str:
    """SHA-256 over sorted ``path\\0content-hash`` lines for ``(rel_posix_path, file)``.

    CRLF is hashed as LF (the ``manifest_sha256`` rule) so one tree hashes the
    same on Windows and Linux. A symlink hashes its target text; a missing,
    directory or unreadable path hashes a fixed marker.

    ponytail: whole-file reads (no streaming); submodule directories are not
    descended; stream or descend if either ever matters.
    """
    lines = sorted((rel, _content_hash(file)) for rel, file in items)
    body = "".join(f"{rel}\0{digest}\n" for rel, digest in lines)
    return hashlib.sha256(body.encode("utf-8", "surrogateescape")).hexdigest()
