"""Pure helpers for `opencomplai ai status` (stdlib only)."""

from __future__ import annotations

import os
from pathlib import Path


def cache_files(cache_dir: Path) -> list[tuple[str, int]]:
    """Regular files under cache_dir (recursive) as (relative posix path, bytes), sorted."""
    root = Path(cache_dir)
    if not root.is_dir():
        return []
    found: list[tuple[str, int]] = []
    for dirpath, _dirs, names in os.walk(root, followlinks=False):
        for name in names:
            p = Path(dirpath) / name
            try:
                if p.is_symlink() or not p.is_file():
                    continue
                size = p.stat().st_size
            except OSError:
                continue
            found.append((p.relative_to(root).as_posix(), size))
    return sorted(found)


def format_cache_size(total_bytes: int) -> str:
    if total_bytes <= 0:
        return "0 MB"
    if total_bytes < 1024 * 1024:
        return "<1 MB"
    return f"{total_bytes // (1024 * 1024)} MB"


def spec_size_label(size_mb: int) -> str:
    return "unknown" if size_mb <= 0 else f"~{size_mb} MB"
