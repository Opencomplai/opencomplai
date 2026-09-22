"""Unit tests for the harmonised-standards catalogue loader (CP-4).

Covers: catalogue shape/coverage and the fail-loud contract mirrored from
`control_catalog.get_catalog()` — a malformed or missing data file raises
`ValueError` rather than silently degrading to an empty catalogue.
"""

from __future__ import annotations

import json

import pytest
from opencomplai_core.harmonised_standards import (
    HarmonisedStandardEntry,
    get_catalog,
)

_VALID_STATUSES = {"harmonised", "published", "draft"}


class TestGetCatalog:
    def test_returns_populated_dict(self):
        catalog = get_catalog()
        assert catalog

    def test_every_entry_has_required_shape(self):
        for entry_id, entry in get_catalog().items():
            assert isinstance(entry, HarmonisedStandardEntry)
            assert entry.id == entry_id
            assert entry.title
            assert entry.status in _VALID_STATUSES
            assert entry.source_url.startswith(("http://", "https://"))
            assert entry.articles_covered
            assert all(a.strip() for a in entry.articles_covered)
            # Mandatory per epic CP-4: no row may be pre-certified.
            assert entry.needs_founder_review is True

    def test_no_row_is_marked_harmonised_without_review(self):
        # Every row ships needs_founder_review=True (enforced by the loader
        # itself), so this is really just documenting the invariant at the
        # catalogue-content level too.
        for entry in get_catalog().values():
            assert entry.needs_founder_review is True


class TestMalformedCatalogFailsLoud:
    """Spot-check: corrupt a row, confirm the loader raises, nothing silent."""

    def _reload_from(self, monkeypatch, tmp_path, payload: dict):
        import opencomplai_core.harmonised_standards as hs_module

        data_path = tmp_path / "harmonised_standards.json"
        data_path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(hs_module, "_DATA_PATH", data_path)
        hs_module.get_catalog.cache_clear()
        return hs_module

    def test_missing_status_raises(self, monkeypatch, tmp_path):
        hs_module = self._reload_from(
            monkeypatch,
            tmp_path,
            {
                "standards": [
                    {
                        "id": "EN-TEST",
                        "title": "Test standard",
                        "source_url": "https://example.org/en-test",
                        "articles_covered": ["Art. 9"],
                        "needs_founder_review": True,
                        # status deliberately omitted
                    }
                ]
            },
        )
        with pytest.raises(ValueError, match="invalid status"):
            hs_module.get_catalog()

    def test_needs_founder_review_false_raises(self, monkeypatch, tmp_path):
        hs_module = self._reload_from(
            monkeypatch,
            tmp_path,
            {
                "standards": [
                    {
                        "id": "EN-TEST",
                        "title": "Test standard",
                        "status": "draft",
                        "source_url": "https://example.org/en-test",
                        "articles_covered": ["Art. 9"],
                        "needs_founder_review": False,
                    }
                ]
            },
        )
        with pytest.raises(ValueError, match="needs_founder_review=true"):
            hs_module.get_catalog()

    def test_empty_standards_list_raises(self, monkeypatch, tmp_path):
        hs_module = self._reload_from(monkeypatch, tmp_path, {"standards": []})
        with pytest.raises(ValueError, match="'standards' is missing or empty"):
            hs_module.get_catalog()

    def test_invalid_json_raises(self, monkeypatch, tmp_path):
        import opencomplai_core.harmonised_standards as hs_module

        data_path = tmp_path / "harmonised_standards.json"
        data_path.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(hs_module, "_DATA_PATH", data_path)
        hs_module.get_catalog.cache_clear()
        with pytest.raises(ValueError, match="invalid JSON"):
            hs_module.get_catalog()

    def test_recovers_after_restoring_real_data(self, monkeypatch, tmp_path):
        """After a monkeypatched failure, clearing the cache and pointing
        back at the real module path must load cleanly again — confirms the
        malformed-row failure doesn't poison the module for later callers."""
        hs_module = self._reload_from(monkeypatch, tmp_path, {"standards": []})
        with pytest.raises(ValueError, match="'standards' is missing or empty"):
            hs_module.get_catalog()

        monkeypatch.undo()
        hs_module.get_catalog.cache_clear()
        catalog = hs_module.get_catalog()
        assert catalog
