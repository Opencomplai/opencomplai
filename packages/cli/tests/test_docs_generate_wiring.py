"""
DOSS-WIRE: `opencomplai docs generate` sidecar wiring (D10).

`docs generate` loads the most recent scan-report.json / eval-report.json
artifacts from cwd (the same files `check`/`gaps` already write) and passes
them through to `generate_dossier`. Absence must stay honest — the dossier
must come out byte-for-byte identical to today's behaviour.

These tests force the local-fallback path (no OPENCOMPLAI_API_URL set, so
`_call_service` raises ConnectionError) and isolate cwd to tmp_path so the
sidecar reads/writes never touch the repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from opencomplai_cli.main import app
from opencomplai_core.models import (
    CorroborationReport,
    DiscrepancySeverity,
    EvalReport,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
    SystemManifest,
)
from typer.testing import CliRunner

runner = CliRunner()

_SYSTEM_ID = "doss-wire-test"
_COMMIT_REF = "HEAD"


def _make_eval_report() -> EvalReport:
    result = EvaluatorResult(
        evaluator_id="EVAL_SAFETY_V1",
        category=EvaluatorCategory.SAFETY,
        outcome=EvaluatorOutcome.PASS,
        score=0.91,
        threshold=0.8,
        metric_name="safety_score",
        sample_count=5,
        findings=[],
        reference="ref",
        evidence_hash="sha256:" + "b" * 64,
    )
    return EvalReport(
        system_id=_SYSTEM_ID,
        commit_ref=_COMMIT_REF,
        eval_set_id="es-1",
        eval_set_version="1.0.0",
        threshold_policy_hash="sha256:policy",
        results=[result],
        evaluators_run=1,
        evaluators_failed=0,
        evaluators_skipped=0,
        overall_outcome=EvaluatorOutcome.PASS,
        generated_at="2026-06-09T00:00:00+00:00",
    )


def _make_corroboration_report() -> CorroborationReport:
    return CorroborationReport(
        scan_id="scan-1",
        system_id=_SYSTEM_ID,
        commit_ref=_COMMIT_REF,
        scanner_version="1.2.3",
        input_digest="sha256:input",
        config_hash="sha256:config",
        detector_versions={"DET_AI_DEP_V1": "1.0.0"},
        declared_purpose="chatbot",
        declared_categories=[],
        evidence=[],
        findings=[],
        detected_categories=["ai_sdk"],
        discrepancies=["undeclared: ai_sdk"],
        score_breakdown={},
        severity=DiscrepancySeverity.MAJOR,
        feature_summary={},
        cache_summary={},
        skipped_paths=[],
        limits_hit=[],
        warnings=[],
        detector_errors=[],
        baseline_ref=None,
        generated_at="2026-06-09T00:00:00+00:00",
        report_hash="sha256:report",
    )


def _invoke_docs_generate(output_dir: Path) -> object:
    return runner.invoke(
        app,
        [
            "docs",
            "generate",
            "--system-id",
            _SYSTEM_ID,
            "--commit-ref",
            _COMMIT_REF,
            "--output-dir",
            str(output_dir),
        ],
    )


def _single_dossier(output_dir: Path) -> dict:
    files = list(output_dir.glob("dossier_*.json"))
    assert len(files) == 1, f"expected exactly one dossier file, found {files}"
    return json.loads(files[0].read_text())


def test_docs_generate_with_artifacts_present_populates_sections(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)

    (tmp_path / "scan-report.json").write_text(
        _make_corroboration_report().model_dump_json(indent=2)
    )
    (tmp_path / "eval-report.json").write_text(
        _make_eval_report().model_dump_json(indent=2)
    )

    output_dir = tmp_path / "out"
    result = _invoke_docs_generate(output_dir)
    assert result.exit_code == 0, result.output

    dossier = _single_dossier(output_dir)
    assert dossier["section5"]["scanner_version"] == "1.2.3"
    assert dossier["section5"]["corroboration_detected_categories"] == ["ai_sdk"]
    eval_metric_keys = [
        k for k in dossier["section4"]["metrics_reported"] if k.startswith("eval_")
    ]
    assert eval_metric_keys, "expected at least one eval_ metric key"
    assert dossier["section4"]["metrics_reported"]["eval_safety_score"] == 0.91


def test_docs_generate_without_artifacts_matches_direct_generator_call(
    tmp_path, monkeypatch
):
    """Absent-artifact path must be identical to calling generate_dossier
    directly with no eval_report/corroboration_report (D10 — never fabricate)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)

    output_dir = tmp_path / "out"
    result = _invoke_docs_generate(output_dir)
    assert result.exit_code == 0, result.output
    # Console note confirms the honest-absence path, not a silent skip.
    assert "No scan-report.json found" in result.output
    assert "No eval-report.json found" in result.output

    dossier = _single_dossier(output_dir)

    from opencomplai_core.dossier_generator import generate_dossier
    from opencomplai_core.engine import assess
    from opencomplai_core.models import AssessmentInput, ModelMetadata, SystemManifest

    manifest = SystemManifest(
        system_id=_SYSTEM_ID,
        intended_purpose="Not specified",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref=_COMMIT_REF,
    )
    risk_result = assess(
        AssessmentInput(
            model=ModelMetadata(
                name=_SYSTEM_ID,
                version=_COMMIT_REF,
                modality="text",
                use_case="Not specified",
                deployment_context="production",
            )
        )
    )
    direct = generate_dossier(manifest, risk_result, provider_name="Unknown Provider")

    assert dossier["section5"]["scanner_version"] == direct.section5.scanner_version
    assert dossier["section5"]["scanner_version"] is None
    assert (
        dossier["section5"]["corroboration_detected_categories"]
        == direct.section5.corroboration_detected_categories
    )
    assert (
        dossier["section5"]["corroboration_discrepancies"]
        == direct.section5.corroboration_discrepancies
    )
    assert (
        dossier["section5"]["corroboration_severity"]
        == direct.section5.corroboration_severity
    )
    assert dossier["section4"]["metrics_reported"] == direct.section4.metrics_reported
    assert (
        dossier["section2"]["performance_metrics"]
        == direct.section2.performance_metrics
    )


