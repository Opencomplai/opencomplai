"""Unit tests for the CTRL-MODEL control instance domain model.

Covers: deterministic control_id, manifest fingerprint stability/sensitivity,
and control catalog coverage of every article emitted by gap_report.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.control_catalog import (
    CONTROL_CATALOG,
    ControlCatalogEntry,
    get_catalog,
)
from opencomplai_core.control_identity import (
    WATCHED_MANIFEST_FIELDS,
    fingerprint_manifest,
    make_control_id,
)
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.gap_report import load_gap_article_map
from opencomplai_core.models import ControlInstance, ControlState, SystemManifest

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).parent
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)


def _manifest_kwargs(**overrides: object) -> dict:
    base: dict[str, object] = {
        "system_id": "sys-1",
        "intended_purpose": "credit scoring",
        "compliance_target": "EU_AI_ACT",
        "high_risk_presumption": True,
        "commit_ref": "abc123",
        "training_data_description": "internal loan applications 2018-2024",
        "model_architecture": "gradient boosted trees",
        "operator_role": "provider",
    }
    base.update(overrides)
    return base


class TestMakeControlId:
    def test_deterministic_across_calls(self):
        id1 = make_control_id("tenant-a", "sys-1", "Art. 9")
        id2 = make_control_id("tenant-a", "sys-1", "Art. 9")
        assert id1 == id2

    def test_differs_when_any_component_differs(self):
        base = make_control_id("tenant-a", "sys-1", "Art. 9")
        assert base != make_control_id("tenant-b", "sys-1", "Art. 9")
        assert base != make_control_id("tenant-a", "sys-2", "Art. 9")
        assert base != make_control_id("tenant-a", "sys-1", "Art. 10")

    def test_length_is_32(self):
        control_id = make_control_id("tenant-a", "sys-1", "Art. 9")
        assert len(control_id) == 32


class TestFingerprintManifest:
    def test_stable_under_field_reordering(self):
        kwargs = _manifest_kwargs()
        reordered_kwargs = dict(reversed(list(kwargs.items())))

        manifest_a = SystemManifest(**kwargs)
        manifest_b = SystemManifest(**reordered_kwargs)

        assert fingerprint_manifest(manifest_a) == fingerprint_manifest(manifest_b)

    def test_stable_under_dict_key_reordering(self):
        kwargs = _manifest_kwargs()
        reordered_kwargs = dict(reversed(list(kwargs.items())))

        assert fingerprint_manifest(kwargs) == fingerprint_manifest(reordered_kwargs)

    def test_changes_on_watched_field_edit(self):
        manifest_a = SystemManifest(**_manifest_kwargs())
        manifest_b = SystemManifest(
            **_manifest_kwargs(model_architecture="transformer")
        )

        assert fingerprint_manifest(manifest_a) != fingerprint_manifest(manifest_b)

    def test_changes_when_high_risk_presumption_flips(self):
        manifest_a = SystemManifest(**_manifest_kwargs(high_risk_presumption=True))
        manifest_b = SystemManifest(**_manifest_kwargs(high_risk_presumption=False))

        assert fingerprint_manifest(manifest_a) != fingerprint_manifest(manifest_b)

    def test_unchanged_on_non_watched_field_edit(self):
        manifest_a = SystemManifest(**_manifest_kwargs())
        manifest_b = SystemManifest(**_manifest_kwargs(commit_ref="def456"))

        assert fingerprint_manifest(manifest_a) == fingerprint_manifest(manifest_b)

    def test_unchanged_when_only_known_limitations_edited(self):
        manifest_a = SystemManifest(**_manifest_kwargs())
        manifest_b = SystemManifest(
            **_manifest_kwargs(), known_limitations=["edge case X"]
        )

        assert fingerprint_manifest(manifest_a) == fingerprint_manifest(manifest_b)

    def test_watched_fields_all_present_on_system_manifest(self):
        manifest = SystemManifest(**_manifest_kwargs())
        dumped = manifest.model_dump()
        for field in WATCHED_MANIFEST_FIELDS:
            assert field in dumped


class TestControlCatalog:
    def test_catalog_covers_every_gap_article(self):
        article_map = load_gap_article_map()
        catalog = get_catalog()
        missing = set(article_map.keys()) - set(catalog.keys())
        assert not missing, f"control_catalog is missing articles: {sorted(missing)}"

    def test_get_catalog_returns_populated_dict(self):
        catalog = get_catalog()
        assert catalog
        assert catalog is CONTROL_CATALOG

    def test_every_entry_has_title_and_ttl_shape(self):
        for entry in get_catalog().values():
            assert isinstance(entry, ControlCatalogEntry)
            assert isinstance(entry.title, str)
            assert entry.title
            assert entry.default_ttl_days is None or entry.default_ttl_days > 0

    def test_malformed_catalog_fails_loud(self, monkeypatch):
        import opencomplai_core.control_catalog as catalog_module

        monkeypatch.setattr(catalog_module, "CONTROL_CATALOG", {})
        try:
            catalog_module.get_catalog()
            raise AssertionError("expected ValueError on empty catalog")
        except ValueError:
            pass

    def test_native_framework_pack_requirements_join_the_catalog(self, monkeypatch):
        monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)
        catalog = get_catalog()

        assert catalog is not CONTROL_CATALOG
        assert catalog["FIXTURE:REQ-1"] == ControlCatalogEntry(
            "Risk register maintained", 180
        )
        assert catalog["FIXTURE:REQ-2"] == ControlCatalogEntry(
            "Governance policy approved", None
        )
        assert catalog["FIXTURE:REQ-3"].default_ttl_days == 365
        assert {k: v for k, v in catalog.items() if ":" not in k} == CONTROL_CATALOG
        assert "FIXTURE:REQ-1" not in CONTROL_CATALOG

    def test_malformed_framework_pack_entry_fails_loud(self, monkeypatch, tmp_path):
        requirements = tmp_path / "requirements.json"
        requirements.write_text(
            json.dumps({"BAD:REQ-1": {"title": "Bad", "default_ttl_days": 0}}),
            encoding="utf-8",
        )
        monkeypatch.setitem(
            FRAMEWORKS, "BAD", FrameworkPack("BAD", "Bad", requirements=requirements)
        )
        with pytest.raises(ValueError, match="BAD:REQ-1"):
            get_catalog()


class TestControlInstance:
    def test_round_trip(self):
        control_id = make_control_id("tenant-a", "sys-1", "Art. 9")
        instance = ControlInstance(
            control_id=control_id,
            tenant_id="tenant-a",
            system_id="sys-1",
            obligation_id="Art. 9",
            article_ref="Art. 9",
            owner=None,
            state=ControlState.EVIDENCE_MISSING,
            evidence_refs=[],
            ttl_days=None,
            last_assessed_at=None,
            last_evidence_at=None,
            due_at=None,
            waiver_rationale=None,
        )
        assert instance.control_id == control_id
        assert instance.state == ControlState.EVIDENCE_MISSING

    def test_all_states_are_valid(self):
        expected = {
            "satisfied",
            "evidence_missing",
            "evidence_stale",
            "pending_review",
            "waived",
        }
        assert {s.value for s in ControlState} == expected
