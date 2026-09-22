"""
DOSS-WIRE: wiring tests for POST /v1/docs/generate.

Covers:
  - D10: optional eval_report / corroboration_report dicts populate the
    dossier's eval-merged metrics and Section 5 scanner fields when supplied,
    and leave them exactly as today when absent (never fabricated).
  - A malformed corroboration_report is a client error (422), not a 500.
  - E-6: the eight Annex IV attestation fields (Sections 4, 6-9) pass
    through verbatim into the generated dossier.

The GenerateDocsResponse body does not carry the full dossier, so these
tests stub out the evidence-vault persistence call and capture the dossier
JSON that would have been persisted.
"""

from __future__ import annotations

import json

import opencomplai_doc_generator.main as main_module
import pytest
from httpx import ASGITransport, AsyncClient
from opencomplai_core.models import (
    CorroborationReport,
    DiscrepancySeverity,
    EvalReport,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
)
from opencomplai_doc_generator.main import app


def _make_eval_report() -> EvalReport:
    result = EvaluatorResult(
        evaluator_id="EVAL_SAFETY_V1",
        category=EvaluatorCategory.SAFETY,
        outcome=EvaluatorOutcome.PASS,
        score=0.95,
        threshold=0.8,
        metric_name="safety_score",
        sample_count=10,
        findings=[],
        reference="ref",
        evidence_hash="sha256:" + "a" * 64,
    )
    return EvalReport(
        system_id="test",
        commit_ref="abc123",
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
        system_id="test",
        commit_ref="abc123",
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


@pytest.fixture
def stub_vault(monkeypatch):
    """
    Skip the evidence-vault network calls made by generate_docs, and capture
    the dossier JSON that would have been persisted so tests can inspect
    sections the GenerateDocsResponse body does not carry.
    """
    captured: dict = {}

    async def _fake_fetch_ledger_root(tenant_id):
        return None

    async def _fake_persist_dossier(
        dossier_json, dossier_id, system_id, commit_ref, bundle_checksum, tenant_id
    ):
        captured["dossier"] = json.loads(dossier_json)
        return "content-hash-stub", "ledger-event-stub"

    monkeypatch.setattr(main_module, "_fetch_ledger_root", _fake_fetch_ledger_root)
    monkeypatch.setattr(main_module, "_persist_dossier", _fake_persist_dossier)
    return captured


async def _post_generate(payload: dict, headers: dict) -> tuple[int, dict]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/v1/docs/generate", json=payload, headers=headers)
    return response.status_code, response.json()


@pytest.mark.asyncio
async def test_eval_and_corroboration_reports_populate_dossier_sections(
    service_auth_headers, stub_vault
):
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "chatbot",
        "eval_report": _make_eval_report().model_dump(mode="json"),
        "corroboration_report": _make_corroboration_report().model_dump(mode="json"),
    }
    status, _ = await _post_generate(payload, service_auth_headers)
    assert status == 200

    dossier = stub_vault["dossier"]
    assert dossier["section5"]["scanner_version"] == "1.2.3"
    assert dossier["section5"]["corroboration_detected_categories"] == ["ai_sdk"]
    assert dossier["section4"]["metrics_reported"].get("eval_safety_score") == 0.95
    assert dossier["section2"]["performance_metrics"].get("eval_safety_score") == 0.95


@pytest.mark.asyncio
async def test_absent_reports_leave_dossier_identical_to_today(
    service_auth_headers, stub_vault
):
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "chatbot",
    }
    status, _ = await _post_generate(payload, service_auth_headers)
    assert status == 200

    dossier = stub_vault["dossier"]
    assert dossier["section5"]["scanner_version"] is None
    assert dossier["section5"]["corroboration_detected_categories"] == []
    assert dossier["section5"]["corroboration_discrepancies"] == []
    assert dossier["section5"]["corroboration_severity"] is None
    assert dossier["section4"]["metrics_reported"] == {}
    assert dossier["section2"]["performance_metrics"] == {}


@pytest.mark.asyncio
async def test_invalid_corroboration_report_returns_422(
    service_auth_headers, stub_vault
):
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "chatbot",
        "corroboration_report": {"not": "a valid corroboration report"},
    }
    status, _ = await _post_generate(payload, service_auth_headers)
    assert status == 422
    # A rejected report must never reach the persisted dossier.
    assert "dossier" not in stub_vault


@pytest.mark.asyncio
async def test_invalid_eval_report_returns_422(service_auth_headers, stub_vault):
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "chatbot",
        "eval_report": {"not": "a valid eval report"},
    }
    status, _ = await _post_generate(payload, service_auth_headers)
    assert status == 422
    assert "dossier" not in stub_vault


@pytest.mark.asyncio
async def test_annex_iv_attestation_passthrough_marks_high_risk_sections_complete(
    service_auth_headers, stub_vault
):
    """E-6: the Annex IV attestation fields are a pure passthrough —
    supplying them all must mark Sections 3, 4 and 6-9 provider_supplied=True
    and the dossier annex_iv_complete=True for a HIGH-risk request."""
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "employment screening",
        "high_risk_presumption": True,
        "training_data_description": "real training data description",
        "model_architecture": "real model architecture description",
        "human_oversight_measures": ["Two-person review on every override"],
        "monitoring_approach": "Datadog + custom drift checks every 6h",
        "incident_response_procedure": "Runbook at runbooks/ai-incident.md",
        "metrics_appropriateness_rationale": (
            "Precision/recall are appropriate for a binary screening decision."
        ),
        "lifecycle_changes": ["v1.1: recalibrated decision threshold"],
        "change_log_reference": "CHANGELOG.md#v1.1",
        "harmonised_standards": [
            "EN ISO/IEC 42001:2023 — AI management system controls applied organisation-wide"
        ],
        "eu_declaration_of_conformity_ref": "DoC-2026-001",
        "post_market_monitoring_plan_ref": "docs/pmm-plan.md",
        "post_market_monitoring_summary": "Quarterly drift review with sign-off.",
    }
    status, _ = await _post_generate(payload, service_auth_headers)
    assert status == 200

    dossier = stub_vault["dossier"]
    assert dossier["section1"]["risk_class"] == "high"
    assert dossier["section3"]["provider_supplied"] is True
    assert dossier["section4"]["provider_supplied"] is True
    for section_key in ("section6", "section7", "section8", "section9"):
        assert dossier[section_key]["provider_supplied"] is True
    assert dossier["annex_iv_complete"] is True


