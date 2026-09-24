"""evaluate_targets and gate_failures: several frameworks side by side.

The EU AI Act entry must equal today's build_gap_report output exactly.
The test-only FIXTURE native pack (registered per test) proves the generic
path end to end: artifact rows, an attested row and an excluded row.
NIST AI RMF rows are derived from the EU evidence and prefixed.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from opencomplai_core import gap_report as gap_report_module
from opencomplai_core.engine import assess
from opencomplai_core.eval_engine import run_evals
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    FrameworkPack,
    data_version,
    evaluate_targets,
    gate_failures,
    validate_gate,
)
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    AssessmentInput,
    Attestation,
    ConfidenceLabel,
    CorroborationReport,
    EvalSampleSet,
    FrameworkInputs,
    FrameworkReport,
    GapReport,
    GapStatus,
    ModelMetadata,
    SystemManifest,
)
from opencomplai_core.nist_rmf_report import build_nist_rmf_report

FIXTURE_PACK = FrameworkPack(
    "FIXTURE",
    "Fixture framework",
    requirements=Path(__file__).parent
    / "fixtures"
    / "framework_pack"
    / "requirements.json",
)

RISK_REGISTER = (
    "# Risk register\n\nIdentified risks: biased scoring.\n"
    "Mitigation: quarterly fairness review; residual risk accepted.\n"
)

ATTESTATION = Attestation(
    statement="The board approved the AI governance policy.",
    attested_by="jane@example.com",
    attested_at="2026-09-01",
)


@pytest.fixture
def fixture_pack(monkeypatch):
    monkeypatch.setitem(FRAMEWORKS, "FIXTURE", FIXTURE_PACK)


@pytest.fixture
def frozen_now(monkeypatch):
    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 23, tzinfo=UTC)

    monkeypatch.setattr(gap_report_module, "datetime", _Frozen)


def _manifest(**inputs: FrameworkInputs) -> SystemManifest:
    return SystemManifest(
        system_id="sys", intended_purpose="credit scoring", framework_inputs=inputs
    )


def _rows(framework_report: FrameworkReport) -> dict[str, ArticleGapStatus]:
    return {row.article: row for row in framework_report.report.articles}


def _run_inputs() -> dict[str, object]:
    """A rule failure, an undeclared scan finding and a failing evaluator,
    shaped like the inputs `gaps` and `check` pass (see test_gap_report.py)."""
    risk_result = assess(
        AssessmentInput(
            model=ModelMetadata(
                name="test-model",
                version="1.0.0",
                modality="text",
                use_case="employment screening and ranking",
                deployment_context="local",
            )
        )
    )
    corroboration_report = CorroborationReport.model_validate(
        {
            "scan_id": "scan-1",
            "system_id": "sys",
            "commit_ref": "abc",
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
                    "signal_category": "pii_dataflow",
                    "evidence_ids": [],
                    "locations": ["src/model.py:1"],
                    "mapped_taxonomy": ["essential_services"],
                    "strength": 1.0,
                    "scope": "prod",
                    "reachability": "reachable_entrypoint",
                    "confidence_rationale": [],
                    "reviewer_prompt": "",
                }
            ],
            "detected_categories": ["essential_services"],
            "discrepancies": ["essential_services"],
            "score_breakdown": {},
            "severity": "major",
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
    eval_report = run_evals(
        "sys",
        "abc",
        EvalSampleSet(
            eval_set_id="s1",
            system_id="sys",
            commit_ref="abc",
            outputs=["this contains kill instructions"],
        ),
    )
    return {
        "risk_result": risk_result,
        "corroboration_report": corroboration_report,
        "eval_report": eval_report,
    }


# --- EU AI Act: exactly today's gap report -----------------------------------


def test_eu_entry_is_exactly_build_gap_report(frozen_now, tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "risk_register.md").write_text(RISK_REGISTER, encoding="utf-8")

    reports = evaluate_targets(
        _manifest(), [EU_AI_ACT], commit_ref="abc", repo_root=tmp_path
    )

    assert list(reports) == [EU_AI_ACT]
    eu = reports[EU_AI_ACT]
    assert eu.report == build_gap_report(
        system_id="sys", commit_ref="abc", repo_root=tmp_path
    )
    assert eu.label == FRAMEWORKS[EU_AI_ACT].label
    assert eu.disclaimer_ref == "DISCLAIMER_V1"
    assert eu.derived_from is None
    assert eu.data_version == data_version(FRAMEWORKS[EU_AI_ACT])
    assert eu.excluded == {}
    assert eu.gated is False


def test_eu_entry_passes_every_run_input_to_build_gap_report(frozen_now):
    inputs = _run_inputs()

    eu = evaluate_targets(_manifest(), [EU_AI_ACT], commit_ref="abc", **inputs)[
        EU_AI_ACT
    ].report

    assert eu == build_gap_report(system_id="sys", commit_ref="abc", **inputs)
    for name in inputs:  # each input changes the report, so each must reach it
        assert eu != build_gap_report(
            system_id="sys", commit_ref="abc", **{**inputs, name: None}
        ), name


def test_native_pack_sees_the_scan_and_eval_inputs(monkeypatch, tmp_path: Path):
    requirements = tmp_path / "requirements.json"
    requirements.write_text(
        json.dumps(
            {
                "FIXTURE:SCAN": {
                    "title": "Personal data flows declared",
                    "default_ttl_days": None,
                    "sources": [{"kind": "scan", "ref": "pii_dataflow"}],
                },
                "FIXTURE:EVAL": {
                    "title": "Outputs are safe",
                    "default_ttl_days": None,
                    "sources": [{"kind": "evaluator", "ref": "EVAL_SAFETY_LEXICAL_V1"}],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(
        FRAMEWORKS,
        "FIXTURE",
        FrameworkPack("FIXTURE", "Fixture framework", requirements=requirements),
    )
    inputs = _run_inputs()

    rows = _rows(
        evaluate_targets(_manifest(), ["FIXTURE"], commit_ref="abc", **inputs)[
            "FIXTURE"
        ]
    )

    assert rows["FIXTURE:SCAN"].status == GapStatus.MISSING
    assert rows["FIXTURE:SCAN"].source == ArticleGapSource.SCAN
    assert rows["FIXTURE:SCAN"].evidence_ref == "find_1"
    assert rows["FIXTURE:EVAL"].status == GapStatus.MISSING
    assert rows["FIXTURE:EVAL"].source == ArticleGapSource.EVALUATOR
    assert rows["FIXTURE:EVAL"].evidence_ref == next(
        r.evidence_hash
        for r in inputs["eval_report"].results
        if r.evaluator_id == "EVAL_SAFETY_LEXICAL_V1"
    )


def test_eu_entry_comes_first_even_when_not_a_target():
    reports = evaluate_targets(_manifest(), ["NIST_AI_RMF"], commit_ref="abc")
    assert list(reports) == [EU_AI_ACT, "NIST_AI_RMF"]


# --- FIXTURE native pack, end to end -----------------------------------------


def test_fixture_pack_end_to_end(fixture_pack, tmp_path: Path):
    manifest = _manifest(
        FIXTURE=FrameworkInputs(
            excluded={"FIXTURE:REQ-3": "No deployers: the system is internal only."},
            attested={"FIXTURE:REQ-2": ATTESTATION},
        )
    )

    empty = evaluate_targets(
        manifest, [EU_AI_ACT, "FIXTURE"], commit_ref="abc", repo_root=tmp_path
    )
    assert list(empty) == [EU_AI_ACT, "FIXTURE"]
    fixture = empty["FIXTURE"]
    assert list(_rows(fixture)) == ["FIXTURE:REQ-1", "FIXTURE:REQ-2"]
    assert _rows(fixture)["FIXTURE:REQ-1"].status == GapStatus.MISSING
    assert fixture.excluded == {
        "FIXTURE:REQ-3": "No deployers: the system is internal only."
    }
    assert fixture.label == "Fixture framework"
    assert fixture.derived_from is None
    assert fixture.disclaimer_ref == "DISCLAIMER_V2"
    assert fixture.data_version == data_version(FIXTURE_PACK)
    assert all(row.disclaimer_ref == "DISCLAIMER_V2" for row in fixture.report.articles)

    attested = _rows(fixture)["FIXTURE:REQ-2"]
    assert attested.status == GapStatus.MET
    assert attested.source == ArticleGapSource.ATTESTATION
    assert attested.confidence is None
    assert attested.confidence_label == ConfidenceLabel.ATTESTED
    assert attested.evidence_ref == "attestation:jane@example.com@2026-09-01"
    assert attested.rationale == ATTESTATION.statement

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "risk_register.md").write_text(RISK_REGISTER, encoding="utf-8")
    with_register = evaluate_targets(
        manifest, [EU_AI_ACT, "FIXTURE"], commit_ref="abc", repo_root=tmp_path
    )
    assert _rows(with_register["FIXTURE"])["FIXTURE:REQ-1"].status in {
        GapStatus.PARTIAL,
        GapStatus.MET,
    }


def test_fixture_requirement_without_attestation_is_unverified(fixture_pack):
    reports = evaluate_targets(_manifest(), ["FIXTURE"], commit_ref="abc")
    row = _rows(reports["FIXTURE"])["FIXTURE:REQ-2"]
    assert row.status == GapStatus.UNVERIFIED
    assert row.source == ArticleGapSource.ATTESTATION
    assert row.confidence_label == ConfidenceLabel.NOT_ASSESSED
    assert "framework_inputs.FIXTURE.attested" in row.rationale


def test_fixture_does_not_change_the_eu_report(fixture_pack, frozen_now):
    manifest = _manifest(
        FIXTURE=FrameworkInputs(attested={"FIXTURE:REQ-2": ATTESTATION})
    )
    alone = evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc")
    together = evaluate_targets(manifest, [EU_AI_ACT, "FIXTURE"], commit_ref="abc")
    assert together[EU_AI_ACT] == alone[EU_AI_ACT]


# --- NIST AI RMF, derived from the EU evidence -------------------------------


def test_nist_rows_are_derived_and_prefixed():
    reports = evaluate_targets(
        _manifest(), [EU_AI_ACT, "NIST_AI_RMF"], commit_ref="abc"
    )
    nist = reports["NIST_AI_RMF"]
    legacy = build_nist_rmf_report(reports[EU_AI_ACT].report)

    assert nist.derived_from == EU_AI_ACT
    assert nist.disclaimer_ref == "DISCLAIMER_V2"
    assert nist.label == FRAMEWORKS["NIST_AI_RMF"].label
    assert [row.article for row in nist.report.articles] == [
        f"NIST_AI_RMF:{row.subcategory}" for row in legacy.subcategories
    ]
    for row, legacy_row in zip(nist.report.articles, legacy.subcategories, strict=True):
        assert row.source == ArticleGapSource.CROSSWALK
        assert row.status == legacy_row.status
        assert row.confidence is None
        assert row.confidence_label == legacy_row.confidence_label
        assert row.disclaimer_ref == "DISCLAIMER_V2"
        assert row.evidence_ref == (
            ", ".join(legacy_row.source_eu_ai_act_articles) or "none"
        )
    assert any(row.evidence_ref != "none" for row in nist.report.articles)
    assert any(row.evidence_ref == "none" for row in nist.report.articles)


def test_nist_exclusion_moves_the_row():
    reason = "Third-party model; no in-house development."
    manifest = _manifest(
        NIST_AI_RMF=FrameworkInputs(excluded={"NIST_AI_RMF:MAP 2.1": reason})
    )
    nist = evaluate_targets(manifest, ["NIST_AI_RMF"], commit_ref="abc")["NIST_AI_RMF"]
    assert "NIST_AI_RMF:MAP 2.1" not in _rows(nist)
    assert nist.excluded == {"NIST_AI_RMF:MAP 2.1": reason}


# --- every ValueError path ---------------------------------------------------


def test_unknown_target_raises():
    with pytest.raises(ValueError, match="ISO_42001"):
        evaluate_targets(_manifest(), [EU_AI_ACT, "ISO_42001"], commit_ref="abc")


def test_eu_framework_inputs_raise():
    manifest = _manifest(EU_AI_ACT=FrameworkInputs(excluded={"Art. 9": "n/a"}))
    with pytest.raises(ValueError, match=r"framework_inputs\.EU_AI_ACT"):
        evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc")


def test_framework_inputs_for_an_unknown_framework_raise():
    manifest = _manifest(ISO_42001=FrameworkInputs(excluded={"ISO_42001:6.1": "n/a"}))
    with pytest.raises(ValueError, match="ISO_42001"):
        evaluate_targets(manifest, [EU_AI_ACT], commit_ref="abc")


def test_unknown_excluded_id_raises(fixture_pack):
    manifest = _manifest(FIXTURE=FrameworkInputs(excluded={"FIXTURE:REQ-9": "n/a"}))
    with pytest.raises(ValueError, match="FIXTURE:REQ-9"):
        evaluate_targets(manifest, ["FIXTURE"], commit_ref="abc")


@pytest.mark.parametrize(
    ("framework", "requirement_id"),
    [
        ("FIXTURE", "FIXTURE:REQ-9"),  # not a requirement
        ("FIXTURE", "FIXTURE:REQ-1"),  # a requirement with no attestation source
        ("NIST_AI_RMF", "NIST_AI_RMF:GOVERN 1.1"),  # derived packs take none
    ],
)
def test_unknown_attested_id_raises(fixture_pack, framework: str, requirement_id: str):
    manifest = _manifest(
        **{framework: FrameworkInputs(attested={requirement_id: ATTESTATION})}
    )
    with pytest.raises(ValueError, match=re.escape(f"attested: '{requirement_id}'")):
        evaluate_targets(manifest, [framework], commit_ref="abc")


def test_blank_exclusion_justification_raises(fixture_pack):
    manifest = _manifest(FIXTURE=FrameworkInputs(excluded={"FIXTURE:REQ-3": "   "}))
    with pytest.raises(ValueError, match="justification"):
        evaluate_targets(manifest, ["FIXTURE"], commit_ref="abc")


def test_inputs_for_a_framework_that_is_not_a_target_are_ignored(fixture_pack):
    manifest = _manifest(FIXTURE=FrameworkInputs(excluded={"FIXTURE:REQ-3": "n/a"}))
    reports = evaluate_targets(manifest, ["NIST_AI_RMF"], commit_ref="abc")
    assert list(reports) == [EU_AI_ACT, "NIST_AI_RMF"]


# --- gate_failures -----------------------------------------------------------


def _framework_report(
    framework: str, statuses: dict[str, GapStatus]
) -> FrameworkReport:
    return FrameworkReport(
        framework=framework,
        label=framework,
        data_version="0" * 12,
        disclaimer_ref="DISCLAIMER_V2",
        report=GapReport(
            system_id="sys",
            commit_ref="abc",
            generated_at="2026-09-23T00:00:00+00:00",
            articles=[
                ArticleGapStatus(
                    article=rid,
                    status=status,
                    source=ArticleGapSource.ARTIFACT,
                    evidence_ref="x",
                )
                for rid, status in statuses.items()
            ],
        ),
    )


GATE_REPORTS = {
    EU_AI_ACT: _framework_report(EU_AI_ACT, {"Art. 9": GapStatus.MISSING}),
    "FIXTURE": _framework_report(
        "FIXTURE",
        {
            "FIXTURE:REQ-1": GapStatus.PARTIAL,
            "FIXTURE:REQ-2": GapStatus.MISSING,
            "FIXTURE:REQ-4": GapStatus.UNVERIFIED,
            "FIXTURE:REQ-5": GapStatus.MET,
        },
    ),
    "NIST_AI_RMF": _framework_report(
        "NIST_AI_RMF",
        {
            "NIST_AI_RMF:GOVERN 1.1": GapStatus.MISSING,
            "NIST_AI_RMF:MAP 1.1": GapStatus.MET,
        },
    ),
}


def test_gate_fails_missing_rows_of_gated_frameworks_only():
    assert gate_failures(GATE_REPORTS, ["FIXTURE"], "missing") == ["FIXTURE:REQ-2"]
    assert gate_failures(GATE_REPORTS, [], "missing") == []


def test_gate_fail_on_partial_adds_partial_rows():
    assert gate_failures(GATE_REPORTS, ["FIXTURE"], "partial") == [
        "FIXTURE:REQ-1",
        "FIXTURE:REQ-2",
    ]


def test_gate_failures_follow_report_order():
    assert gate_failures(GATE_REPORTS, ["NIST_AI_RMF", "FIXTURE"], "missing") == [
        "FIXTURE:REQ-2",
        "NIST_AI_RMF:GOVERN 1.1",
    ]


def test_gate_ignores_excluded_rows(fixture_pack, tmp_path: Path):
    manifest = _manifest(FIXTURE=FrameworkInputs(excluded={"FIXTURE:REQ-1": "n/a"}))
    reports = evaluate_targets(
        manifest, ["FIXTURE"], commit_ref="abc", repo_root=tmp_path
    )
    assert gate_failures(reports, ["FIXTURE"], "partial") == ["FIXTURE:REQ-3"]


def test_gate_rejects_bad_fail_on_and_unassessed_frameworks():
    with pytest.raises(ValueError, match="fail_on"):
        gate_failures(GATE_REPORTS, ["FIXTURE"], "unverified")
    with pytest.raises(ValueError, match="ISO_42001"):
        gate_failures(GATE_REPORTS, ["ISO_42001"], "missing")
    with pytest.raises(ValueError, match="EU_AI_ACT"):
        gate_failures(GATE_REPORTS, [EU_AI_ACT, "FIXTURE"], "missing")


def test_validate_gate_needs_known_non_eu_targets(fixture_pack):
    targets = [EU_AI_ACT, "NIST_AI_RMF"]
    validate_gate(["NIST_AI_RMF"], "partial", targets)
    validate_gate([], "missing", [EU_AI_ACT])
    with pytest.raises(ValueError, match="unknown gated framework ISO_42001"):
        validate_gate(["ISO_42001"], "missing", targets)
    with pytest.raises(ValueError, match="not among the compliance targets: FIXTURE"):
        validate_gate(["FIXTURE"], "missing", targets)
    with pytest.raises(ValueError, match="EU_AI_ACT cannot be gated"):
        validate_gate([EU_AI_ACT], "missing", targets)
    with pytest.raises(ValueError, match="fail_on"):
        validate_gate([], "unverified", targets)
