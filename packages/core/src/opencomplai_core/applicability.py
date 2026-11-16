"""Scope keys and framework-level applicability.

`scope_keys.json` holds the answer keys every pack may use in
`framework_inputs.<FW>.scope`. A pack adds its own keys, and a framework-level
outcome, in `packs/<KEY>/applicability.json`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from opencomplai_core import pack_registry

OUTCOMES = ("applies", "voluntary", "not_applicable")
APPLICABILITY_FILE = "applicability.json"
MIN_QUESTIONS = 2
MAX_QUESTIONS = 6

_SCOPE_KEYS_FILE = Path(__file__).resolve().parent / "scope_keys.json"


def _read_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: cannot read: {exc}") from exc


def _check_entry(path: Path, key: str, entry: Any) -> None:
    if not isinstance(entry, dict) or not all(
        isinstance(entry.get(name), str) and entry[name].strip()
        for name in ("text", "false_means")
    ):
        raise ValueError(f"{path}: {key!r} needs non-empty text and false_means")


@cache
def _shared_keys() -> dict[str, dict[str, str]]:
    data = _read_json(_SCOPE_KEYS_FILE)
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{_SCOPE_KEYS_FILE}: must be a non-empty JSON object")
    for key, entry in data.items():
        _check_entry(_SCOPE_KEYS_FILE, key, entry)
    return data


def load_scope_keys() -> dict[str, dict[str, str]]:
    """The shared scope keys: key -> {text, false_means}."""
    return {key: dict(entry) for key, entry in _shared_keys().items()}


def load_applicability(key: str) -> dict[str, Any] | None:
    """Read and validate `packs/<key>/applicability.json`.

    None when the pack has no such file; ValueError naming the file when it is
    unreadable or malformed.
    """
    path = pack_registry.pack_dir(key) / APPLICABILITY_FILE
    if not path.is_file():
        return None
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: must be a JSON object")
    if data.get("default") not in OUTCOMES:
        raise ValueError(f"{path}: default must be one of {', '.join(OUTCOMES)}")
    questions = data.get("questions")
    if not isinstance(questions, list) or not (
        MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS
    ):
        raise ValueError(
            f"{path}: questions must be a list of {MIN_QUESTIONS} to "
            f"{MAX_QUESTIONS} entries"
        )
    own: set[str] = set()
    for question in questions:
        if not isinstance(question, dict) or not isinstance(question.get("key"), str):
            raise ValueError(f"{path}: every question needs a key")
        qkey = question["key"]
        _check_entry(path, qkey, question)
        if qkey in _shared_keys():
            raise ValueError(f"{path}: question key {qkey!r} repeats a shared key")
        if qkey in own:
            raise ValueError(f"{path}: question key {qkey!r} is repeated")
        own.add(qkey)
    outcomes = data.get("outcomes")
    if not isinstance(outcomes, list):
        raise ValueError(f"{path}: outcomes must be a list")
    known = own | set(_shared_keys())
    for rule in outcomes:
        when = rule.get("when") if isinstance(rule, dict) else None
        if (
            not isinstance(when, dict)
            or not when
            or not all(isinstance(v, bool) for v in when.values())
        ):
            raise ValueError(f"{path}: every outcome needs a `when` of true/false")
        if set(when) - known:
            undeclared = ", ".join(sorted(set(when) - known))
            raise ValueError(f"{path}: outcome uses undeclared key(s) {undeclared}")
        if rule.get("outcome") not in OUTCOMES:
            raise ValueError(f"{path}: outcome must be one of {', '.join(OUTCOMES)}")
        if not isinstance(rule.get("reason"), str):
            raise ValueError(f"{path}: every outcome needs a reason")
    return data


def declared_scope_keys(key: str) -> dict[str, dict[str, str]]:
    """Shared keys plus the pack's own questions: key -> {text, false_means}."""
    declared = load_scope_keys()
    data = load_applicability(key)
    if data is not None:
        for question in data["questions"]:
            declared[question["key"]] = {
                "text": question["text"],
                "false_means": question["false_means"],
            }
    return declared


def applicability_outcome(
    key: str, answers: Mapping[str, bool]
) -> tuple[str, str] | None:
    """`(outcome, reason)` for a pack, or None when it has no applicability file.

    The first rule whose `when` pairs all equal the answers wins; otherwise the
    default, with an empty reason.
    """
    data = load_applicability(key)
    if data is None:
        return None
    for rule in data["outcomes"]:
        if all(
            name in answers and answers[name] is want
            for name, want in rule["when"].items()
        ):
            return rule["outcome"], rule["reason"]
    return data["default"], ""
