"""Shared snippet reader — one disk read per location."""

from __future__ import annotations

from pathlib import Path


class SnippetCache:
    """Cache file snippets keyed by ``path:line`` location strings."""

    def __init__(self, context_lines: int = 5, root: Path | None = None) -> None:
        self._context_lines = context_lines
        self._root = root
        # Numbered locations whose file could not be read (never silent).
        self.unreadable: set[str] = set()
        self._cache: dict[str, str] = {}

    def read(self, location: str, *, context_lines: int | None = None) -> str:
        if location in self._cache:
            return self._cache[location]
        snippet = _read_snippet_uncached(
            location,
            context_lines=context_lines or self._context_lines,
            root=self._root,
            unreadable=self.unreadable,
        )
        self._cache[location] = snippet
        return snippet

    def read_narrow(self, location: str, *, half_window: int = 2) -> str:
        key = f"{location}@narrow:{half_window}"
        if key in self._cache:
            return self._cache[key]
        snippet = _read_snippet_uncached(
            location,
            half_window=half_window,
            root=self._root,
            unreadable=self.unreadable,
        )
        self._cache[key] = snippet
        return snippet


def _read_snippet_uncached(
    location: str,
    *,
    context_lines: int = 5,
    half_window: int | None = None,
    root: Path | None = None,
    unreadable: set[str] | None = None,
) -> str:
    if ":" not in location:
        return ""
    file_path, _, line_str = location.rpartition(":")
    try:
        line_no = int(line_str)
    except ValueError:
        return ""
    try:
        path = Path(file_path) if root is None else Path(root) / file_path
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        if unreadable is not None:
            unreadable.add(location)
        return ""
    if half_window is not None:
        start = max(0, line_no - 1 - half_window)
        end = min(len(lines), line_no + half_window)
    else:
        start = max(0, line_no - 1 - context_lines // 2)
        end = min(len(lines), line_no + context_lines // 2)
    return "\n".join(lines[start:end])
