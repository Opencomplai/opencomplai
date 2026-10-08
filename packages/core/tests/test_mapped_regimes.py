"""Mapped-only DORA/EBA citations: loader contract (SU-32c). Mapping, never a verdict."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from opencomplai_core import mapped_regimes as mr
from opencomplai_core.control_catalog import get_catalog

_VALID_ROW = {
    "eu_ai_act_article": "Art. 9",
    "regime": "DORA",
    "citation": "DORA Chapter II",
    "topic": "t",
    "source": "s",
    "confidence": "low",
    "needs_founder_review": True,
    "notes": "n",
}


def test_loads_both_regimes():
    data = mr.get_mapped_regimes()
    assert set(data) == set(mr.MAPPED_REGIMES)
    assert all(data[r] for r in mr.MAPPED_REGIMES)


def test_every_row_flagged_low_confidence_needs_review():
    for entries in mr.get_mapped_regimes().values():
        for entry in entries:
            assert entry.confidence == "low"
            assert entry.needs_founder_review is True


def test_entry_has_no_status_field():
    names = {f.name for f in dataclasses.fields(mr.MappedEntry)}
    assert not names & {"status", "verdict", "gap_status"}


def test_every_article_exists_in_control_catalog():
    catalog = get_catalog()
    for entries in mr.get_mapped_regimes().values():
        for entry in entries:
            assert entry.eu_ai_act_article in catalog


def test_framework_crosswalk_json_unchanged_shape():
    path = Path(mr.__file__).parent / "data" / "framework_crosswalk.json"
    text = path.read_text(encoding="utf-8").lower()
    raw = json.loads(text)
    assert "dora" not in raw
    assert "eba" not in raw
    assert '"dora"' not in text
    assert '"eba"' not in text


def test_rows_for_groups_by_article_and_regime():
    rows = mr.rows_for(["DORA"])
    assert "DORA" in rows["Art. 9"]
    assert all(set(by_regime) == {"DORA"} for by_regime in rows.values())


class TestFailLoud:
    def _load(self, monkeypatch, tmp_path, payload):
        path = tmp_path / "mapped_regimes.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(mr, "_DATA_PATH", path)
        mr.get_mapped_regimes.cache_clear()
        try:
            return mr.get_mapped_regimes()
        finally:
            mr.get_mapped_regimes.cache_clear()

    def test_valid_row_loads(self, monkeypatch, tmp_path):
        data = self._load(monkeypatch, tmp_path, {"rows": [_VALID_ROW]})
        assert data["DORA"][0].citation == "DORA Chapter II"

    def test_missing_file_raises(self, monkeypatch, tmp_path):
        monkeypatch.setattr(mr, "_DATA_PATH", tmp_path / "absent.json")
        mr.get_mapped_regimes.cache_clear()
        try:
            with pytest.raises(ValueError, match="cannot read"):
                mr.get_mapped_regimes()
        finally:
            mr.get_mapped_regimes.cache_clear()

    def test_row_without_review_flag_raises(self, monkeypatch, tmp_path):
        row = {**_VALID_ROW, "needs_founder_review": False}
        with pytest.raises(ValueError, match="needs_founder_review"):
            self._load(monkeypatch, tmp_path, {"rows": [row]})

    def test_non_low_confidence_raises(self, monkeypatch, tmp_path):
        row = {**_VALID_ROW, "confidence": "medium"}
        with pytest.raises(ValueError, match="confidence"):
            self._load(monkeypatch, tmp_path, {"rows": [row]})

    def test_unknown_regime_raises(self, monkeypatch, tmp_path):
        row = {**_VALID_ROW, "regime": "SOX"}
        with pytest.raises(ValueError, match="unknown regime"):
            self._load(monkeypatch, tmp_path, {"rows": [row]})

    def test_empty_rows_raises(self, monkeypatch, tmp_path):
        with pytest.raises(ValueError, match="rows"):
            self._load(monkeypatch, tmp_path, {"rows": []})

    def test_duplicate_row_raises(self, monkeypatch, tmp_path):
        with pytest.raises(ValueError, match="duplicate"):
            self._load(monkeypatch, tmp_path, {"rows": [_VALID_ROW, _VALID_ROW]})


def _not_covered_articles(key):
    first, *rest = key.split("/")
    return [first.strip()] + [f"Art. {p.strip()}" for p in rest]


def _false_reasons(not_covered, catalog):
    return [
        key
        for key, reason in not_covered.items()
        if all(a in catalog for a in _not_covered_articles(key))
        and "not in control_catalog" in reason.lower()
    ]


def _load_not_covered():
    path = Path(mr.__file__).parent / "data" / "mapped_regimes.json"
    return json.loads(path.read_text(encoding="utf-8"))["_meta"]["not_covered"]


def test_not_covered_reasons_do_not_contradict_catalog():
    assert _false_reasons(_load_not_covered(), get_catalog()) == []


def test_not_covered_guard_detects_false_reason():
    old = {
        "Art. 72/73": "Serious-incident reporting is not in control_catalog, so no row."
    }
    assert _false_reasons(old, {"Art. 72": 1, "Art. 73": 1}) == ["Art. 72/73"]
    assert _false_reasons(_load_not_covered(), get_catalog()) == []
