"""Shared dictionary loader for detectors."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_signals.json"

_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}
_CAMEL_BOUNDARY_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_BOUNDARY_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")


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


def tokenize_identifier(text: str) -> set[str]:
    """Split identifiers into semantic segments (snake, camelCase, dotted paths)."""
    if not text:
        return set()
    normalized = _CAMEL_BOUNDARY_2.sub(r"\1_\2", text)
    normalized = _CAMEL_BOUNDARY_1.sub(r"\1_\2", normalized)
    lower = normalized.lower()
    segments: set[str] = set()
    for chunk in re.split(r"[^a-z0-9_]+", lower):
        if not chunk:
            continue
        segments.add(chunk)
        for part in chunk.split("_"):
            if part:
                segments.add(part)
    return segments


_SEPARATOR_RUN = re.compile(r"[-_.]+")
_NAME_CHUNK_SPLIT = re.compile(r"[^a-z0-9_.\-]+")


@lru_cache(maxsize=4096)
def normalize_package_name(text: str) -> str:
    """Lower-case a package or module name; every run of ``-``, ``_``, ``.`` is one ``_``."""
    return _SEPARATOR_RUN.sub("_", text.lower()).strip("_")


def _match_normalised(identifier: str, signal: str) -> bool:
    """Whole-name equality after normalising separators; never a substring test."""
    sig_lower = signal.lower()
    if "_" not in sig_lower and "." not in sig_lower and len(sig_lower) < 4:
        return False
    wanted = normalize_package_name(sig_lower)
    if not wanted:
        return False
    for chunk in _NAME_CHUNK_SPLIT.split(identifier.lower()):
        if normalize_package_name(chunk) == wanted:
            return True
        if "." in chunk and any(
            normalize_package_name(part) == wanted for part in chunk.split(".")
        ):
            return True
    return False


def match_code_signal(identifier: str, signal: str) -> bool:
    """Match a code signal, then fall back to the separator-insensitive name match.

    The fallback runs only when the exact logic found nothing, so it can add
    matches (``face-recognition`` for ``face_recognition``) and never remove one.
    """
    return _match_existing(identifier, signal) or _match_normalised(identifier, signal)


def _match_existing(identifier: str, signal: str) -> bool:
    """Match Annex III / Art. 5 code signals without short-substring false positives."""
    if not identifier or not signal:
        return False
    ident_lower = identifier.lower()
    sig_lower = signal.lower()
    if ident_lower == sig_lower:
        return True

    segments = tokenize_identifier(identifier)
    if sig_lower in segments:
        return True

    if "." in sig_lower:
        if sig_lower in ident_lower:
            return True
        tail = sig_lower.rsplit(".", 1)[-1]
        prefix = sig_lower.rsplit(".", 1)[0]
        return tail in segments and prefix in ident_lower

    if "_" in sig_lower or len(sig_lower) >= 4:
        if sig_lower in segments:
            return True
        pattern = re.compile(
            r"(?<![a-z0-9_])" + re.escape(sig_lower) + r"(?![a-z0-9_])"
        )
        return pattern.search(ident_lower) is not None

    return False


def match_any_code_signal(identifier: str, signals: Iterable[str]) -> str | None:
    """Return the first matching code signal for *identifier*, if any."""
    for signal in signals:
        if match_code_signal(identifier, signal):
            return signal
    return None


def match_token_identifier(text: str, category_key: str) -> str | None:
    """Identifier-aware matching for AST tokens, package names, and import modules."""
    for token in load_signals().get(category_key, []):
        if match_code_signal(text, token):
            return token
    return None
