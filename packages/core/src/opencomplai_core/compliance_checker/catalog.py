"""Load FLI catalog JSON from the bundled data directory."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from opencomplai_core.compliance_checker.models import ObligationItem, StatusChangeItem

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_json(name: str) -> dict:
    path = _DATA_DIR / name
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_obligations() -> dict[str, ObligationItem]:
    raw = _load_json("obligations.json")
    return {key: ObligationItem(id=key, **value) for key, value in raw.items()}


@lru_cache(maxsize=1)
def load_status_changes() -> dict[str, StatusChangeItem]:
    raw = _load_json("status_changes.json")
    return {key: StatusChangeItem(id=key, **value) for key, value in raw.items()}


@lru_cache(maxsize=1)
def load_help_content() -> dict[str, dict[str, str]]:
    return _load_json("help_content.json")


@lru_cache(maxsize=1)
def load_questions() -> dict[str, dict[str, Any]]:
    """Question id -> {label, section, options?} for rendering answer summaries."""
    return _load_json("questions.json")


def get_obligation(obligation_id: str) -> ObligationItem:
    obligations = load_obligations()
    if obligation_id not in obligations:
        msg = f"Unknown obligation id: {obligation_id}"
        raise KeyError(msg)
    return obligations[obligation_id]


def get_status_change(status_id: str) -> StatusChangeItem:
    status_changes = load_status_changes()
    if status_id not in status_changes:
        msg = f"Unknown status change id: {status_id}"
        raise KeyError(msg)
    return status_changes[status_id]
