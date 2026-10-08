"""Structured human_oversight manifest block and its Art. 14 / Art. 12 sources."""

from __future__ import annotations

import hashlib
import json

import pytest
from opencomplai_core.control_assessment import derive_controls
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.control_identity import fingerprint_manifest, make_control_id
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.manifest_sources import (
    MANIFEST_SOURCE_REFS,
    NEEDS_REVIEW_NOTES,
    manifest_gap_status,
    oversight_warnings,
)
from opencomplai_core.models import (
    ArticleGapSource,
    ControlInstance,
    ControlState,
    CorroborationReport,
    GapStatus,
    SystemManifest,
)
from pydantic import ValidationError

_BASE = {
    "system_id": "sys-1",
    "intended_purpose": "credit scoring",
    "compliance_target": "EU_AI_ACT",
    "high_risk_presumption": True,
    "commit_ref": "abc123",
    "training_data_description": "internal loan applications 2018-2024",
    "model_architecture": "gradient boosted trees",
    "operator_role": "provider",
}
_BLOCK = {
    "roles": [
        {
            "role": "Credit officer",
            "authority": "May override any score",
            "can_intervene": True,
            "conditions": ["score below 300"],
            "training_ref": "docs/training.md",
        },
        {"role": "Risk lead", "can_intervene": False, "training_ref": "docs/t2.md"},
    ],
    "escalation": "Risk lead, then board",
    "evidence_refs": ["docs/oversight.md"],
}
_NOW = "2026-08-17T00:00:00+00:00"


def _manifest(**extra) -> SystemManifest:
    return SystemManifest(**{**_BASE, **extra})


def _art14(report):
    return next(r for r in report.articles if r.article == "Art. 14")


def _art12(report):
    return next(r for r in report.articles if r.article == "Art. 12")


def _rows(report):
    return {r.article: r.model_dump() for r in report.articles}


def _scan_report() -> CorroborationReport:
    return CorroborationReport.model_validate(
        {
            "scan_id": "scan-1",
            "system_id": "sys-1",
            "commit_ref": "HEAD",
            "scanner_version": "0.1.0",
            "input_digest": "sha256:abc",
            "config_hash": "sha256:def",
            "detector_versions": {},
            "declared_purpose": "credit scoring",
            "declared_categories": [],
            "evidence": [],
            "findings": [
                {
                    "finding_id": "find_1",
                    "signal_category": "agent_framework",
                    "evidence_ids": [],
                    "locations": ["src/model.py:1"],
                    "mapped_taxonomy": [],
                    "strength": 1.0,
                    "scope": "prod",
                    "reachability": "reachable_entrypoint",
                    "confidence_rationale": [],
                    "reviewer_prompt": "",
                }
            ],
            "detected_categories": [],
            "discrepancies": [],
            "score_breakdown": {},
            "severity": "none",
            "feature_summary": {},
            "cache_summary": {},
            "skipped_paths": [],
            "limits_hit": [],
            "warnings": [],
            "detector_errors": [],
            "baseline_ref": None,
            "generated_at": "2026-07-11T00:00:00Z",
            "report_hash": "sha256:ghi",
        }
    )


# --- model -----------------------------------------------------------------


def test_manifest_without_oversight_serialises_to_identical_bytes():
    manifest = _manifest()
    assert "human_oversight" not in manifest.model_dump()
    assert "human_oversight" not in manifest.model_dump(mode="json")
    assert "human_oversight" not in json.loads(manifest.model_dump_json())
    assert '"human_oversight":' not in manifest.model_dump_json()


def test_oversight_round_trips_through_json():
    manifest = _manifest(human_oversight=_BLOCK)
    again = SystemManifest.model_validate_json(manifest.model_dump_json())
    assert again == manifest
    dumped = json.loads(manifest.model_dump_json())["human_oversight"]
    assert dumped["roles"][0] == _BLOCK["roles"][0]
    assert dumped["roles"][1]["authority"] is None
    assert dumped["escalation"] == "Risk lead, then board"
    assert dumped["evidence_refs"] == ["docs/oversight.md"]


def test_block_rejects_empty_roles():
    with pytest.raises(ValidationError):
        _manifest(human_oversight={"roles": []})


