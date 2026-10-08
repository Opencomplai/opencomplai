"""Read the rule-set history (`data/ruleset_history.json`), oldest to newest."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "data" / "ruleset_history.json"


@lru_cache(maxsize=1)
def _load() -> tuple[dict, ...]:
    return tuple(json.loads(_PATH.read_text(encoding="utf-8")))


def load_ruleset_history() -> list[dict]:
    """Entries in file order (oldest first; the last is RULE_SET_VERSION)."""
    return [dict(e) for e in _load()]


def parse_version(v: str) -> tuple[int, ...]:
    """'1.10.0' -> (1, 10, 0). ValueError on anything but dot-separated integers."""
    parts = v.split(".") if isinstance(v, str) else []
    if not parts or not all(p.isascii() and p.isdigit() for p in parts):
        raise ValueError(f"not a dotted integer version: {v!r}")
    return tuple(int(p) for p in parts)


def entries_since(since: str | None) -> list[dict]:
    """Entries whose version is strictly greater than `since` (all when None)."""
    entries = load_ruleset_history()
    if since is None:
        return entries
    floor = parse_version(since)
    return [e for e in entries if parse_version(e["version"]) > floor]


def entries_between(a: str, b: str) -> list[dict]:
    """Entries greater than `a`, up to and including `b`."""
    lo, hi = parse_version(a), parse_version(b)
    return [e for e in load_ruleset_history() if lo < parse_version(e["version"]) <= hi]
