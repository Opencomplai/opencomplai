"""Tree provenance for ``check``: content digest and dirty flag from git."""

from __future__ import annotations

import contextlib
import os
import subprocess
from pathlib import Path

from opencomplai_core.tree_digest import tree_digest


def _git(repo_root: Path, *args: str) -> bytes | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def tree_provenance(repo_root: Path) -> tuple[str, bool] | None:
    """``(tree_sha256, tree_dirty)`` for the git tree at ``repo_root``, else None.

    The digest covers tracked plus untracked non-ignored file content. Dirty is
    true for any tracked modification or any untracked non-ignored file. The
    ``.`` pathspec keeps paths relative to ``repo_root``, so one tree in two
    directories gives one digest.

    ponytail: whole-file reads, submodules are not descended, and a
    ``.gitattributes`` text conversion can report a clean checkout as dirty on
    one platform; add streaming or conversion handling if that bites.
    """
    tracked = _git(repo_root, "ls-files", "-z", "--", ".")
    untracked = _git(
        repo_root, "ls-files", "-z", "--others", "--exclude-standard", "--", "."
    )
    status = _git(repo_root, "status", "--porcelain", "--", ".")
    if not tracked or untracked is None or status is None:
        return None
    paths = {
        os.fsdecode(p) for blob in (tracked, untracked) for p in blob.split(b"\0") if p
    }
    digest = tree_digest((p, repo_root / p) for p in paths)
    return digest, bool(status.strip())


def record_written_files(repo_root: Path, *paths: Path | None) -> None:
    """Record report files this run wrote, so the scan digest can skip them.

    Call after each file is closed. A path outside ``repo_root`` or not on disk
    is skipped by the recorder itself.

    ponytail: best effort, last writer wins. A failure is swallowed so recording
    never changes an exit code; the file then reads as edited (stale proposal).
    """
    from opencomplai_core.written_files import record_written_file

    for path in paths:
        if path is None:
            continue
        with contextlib.suppress(Exception):  # never fail the command over a hint
            record_written_file(repo_root, path)