def test_oversight_rejects_duplicate_roles_ignoring_case():
    roles = [{"role": "Officer"}, {"role": "  officer "}]
    with pytest.raises(ValidationError, match="duplicate oversight role"):
        _manifest(human_oversight={"roles": roles})


def test_oversight_rejects_unknown_keys_and_blank_role():
    with pytest.raises(ValidationError):
        _manifest(human_oversight={"roles": [{"role": "A"}], "owner": "x"})
    with pytest.raises(ValidationError):
        _manifest(human_oversight={"roles": [{"role": "A", "nope": 1}]})
    with pytest.raises(ValidationError):
        _manifest(human_oversight={"roles": [{"role": ""}]})


# --- manifest source -------------------------------------------------------


def test_structured_oversight_gives_partial_art14_row(tmp_path):
    report = build_gap_report(
        "sys-1", "HEAD", repo_root=tmp_path, manifest=_manifest(human_oversight=_BLOCK)
    )
    row = _art14(report)
    assert row.source == ArticleGapSource.MANIFEST
    assert row.status == GapStatus.PARTIAL
    assert row.evidence_ref == "manifest:human_oversight_declaration"
    assert "2 role(s), 1 with authority to intervene" in row.rationale
    assert "escalation path declared" in row.rationale


def test_art14_never_met_from_manifest(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "human_oversight.md").write_text("oversight", "utf-8")
    manifest = _manifest(human_oversight=_BLOCK)
    for repo in (tmp_path, None):
        for scan in (None, _scan_report()):
            report = build_gap_report(
                "sys-1",
                "HEAD",
                corroboration_report=scan,
                repo_root=repo,
                manifest=manifest,
            )
            assert _art14(report).status != GapStatus.MET
    direct = manifest_gap_status("human_oversight_declaration", manifest)
    assert direct is not None
    assert direct.status == GapStatus.PARTIAL


def test_legacy_measures_only_manifest_behaves_as_before(tmp_path):
    legacy = _manifest(human_oversight_measures=["A human reviews every decision"])
    plain = build_gap_report("sys-1", "HEAD", repo_root=tmp_path)
    with_manifest = build_gap_report(
        "sys-1", "HEAD", repo_root=tmp_path, manifest=legacy
    )
    a, b = plain.model_dump(), with_manifest.model_dump()
    a["generated_at"] = b["generated_at"] = ""
    assert a == b
    assert manifest_gap_status("human_oversight_declaration", legacy) is None


def test_unknown_ref_and_absent_block_yield_no_candidate():
    assert manifest_gap_status("no_such_ref", _manifest(human_oversight=_BLOCK)) is None
    assert manifest_gap_status("human_oversight_declaration", _manifest()) is None


def test_needs_review_note_is_flagged():
    assert NEEDS_REVIEW_NOTES
    for ref, note in NEEDS_REVIEW_NOTES.items():
        assert ref in MANIFEST_SOURCE_REFS
        assert note["source"]
        assert note["confidence"]
        assert note["note"]
        assert note["needs_founder_review"] is True


def test_warnings_when_no_role_can_intervene():
    assert oversight_warnings(_manifest()) == []
    block = {"roles": [{"role": "Observer", "training_ref": "t.md"}]}
    manifest = _manifest(human_oversight=block)
    assert oversight_warnings(manifest) == [
        "human_oversight: no declared role can intervene"
    ]
    row = manifest_gap_status("human_oversight_declaration", manifest)
    assert "No declared role can intervene." in row.rationale
    untrained = {"roles": [{"role": "A", "can_intervene": True}]}
    assert oversight_warnings(_manifest(human_oversight=untrained)) == [
        "human_oversight: role 'A' has no training_ref"
    ]


# --- gap report dispatch ---------------------------------------------------


def test_declaration_supersedes_only_artifact_missing(tmp_path):
    manifest = _manifest(human_oversight=_BLOCK)
    empty = build_gap_report("sys-1", "HEAD", repo_root=tmp_path, manifest=manifest)
    assert _art14(empty).source == ArticleGapSource.MANIFEST
    assert _art14(empty).status == GapStatus.PARTIAL

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "human_oversight.md").write_text("oversight", "utf-8")
    plain = build_gap_report("sys-1", "HEAD", repo_root=tmp_path)
    assert _art14(plain).status == GapStatus.PARTIAL
    with_block = build_gap_report(
        "sys-1", "HEAD", repo_root=tmp_path, manifest=manifest
    )
    assert _art14(with_block).source == ArticleGapSource.ARTIFACT  # tie: first wins
    assert _art14(with_block).model_dump() == _art14(plain).model_dump()


