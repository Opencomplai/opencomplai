"""The dossier's cybersecurity part (Annex IV point 2(h)) from the ISO/IEC 27090 report."""

from __future__ import annotations

import json
from collections import Counter

import jsonschema
import pytest
from opencomplai_core.dossier import CYBERSECURITY_LEAD_IN, AnnexIVDossier
from opencomplai_core.dossier_generator import generate_dossier
from opencomplai_core.dossier_render import render_markdown, render_pdf
from opencomplai_core.dossier_verify import verify_dossier
from opencomplai_core.engine import assess
from opencomplai_core.frameworks import EU_AI_ACT, ISO_27090, evaluate_targets
from opencomplai_core.json_schemas import build_dossier_schema
from opencomplai_core.models import (
    AssessmentInput,
    Attestation,
    EvalReport,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
    FrameworkInputs,
    GapStatus,
    ModelMetadata,
    SystemManifest,
)

ISO = ISO_27090


@pytest.fixture(autouse=True)
def _clean_signing_env(monkeypatch):
    for name in (
        "DOSSIER_SIGNING_KEY_PATH",
        "LOCAL_SIGNING_KEY_PATH",
        "SIGNING_KEY_PRIVATE",
    ):
        monkeypatch.delenv(name, raising=False)


def _risk_result():
    return assess(
        AssessmentInput(
            model=ModelMetadata(
                name="sys",
                version="1.0.0",
                modality="text",
                use_case="support chatbot",
                deployment_context="production",
            )
        )
    )


def _eval_report(outcome: EvaluatorOutcome) -> EvalReport:
    result = EvaluatorResult(
        evaluator_id="EVAL_DATA_LEAKAGE_V1",
        category=EvaluatorCategory.DATA_LEAKAGE,
        outcome=outcome,
        score=0.0 if outcome is EvaluatorOutcome.FAIL else 1.0,
        threshold=0.9,
        metric_name="leak_free_rate",
        sample_count=10,
        reference="test",
        evidence_hash="sha256:00",
    )
    return EvalReport(
        system_id="sys",
        commit_ref="HEAD",
        eval_set_id="SET",
        eval_set_version="1",
        threshold_policy_hash="sha256:00",
        results=[result],
        evaluators_run=1,
        evaluators_failed=int(outcome is EvaluatorOutcome.FAIL),
        evaluators_skipped=0,
        overall_outcome=outcome,
        generated_at="2026-11-02T00:00:00Z",
    )


def _manifest(*, with_27090: bool = True) -> SystemManifest:
    attestation = Attestation(
        statement="Third-party models are pinned by hash.",
        attested_by="ciso@example.com",
        attested_at="2026-11-02",
    )
    extra: dict = {}
    if with_27090:
        extra = {
            "compliance_targets": [EU_AI_ACT, ISO],
            "framework_inputs": {
                ISO: FrameworkInputs(
                    attested={
                        f"{ISO}:5.5": attestation,
                        f"{ISO}:6.8": attestation,
                    },
                    excluded={
                        f"{ISO}:7.9": "Model size is set by the hosted provider."
                    },
                )
            },
        }
    return SystemManifest(
        system_id="sys",
        intended_purpose="support chatbot",
        commit_ref="abc123",
        **extra,
    )


def _dossier(manifest: SystemManifest, targets: list[str], eval_report=None):
    reports = evaluate_targets(
        manifest, targets, commit_ref="abc123", eval_report=eval_report
    )
    dossier = generate_dossier(
        manifest, _risk_result(), eval_report=eval_report, framework_reports=reports
    )
    return dossier, reports


def test_absent_without_the_target():
    dossier, _ = _dossier(_manifest(with_27090=False), [EU_AI_ACT])
    assert dossier.cybersecurity is None
    assert "cybersecurity" not in dossier.model_dump()
    assert "cybersecurity" not in json.loads(dossier.model_dump_json())


def test_absent_when_no_framework_reports_are_passed():
    dossier = generate_dossier(_manifest(), _risk_result())
    assert dossier.cybersecurity is None
    assert "cybersecurity" not in dossier.model_dump_json()


def test_other_targets_leave_bytes_and_checksum_unchanged():
    manifest = _manifest(with_27090=False)
    plain = generate_dossier(manifest, _risk_result())
    dossier, _ = _dossier(manifest, [EU_AI_ACT, "ISO_IEC_42001"])
    assert dossier.bundle_checksum == plain.bundle_checksum


def test_entries_match_the_framework_report():
    dossier, reports = _dossier(_manifest(), [ISO])
    part = dossier.cybersecurity
    assert part is not None
    framework_report = reports[ISO]
    rows = framework_report.report.articles
    assert [e.clause_id for e in part.entries] == [r.article for r in rows]
    for entry, row in zip(part.entries, rows, strict=True):
        assert entry.status == row.status
        assert entry.source == row.source
        assert entry.evidence_ref == row.evidence_ref
        assert entry.rationale == row.rationale
        assert entry.heading
    assert part.framework == ISO
    assert part.data_version == framework_report.data_version
    assert part.lead_in == CYBERSECURITY_LEAD_IN


