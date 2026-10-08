"""ruleset_history.json stays in step with RULE_SET_VERSION."""

from __future__ import annotations

import json
from pathlib import Path

import opencomplai_core
from opencomplai_core.rules import RULE_SET_VERSION

HISTORY = json.loads(
    (
        Path(opencomplai_core.__file__).parent / "data" / "ruleset_history.json"
    ).read_text(encoding="utf-8")
)


def test_last_history_entry_equals_rule_set_version():
    assert HISTORY[-1]["version"] == RULE_SET_VERSION


def test_history_versions_are_unique_and_ascending():
    versions = [tuple(int(p) for p in e["version"].split(".")) for e in HISTORY]
    assert versions == sorted(set(versions))


def test_every_entry_has_source_confidence_and_review_flag():
    for entry in HISTORY:
        assert entry["source"]
        assert entry["confidence"]
        assert isinstance(entry["needs_founder_review"], bool)
        assert entry["summary"]
        assert entry["changes"]
