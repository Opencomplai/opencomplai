"""Unit tests for the framework-crosswalk loader (CP-5, D-3a).

Covers: crosswalk shape/coverage and the fail-loud contract mirrored from
`harmonised_standards.get_catalog()` / `control_catalog.get_catalog()` — a
malformed or missing data file raises `ValueError` rather than silently
degrading to an empty crosswalk. Also covers `control_catalog`'s best-effort
enrichment (a missing/broken crosswalk must never break control_catalog).
"""

from __future__ import annotations

import json

import pytest
from opencomplai_core.framework_crosswalk import CrosswalkEntry, get_crosswalk

_VALID_CONFIDENCES = {"low", "medium", "high"}


class TestGetCrosswalk:
    def test_returns_populated_dict(self):
        crosswalk = get_crosswalk()
        assert crosswalk

    def test_every_entry_has_required_shape(self):
        for article, entry in get_crosswalk().items():
            assert isinstance(entry, CrosswalkEntry)
            assert entry.eu_ai_act_article == article
            assert entry.iso_42001_clause
            assert entry.nist_ai_rmf_subcategory
            assert entry.source
            assert entry.confidence in _VALID_CONFIDENCES
            # Mandatory per epic CP-5: no row may be pre-certified.
            assert entry.needs_founder_review is True

    def test_art_9_and_art_17_are_covered(self):
        """Spot-check the two textbook-canonical rows (D-3a's confidence
        definitions call these "medium", not "low")."""
        crosswalk = get_crosswalk()
        assert crosswalk["Art. 9"].confidence == "medium"
        assert crosswalk["Art. 17"].confidence == "medium"

    def test_art_47_and_art_48_deliberately_uncovered(self):
        """EU declaration of conformity / CE marking have no ISO/IEC 42001 or
        NIST AI RMF equivalent — no fabricated row for either (see the data
        file's `_meta.not_covered`)."""
        crosswalk = get_crosswalk()
        assert "Art. 47" not in crosswalk
        assert "Art. 48" not in crosswalk


class TestMalformedCrosswalkFailsLoud:
    def _reload_from(self, monkeypatch, tmp_path, payload: dict):
        import opencomplai_core.framework_crosswalk as fc_module

        data_path = tmp_path / "framework_crosswalk.json"
        data_path.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(fc_module, "_DATA_PATH", data_path)
        fc_module.get_crosswalk.cache_clear()
        return fc_module

    def test_missing_confidence_raises(self, monkeypatch, tmp_path):
        fc_module = self._reload_from(
            monkeypatch,
            tmp_path,
            {
                "rows": [
                    {
                        "eu_ai_act_article": "Art. 9",
                        "iso_42001_clause": "Clause 6.1",
                        "nist_ai_rmf_subcategory": "GOVERN 1",
                        "source": "iso_42001",
                        "needs_founder_review": True,
                        # confidence deliberately omitted
                    }
                ]
            },
        )
        with pytest.raises(ValueError, match="invalid confidence"):
            fc_module.get_crosswalk()

    def test_needs_founder_review_false_raises(self, monkeypatch, tmp_path):
        fc_module = self._reload_from(
            monkeypatch,
            tmp_path,
            {
                "rows": [
                    {
                        "eu_ai_act_article": "Art. 9",
                        "iso_42001_clause": "Clause 6.1",
                        "nist_ai_rmf_subcategory": "GOVERN 1",
                        "source": "iso_42001",
                        "confidence": "low",
                        "needs_founder_review": False,
                    }
                ]
            },
        )
        with pytest.raises(ValueError, match="needs_founder_review=true"):
            fc_module.get_crosswalk()

    def test_empty_rows_raises(self, monkeypatch, tmp_path):
        fc_module = self._reload_from(monkeypatch, tmp_path, {"rows": []})
        with pytest.raises(ValueError, match="'rows' is missing or empty"):
            fc_module.get_crosswalk()

    def test_invalid_json_raises(self, monkeypatch, tmp_path):
        import opencomplai_core.framework_crosswalk as fc_module

        data_path = tmp_path / "framework_crosswalk.json"
        data_path.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(fc_module, "_DATA_PATH", data_path)
        fc_module.get_crosswalk.cache_clear()
        with pytest.raises(ValueError, match="invalid JSON"):
            fc_module.get_crosswalk()

    def test_recovers_after_restoring_real_data(self, monkeypatch, tmp_path):
        fc_module = self._reload_from(monkeypatch, tmp_path, {"rows": []})
        with pytest.raises(ValueError, match="'rows' is missing or empty"):
            fc_module.get_crosswalk()

        monkeypatch.undo()
        fc_module.get_crosswalk.cache_clear()
        crosswalk = fc_module.get_crosswalk()
        assert crosswalk


class TestControlCatalogEnrichment:
    """control_catalog attaches crosswalk references per article (CP-5 task 3)."""

    def test_art_9_has_iso_and_nist_references(self):
        from opencomplai_core.control_catalog import get_catalog

        entry = get_catalog()["Art. 9"]
        assert entry.iso_42001_clause
        assert entry.nist_ai_rmf_subcategory

    def test_art_47_has_no_reference_since_crosswalk_has_no_row(self):
        from opencomplai_core.control_catalog import get_catalog

        entry = get_catalog()["Art. 47"]
        assert entry.iso_42001_clause is None
        assert entry.nist_ai_rmf_subcategory is None

    def test_broken_crosswalk_degrades_to_no_references_not_an_exception(
        self, monkeypatch
    ):
        """Best-effort contract: control_catalog must stay usable even if the
        crosswalk module fails to import/load (mirrors the doc-generator's
        best-effort harmonised-standards lookup)."""
        import opencomplai_core.control_catalog as cc_module

        def _boom():
            raise ValueError("simulated crosswalk failure")

        monkeypatch.setattr("opencomplai_core.framework_crosswalk.get_crosswalk", _boom)
        enriched = cc_module._with_crosswalk_references(
            {"Art. 9": cc_module.ControlCatalogEntry(title="x", default_ttl_days=1)}
        )
        assert enriched["Art. 9"].iso_42001_clause is None