def test_attested_rows_cite_who_and_when_and_unattested_rows_say_none():
    dossier, _ = _dossier(_manifest(), [ISO])
    by_id = {e.clause_id: e for e in dossier.cybersecurity.entries}
    met = by_id[f"{ISO}:5.5"]
    assert (met.status, met.source) == (GapStatus.MET, "attestation")
    assert met.evidence_ref == "attestation:ciso@example.com@2026-11-02"
    bare = by_id[f"{ISO}:5.2"]
    assert (bare.status, bare.evidence_ref) == (GapStatus.UNVERIFIED, "none")


def test_evaluator_result_reaches_the_entry():
    dossier, _ = _dossier(
        _manifest(), [ISO], eval_report=_eval_report(EvaluatorOutcome.FAIL)
    )
    entry = {e.clause_id: e for e in dossier.cybersecurity.entries}[f"{ISO}:6.8"]
    assert entry.status == GapStatus.MISSING
    assert "EVAL_DATA_LEAKAGE_V1" in entry.rationale
    assert "fail" in entry.rationale


def test_excluded_rows_are_listed_apart_with_their_reason():
    dossier, reports = _dossier(_manifest(), [ISO])
    part = dossier.cybersecurity
    rid = f"{ISO}:7.9"
    assert rid not in {e.clause_id for e in part.entries}
    assert len(part.entries) == 30
    assert [(x.clause_id, x.reason) for x in part.excluded] == list(
        reports[ISO].excluded.items()
    )
    assert part.excluded[0].heading


def test_status_counts_cover_every_status_and_every_entry():
    dossier, _ = _dossier(_manifest(), [ISO])
    part = dossier.cybersecurity
    expected = Counter(e.status.value for e in part.entries)
    assert part.status_counts == {s.value: expected[s.value] for s in GapStatus}
    assert sum(part.status_counts.values()) == len(part.entries)
    assert part.status_counts["met"] == 2
    assert part.status_counts["unverified"] == 28


def test_presence_changes_the_checksum_and_a_signed_dossier_verifies(
    tmp_path, monkeypatch
):
    from opencomplai_core.signing import generate_keypair

    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setenv("DOSSIER_SIGNING_KEY_PATH", str(key_dir / "signing.key"))
    manifest = _manifest()
    with_part, _ = _dossier(manifest, [ISO])
    without_part = generate_dossier(manifest, _risk_result())
    assert with_part.bundle_checksum != without_part.bundle_checksum

    payload = json.loads(with_part.model_dump_json())
    assert verify_dossier(payload, key_dir / "signing.pub").ok
    # Round trip keeps the bytes the signature covers.
    assert AnnexIVDossier.model_validate(payload).model_dump_json() == (
        with_part.model_dump_json()
    )
    payload["cybersecurity"]["entries"][0]["status"] = "met"
    assert verify_dossier(payload, key_dir / "signing.pub").code == "CHECKSUM_MISMATCH"


def test_schema_accepts_the_part():
    dossier, _ = _dossier(_manifest(), [ISO])
    jsonschema.validate(json.loads(dossier.model_dump_json()), build_dossier_schema())


def test_markdown_lists_the_part_and_pdf_renders():
    dossier, _ = _dossier(_manifest(), [ISO])
    text = render_markdown(dossier, schema_valid=True)
    assert "## Cybersecurity measures (Annex IV point 2(h), ISO/IEC 27090)" in text
    assert CYBERSECURITY_LEAD_IN in text
    assert "Rows reported: 30. Met 2, Partial 0, Missing 0, Unverified 28." in text
    assert (
        f"- {ISO}:5.5 Supply chain management: Met "
        "(attestation; attestation:ciso@example.com@2026-11-02)"
    ) in text
    for entry in dossier.cybersecurity.entries:
        assert entry.clause_id in text
    assert "Rows excluded by the manifest:" in text
    assert "Model size is set by the hosted provider." in text
    pytest.importorskip("fpdf")
    assert render_pdf(dossier, schema_valid=True).startswith(b"%PDF")


def test_markdown_without_the_part_has_no_cybersecurity_heading():
    dossier = generate_dossier(_manifest(with_27090=False), _risk_result())
    assert "Cybersecurity" not in render_markdown(dossier, schema_valid=True)


def test_markdown_says_when_nothing_is_excluded():
    manifest = _manifest().model_copy(
        update={
            "framework_inputs": {
                ISO: _manifest()
                .framework_inputs[ISO]
                .model_copy(update={"excluded": {}})
            }
        }
    )
    dossier, _ = _dossier(manifest, [ISO])
    assert dossier.cybersecurity.excluded == []
    assert "Rows excluded by the manifest: none." in render_markdown(
        dossier, schema_valid=True
    )
