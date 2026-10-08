"""The ruleset_history loader: order, strict version filters, bad input."""

from __future__ import annotations

import pytest
from opencomplai_core import ruleset_history as rh
from opencomplai_core.rules import RULE_SET_VERSION


def test_loaded_history_ends_at_rule_set_version():
    assert rh.load_ruleset_history()[-1]["version"] == RULE_SET_VERSION


def test_entries_since_is_strict_and_numeric(monkeypatch):
    fake = tuple({"version": v} for v in ("1.9.0", "1.10.0", "1.11.0"))
    monkeypatch.setattr(rh, "_load", lambda: fake)
    assert [e["version"] for e in rh.entries_since("1.9.0")] == ["1.10.0", "1.11.0"]
    assert [e["version"] for e in rh.entries_since(None)] == [
        "1.9.0",
        "1.10.0",
        "1.11.0",
    ]
    assert rh.entries_since("1.11.0") == []


def test_entries_between_bounds(monkeypatch):
    fake = tuple({"version": v} for v in ("1.4.0", "1.5.0", "1.6.0", "1.7.0"))
    monkeypatch.setattr(rh, "_load", lambda: fake)
    assert [e["version"] for e in rh.entries_between("1.4.0", "1.6.0")] == [
        "1.5.0",
        "1.6.0",
    ]
    assert rh.entries_between("1.6.0", "1.6.0") == []


@pytest.mark.parametrize("bad", ["", "1..2", "v1.2", "1.2.x", "1.-2", "latest"])
def test_parse_version_rejects_garbage(bad):
    with pytest.raises(ValueError, match="dotted integer"):
        rh.parse_version(bad)
    assert rh.parse_version("1.10.0") == (1, 10, 0)
