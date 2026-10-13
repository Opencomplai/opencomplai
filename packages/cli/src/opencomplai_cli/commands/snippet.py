"""Display-only source snippet reader for the human scan output."""

from __future__ import annotations

from pathlib import Path


def read_display_snippet(location: str, repo_root: Path | None = None) -> str | None:
    """Return the trimmed source line for ``rel_path:line``, or ``None``.

    The file is resolved against ``repo_root`` (the process working directory
    when ``None``); an absolute path stays absolute under the join.
    """
    if ":" not in location:
        return None
    file_path, _, line_str = location.rpartition(":")
    try:
        line_number = int(line_str)
    except ValueError:
        return None
    base = Path(repo_root) if repo_root is not None else Path()
    try:
        lines = (
            (base / file_path)
            .read_text(encoding="utf-8", errors="replace")
            .splitlines()
        )
        if line_number < 1 or line_number > len(lines):
            return None
        return lines[line_number - 1][:80].strip()
    except OSError:
        return None