@pytest.mark.asyncio
async def test_high_risk_presumption_with_non_matching_purpose_fails_schema_valid(
    service_auth_headers, stub_vault
):
    """FINDING 48.6: high_risk_presumption=True must gate schema_valid even
    when intended_purpose ("chatbot") doesn't keyword-match a high-risk rule
    and no Annex IV attestations were supplied — previously this produced an
    all-placeholder dossier stamped schema_valid=True.

    D-2: an invalid dossier now also trips the fail-closed gate, so the
    default (allow_incomplete=False) response is a 422, not a 200 — the
    dossier is still persisted (stub_vault still captures it)."""
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "chatbot",
        "high_risk_presumption": True,
    }
    status, body = await _post_generate(payload, service_auth_headers)
    assert status == 422
    assert body["detail"]["schema_valid"] is False
    assert body["detail"]["error_code"] == "DOSSIER_SCHEMA_INVALID"

    dossier = stub_vault["dossier"]
    assert dossier["section1"]["risk_class"] != "high"
    assert dossier["section2_complete"] is False
    assert dossier["annex_iv_complete"] is False


@pytest.mark.asyncio
async def test_high_risk_presumption_with_non_matching_purpose_and_attestations_passes(
    service_auth_headers, stub_vault
):
    """The same presumed-high, non-matching-purpose request passes once the
    caller actually supplies the Section 2 / Annex IV attestation fields."""
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "chatbot",
        "high_risk_presumption": True,
        "training_data_description": "real training data description",
        "model_architecture": "real model architecture description",
        "human_oversight_measures": ["Two-person review on every override"],
        "monitoring_approach": "Datadog + custom drift checks every 6h",
        "incident_response_procedure": "Runbook at runbooks/ai-incident.md",
        "metrics_appropriateness_rationale": (
            "Precision/recall are appropriate for a binary screening decision."
        ),
        "lifecycle_changes": ["v1.1: recalibrated decision threshold"],
        "change_log_reference": "CHANGELOG.md#v1.1",
        "harmonised_standards": [
            "EN ISO/IEC 42001:2023 — AI management system controls applied organisation-wide"
        ],
        "eu_declaration_of_conformity_ref": "DoC-2026-001",
        "post_market_monitoring_plan_ref": "docs/pmm-plan.md",
        "post_market_monitoring_summary": "Quarterly drift review with sign-off.",
    }
    status, body = await _post_generate(payload, service_auth_headers)
    assert status == 200
    assert body["schema_valid"] is True


@pytest.mark.asyncio
async def test_genuine_high_risk_still_fails_schema_valid_without_presumption(
    service_auth_headers, stub_vault
):
    """A genuinely high-risk purpose with high_risk_presumption left at its
    default (False) must still fail schema_valid when unattested — the new
    presumed_high plumbing must not become the only path to strict gating.

    D-2: default (allow_incomplete=False) now returns 422 for this invalid
    dossier instead of 200."""
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "employment screening",
    }
    status, body = await _post_generate(payload, service_auth_headers)
    assert status == 422
    assert body["detail"]["schema_valid"] is False

    dossier = stub_vault["dossier"]
    assert dossier["section1"]["risk_class"] == "high"
    assert dossier["annex_iv_complete"] is False


@pytest.mark.asyncio
async def test_annex_iv_attestation_absent_keeps_high_risk_dossier_incomplete(
    service_auth_headers, stub_vault
):
    """Without the attestation fields, a HIGH-risk dossier must still be
    flagged incomplete — no defaults, no fabrication (E-6).

    D-2: this invalid dossier is still persisted (stub_vault captures it)
    but the default response is now 422, not 200."""
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "employment screening",
        "high_risk_presumption": True,
    }
    status, _ = await _post_generate(payload, service_auth_headers)
    assert status == 422

    dossier = stub_vault["dossier"]
    assert dossier["section1"]["risk_class"] == "high"
    assert dossier["section3"]["provider_supplied"] is False
    assert dossier["section4"]["provider_supplied"] is False
    for section_key in ("section6", "section7", "section8", "section9"):
        assert dossier[section_key]["provider_supplied"] is False
    assert dossier["annex_iv_complete"] is False


@pytest.mark.asyncio
async def test_invalid_dossier_with_allow_incomplete_returns_200(
    service_auth_headers, stub_vault
):
    """D-2 escape hatch: the same invalid HIGH-risk dossier as the test
    above must return 200 with schema_valid=False once the caller opts in
    via allow_incomplete=True — the documented compatibility path for
    existing CI users."""
    payload = {
        "system_id": "test",
        "commit_ref": "abc123",
        "intended_purpose": "employment screening",
        "high_risk_presumption": True,
        "allow_incomplete": True,
    }
    status, body = await _post_generate(payload, service_auth_headers)
    assert status == 200
    assert body["schema_valid"] is False

    dossier = stub_vault["dossier"]
    assert dossier["annex_iv_complete"] is False