def test_docs_generate_warns_and_continues_on_malformed_scan_report(
    tmp_path, monkeypatch
):
    """A corrupt sidecar must never abort generation — warn and continue
    honestly unpopulated (D10 — never fabricate, never abort)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    (tmp_path / "scan-report.json").write_text("not valid json")

    output_dir = tmp_path / "out"
    result = _invoke_docs_generate(output_dir)
    assert result.exit_code == 0, result.output
    assert "Warning" in result.output

    dossier = _single_dossier(output_dir)
    assert dossier["section5"]["scanner_version"] is None


def test_check_scan_writes_scan_report_sidecar(tmp_path, monkeypatch):
    """`check --scan` must write scan-report.json beside compliance-artifact.json
    (E-5) so `docs generate` can pick it up as the most recent evidence."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)

    manifest_path = tmp_path / "system-manifest.json"
    init_result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            _SYSTEM_ID,
            "--intended-purpose",
            "customer support chatbot",
            "--output",
            str(manifest_path),
        ],
    )
    assert init_result.exit_code == 0, init_result.output

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "face.py").write_text("import face_recognition\n", encoding="utf-8")

    check_result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--scan",
        ],
    )
    assert check_result.exit_code in (0, 1)

    scan_report_path = tmp_path / "scan-report.json"
    assert scan_report_path.exists()
    parsed = CorroborationReport.model_validate_json(scan_report_path.read_text())
    assert parsed.scanner_version


