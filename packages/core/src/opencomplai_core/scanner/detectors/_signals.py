"""Shared dictionary loader for detectors."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_signals.json"

_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


@lru_cache(maxsize=1)
def load_signals() -> dict:
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def _compile_category(category_key: str) -> re.Pattern[str]:
    if category_key in _PATTERN_CACHE:
        return _PATTERN_CACHE[category_key]
    tokens = load_signals().get(category_key, [])
    if not tokens:
        pattern = re.compile(r"(?!)")
    else:
        escaped = [re.escape(t) for t in tokens]
        pattern = re.compile(r"\b(" + "|".join(escaped) + r")\b", re.I)
    _PATTERN_CACHE[category_key] = pattern
    return pattern


def match_token(text: str, category_key: str) -> str | None:
    """Word-boundary matching for prose / file content lines."""
    m = _compile_category(category_key).search(text)
    return m.group(0).lower() if m else None


def match_token_identifier(text: str, category_key: str) -> str | None:
    """Substring matching for AST identifiers, package names, and import modules."""
    lower = text.lower()
    for token in load_signals().get(category_key, []):
        if token in lower:
            return token
    return None