def test_manifest_row_is_art14_in_full_report_and_only_there(tmp_path):
    base = build_gap_report("sys-1", "HEAD", repo_root=tmp_path, manifest=_manifest())
    with_block = build_gap_report(
        "sys-1", "HEAD", repo_root=tmp_path, manifest=_manifest(human_oversight=_BLOCK)
    )
    a, b = _rows(base), _rows(with_block)
    assert [k for k in a if a[k] != b[k]] == ["Art. 14"]


def test_scan_unverified_does_not_mask_declaration():
    report = build_gap_report(
        "sys-1",
        "HEAD",
        corroboration_report=_scan_report(),
        manifest=_manifest(human_oversight=_BLOCK),
    )
    assert _art14(report).source == ArticleGapSource.MANIFEST
    assert _art14(report).status == GapStatus.PARTIAL
    no_block = build_gap_report("sys-1", "HEAD", corroboration_report=_scan_report())
    assert _art14(no_block).source != ArticleGapSource.MANIFEST
    assert _art14(no_block).status == GapStatus.UNVERIFIED


def test_record_keeping_declaration_feeds_art12(tmp_path):
    declared = _manifest(
        record_keeping={"logging_enabled": True, "log_retention_days": 180}
    )
    report = build_gap_report("sys-1", "HEAD", repo_root=tmp_path, manifest=declared)
    row = _art12(report)
    assert row.source == ArticleGapSource.MANIFEST
    assert row.status == GapStatus.PARTIAL
    assert row.evidence_ref == "manifest:record_keeping_declaration"
    plain = build_gap_report("sys-1", "HEAD", repo_root=tmp_path, manifest=_manifest())
    assert _art12(plain).source != ArticleGapSource.MANIFEST
    assert _art12(plain).status == GapStatus.MISSING


# --- fingerprint -----------------------------------------------------------

# Fingerprint of _BASE computed by the function before this block existed.
_PINNED_FINGERPRINT = "d2571a2508d43b73bbf9571ebb4a09398b615687749dbe8088cbca420b632f93"


def test_fingerprint_unchanged_without_block():
    subset = {
        k: _BASE[k]
        for k in (
            "intended_purpose",
            "model_architecture",
            "high_risk_presumption",
            "training_data_description",
            "operator_role",
        )
    }
    oracle = hashlib.sha256(
        json.dumps(subset, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert fingerprint_manifest(_manifest()) == oracle == _PINNED_FINGERPRINT


def test_fingerprint_changes_with_block():
    base = fingerprint_manifest(_manifest())
    first = fingerprint_manifest(_manifest(human_oversight=_BLOCK))
    edited = json.loads(json.dumps(_BLOCK))
    edited["roles"][1]["can_intervene"] = True
    second = fingerprint_manifest(_manifest(human_oversight=edited))
    assert len({base, first, second}) == 3


# --- controls --------------------------------------------------------------


def test_manual_evidence_survives_manifest_partial_row(tmp_path):
    manifest = _manifest(human_oversight=_BLOCK)
    report = build_gap_report("sys-1", "HEAD", repo_root=tmp_path, manifest=manifest)
    assert _art14(report).source == ArticleGapSource.MANIFEST
    existing = ControlInstance(
        control_id=make_control_id("tenant-a", "sys-1", "Art. 14"),
        tenant_id="tenant-a",
        system_id="sys-1",
        obligation_id="Art. 14",
        article_ref="Art. 14",
        owner="compliance-team",
        state=ControlState.SATISFIED,
        evidence_refs=["sha256:manual-evidence-hash"],
        ttl_days=None,
        last_assessed_at=_NOW,
        last_evidence_at=_NOW,
        due_at=None,
        waiver_rationale=None,
    )
    derived = derive_controls(
        report, manifest, get_catalog(), [existing], tenant_id="tenant-a", now=_NOW
    )
    control = next(c for c in derived if c.obligation_id == "Art. 14")
    assert control.state == ControlState.SATISFIED
    assert control.evidence_refs == existing.evidence_refs