def test_docs_generate_local_fallback_honors_high_risk_presumption_in_schema_check(
    tmp_path, monkeypatch
):
    """
    A manifest that declares high_risk_presumption=True but whose
    intended_purpose matches no Annex III keyword (so assess() does not
    itself classify the system as high risk) and carries no Section 6-9
    attestations must be reported as schema-INVALID locally, matching the
    doc-generator service (which passes presumed_high=request.
    high_risk_presumption into validate_dossier_schema — see services/
    doc-generator/src/opencomplai_doc_generator/main.py). Before the fix,
    the local fallback called validate_dossier_schema(dossier) with no
    presumed_high argument, so the attestation checks were skipped and the
    CLI printed "schema: valid" for a dossier the service would reject.

    D-2: an invalid dossier like this one is also the fail-closed gate's
    canonical case — the dossier is still written to disk, but the process
    now exits 2 (VALIDATION_FAIL) instead of 0 unless --allow-incomplete is
    passed (see the two tests below).
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)

    manifest_path = tmp_path / "system-manifest.json"
    manifest_path.write_text(
        SystemManifest(
            system_id=_SYSTEM_ID,
            intended_purpose="Not specified",
            high_risk_presumption=True,
            commit_ref=_COMMIT_REF,
        ).model_dump_json(indent=2)
    )

    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "docs",
            "generate",
            "--system-id",
            _SYSTEM_ID,
            "--commit-ref",
            _COMMIT_REF,
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 2, result.output

    dossier = _single_dossier(output_dir)
    # The manifest carries no lifecycle/attestation fields, so with the
    # presumption honored, Annex IV cannot be complete.
    assert dossier["section1"]["risk_class"] != "high"
    assert dossier["annex_iv_complete"] is False
    assert "invalid" in result.output
    assert "valid" not in result.output.replace("invalid", "")


def test_docs_generate_invalid_dossier_allow_incomplete_restores_exit_zero(
    tmp_path, monkeypatch
):
    """D-2 escape hatch: the same invalid-schema fixture as the test above
    must exit 0 (and still write the file, still print "invalid") once
    --allow-incomplete is passed — the documented compatibility path for
    existing CI users."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)

    manifest_path = tmp_path / "system-manifest.json"
    manifest_path.write_text(
        SystemManifest(
            system_id=_SYSTEM_ID,
            intended_purpose="Not specified",
            high_risk_presumption=True,
            commit_ref=_COMMIT_REF,
        ).model_dump_json(indent=2)
    )

    output_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "docs",
            "generate",
            "--system-id",
            _SYSTEM_ID,
            "--commit-ref",
            _COMMIT_REF,
            "--manifest",
            str(manifest_path),
            "--output-dir",
            str(output_dir),
            "--allow-incomplete",
        ],
    )
    assert result.exit_code == 0, result.output

    dossier = _single_dossier(output_dir)
    assert dossier["annex_iv_complete"] is False
    assert "invalid" in result.output


def test_docs_generate_valid_dossier_exits_zero_without_allow_incomplete(
    tmp_path, monkeypatch
):
    """D-2 must not regress the happy path: a schema-valid dossier (no
    high_risk_presumption, no manifest) still exits 0 with no flag needed —
    this is the same fixture as
    test_docs_generate_without_artifacts_matches_direct_generator_call."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)

    output_dir = tmp_path / "out"
    result = _invoke_docs_generate(output_dir)
    assert result.exit_code == 0, result.output

    dossier = _single_dossier(output_dir)
    assert dossier["annex_iv_complete"] is True


def test_docs_generate_local_fallback_needs_only_published_packages(
    tmp_path, monkeypatch
):
    """A PyPI install has opencomplai-core but never the unpublished
    doc-generator service package, so the local fallback must not import it.
    Submodules cached by earlier tests are blocked too, otherwise the import
    would be served from sys.modules without looking at the parent."""
    for name in [m for m in sys.modules if m.startswith("opencomplai_doc_generator")]:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, "opencomplai_doc_generator", None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)

    output_dir = tmp_path / "out"
    result = _invoke_docs_generate(output_dir)
    assert result.exit_code == 0, result.output

    dossier = _single_dossier(output_dir)
    assert dossier["system_id"] == _SYSTEM_ID
