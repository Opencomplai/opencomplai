"""Unit tests for the NIST AI RMF 1.0 subcategory taxonomy loader (CP-16).

Covers: taxonomy shape/coverage and the fail-loud contract mirrored from
`harmonised_standards.get_catalog()` -- a malformed or missing data file
raises `ValueError` rather than silently degrading to an empty taxonomy.
"""

from __future__ import annotations

import json

import pytest
from opencomplai_core.nist_ai_rmf_subcategories import (
    RmfSubcategoryEntry,
    get_subcategories,
)

_FUNCTIONS = {"GOVERN", "MAP", "MEASURE", "MANAGE"}


class TestGetSubcategories:
    def test_returns_populated_dict(self):
        taxonomy = get_subcategories()
        assert taxonomy

    def test_total_is_72(self):
        """Matches AI RMF 1.0's publicly documented total (Tables 1-4)."""
        assert len(get_subcategories()) == 72

    def test_every_entry_has_required_shape(self):
        for subcat_id, entry in get_subcategories().items():
            assert isinstance(entry, RmfSubcategoryEntry)
            assert entry.id == subcat_id
            assert entry.function in _FUNCTIONS
            assert entry.category
            assert entry.category_title
            assert entry.outcome
            assert entry.category.startswith(entry.function)
            assert subcat_id.startswith(entry.category)

    def test_all_four_functions_present(self):
        functions = {entry.function for entry in get_subcategories().values()}
        assert functions == _FUNCTIONS

    def test_function_counts_match_meta(self):
        """Cross-checked against two independent NIST AIRC fetches at
        research time (see the data file's `_meta.function_counts`)."""
        counts: dict[str, int] = {}
        for entry in get_subcategories().values():
            counts[entry.function] = counts.get(entry.function, 0) + 1
        assert counts == {"GOVERN": 19, "MAP": 18, "MEASURE": 22, "MANAGE": 13}

    def test_govern_1_1_known_outcome(self):
        entry = get_subcategories()["GOVERN 1.1"]
        assert "Legal and regulatory requirements" in entry.outcome

    def test_manage_4_3_known_outcome(self):
        entry = get_subcategories()["MANAGE 4.3"]
        assert "Incidents and errors are communicated" in entry.outcome


class TestMalformedTaxonomyFailsLoud:
    def _reload_from(self, monkeypatch, tmp_path, payload: dict):
        import opencomplai_core.nist_ai_rmf_subcategories as rmf_module

        data_path = tmp_path / "nist_ai_rmf_subcategories.json"
        data_path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(rmf_module, "_DATA_PATH", data_path)
        rmf_module.get_subcategories.cache_clear()
        return rmf_module

    def test_missing_outcome_raises(self, monkeypatch, tmp_path):
        rmf_module = self._reload_from(
            monkeypatch,
            tmp_path,
            {
                "subcategories": [
                    {
                        "id": "GOVERN 1.1",
                        "function": "GOVERN",
                        "category": "GOVERN 1",
                        "category_title": "test",
                        # outcome deliberately omitted
                    }
                ]
            },
        )
        with pytest.raises(ValueError, match="empty outcome"):
            rmf_module.get_subcategories()

    def test_category_function_mismatch_raises(self, monkeypatch, tmp_path):
        rmf_module = self._reload_from(
            monkeypatch,
            tmp_path,
            {
                "subcategories": [
                    {
                        "id": "GOVERN 1.1",
                        "function": "GOVERN",
                        "category": "MAP 1",
                        "category_title": "test",
                        "outcome": "test",
                    }
                ]
            },
        )
        with pytest.raises(ValueError, match="expected 'GOVERN 1'"):
            rmf_module.get_subcategories()

    def test_invalid_function_raises(self, monkeypatch, tmp_path):
        rmf_module = self._reload_from(
            monkeypatch,
            tmp_path,
            {
                "subcategories": [
                    {
                        "id": "BOGUS 1.1",
                        "function": "BOGUS",
                        "category": "BOGUS 1",
                        "category_title": "test",
                        "outcome": "test",
                    }
                ]
            },
        )
        with pytest.raises(ValueError, match="invalid function"):
            rmf_module.get_subcategories()

    def test_empty_subcategories_raises(self, monkeypatch, tmp_path):
        rmf_module = self._reload_from(monkeypatch, tmp_path, {"subcategories": []})
        with pytest.raises(ValueError, match="'subcategories' is missing or empty"):
            rmf_module.get_subcategories()

    def test_invalid_json_raises(self, monkeypatch, tmp_path):
        import opencomplai_core.nist_ai_rmf_subcategories as rmf_module

        data_path = tmp_path / "nist_ai_rmf_subcategories.json"
        data_path.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(rmf_module, "_DATA_PATH", data_path)
        rmf_module.get_subcategories.cache_clear()
        with pytest.raises(ValueError, match="invalid JSON"):
            rmf_module.get_subcategories()

    def test_recovers_after_restoring_real_data(self, monkeypatch, tmp_path):
        rmf_module = self._reload_from(monkeypatch, tmp_path, {"subcategories": []})
        with pytest.raises(ValueError, match="'subcategories' is missing or empty"):
            rmf_module.get_subcategories()

        monkeypatch.undo()
        rmf_module.get_subcategories.cache_clear()
        taxonomy = rmf_module.get_subcategories()
        assert taxonomy
