"""Agent responsibility reference data: loader and shipped rows."""

from __future__ import annotations

import copy
import json
import re

import opencomplai_core.agent_responsibility as ar
import pytest
from opencomplai_core.agent_responsibility import get_responsibilities

_UPSTREAM_REF = re.compile(r"Art\. (53|55)\b")


@pytest.fixture(autouse=True)
def _clear_cache():
    get_responsibilities.cache_clear()
    yield
    get_responsibilities.cache_clear()


def test_loads_rows():
    rows = get_responsibilities()
    assert len(rows) >= 10
    assert {r.party for r in rows} == {"customer", "upstream_model_provider", "shared"}


def test_every_row_carries_review_metadata():
    for r in get_responsibilities():
        assert r.source.strip()
        assert r.confidence in {"low", "medium"}
        assert r.needs_founder_review is True


def test_no_row_claims_high_confidence():
    assert all(r.confidence == "low" for r in get_responsibilities())


def test_gpai_duties_stay_upstream():
    gpai = [r for r in get_responsibilities() if _UPSTREAM_REF.search(r.regime_ref)]
    assert gpai
    assert all(r.party == "upstream_model_provider" for r in gpai)


def _write(tmp_path, monkeypatch, mutate):
    raw = json.loads(ar._DATA_PATH.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    mutate(raw)
    path = tmp_path / "agent_responsibility.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(ar, "_DATA_PATH", path)
    get_responsibilities.cache_clear()


def _del(key):
    return lambda raw: raw["rows"][0].pop(key)


def _set(key, value):
    return lambda raw: raw["rows"][0].__setitem__(key, value)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw.__setitem__("rows", []),
        lambda raw: raw.pop("rows"),
        lambda raw: raw["rows"].append(copy.deepcopy(raw["rows"][0])),
        _set("party", "nobody"),
        _set("confidence", "high"),
        _del("confidence"),
        _del("needs_founder_review"),
        _set("needs_founder_review", "yes"),
        _set("source", " "),
        _del("source"),
    ],
    ids=[
        "empty-rows",
        "no-rows",
        "duplicate-id",
        "bad-party",
        "bad-confidence",
        "missing-confidence",
        "missing-flag",
        "non-bool-flag",
        "empty-source",
        "missing-source",
    ],
)
def test_malformed_file_raises(tmp_path, monkeypatch, mutate):
    _write(tmp_path, monkeypatch, mutate)
    with pytest.raises(ValueError, match="agent_responsibility"):
        get_responsibilities()


def test_unreadable_and_bad_json_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(ar, "_DATA_PATH", tmp_path / "missing.json")
    with pytest.raises(ValueError, match="cannot read"):
        get_responsibilities()
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    monkeypatch.setattr(ar, "_DATA_PATH", bad)
    get_responsibilities.cache_clear()
    with pytest.raises(ValueError, match="invalid JSON"):
        get_responsibilities()
