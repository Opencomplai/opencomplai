"""Tests for the core assessment engine."""

from opencomplai_core.engine import assess
from opencomplai_core.models import AssessmentInput, ModelMetadata, RiskLevel


def _make_input(use_case: str) -> AssessmentInput:
    """Helper to build a minimal AssessmentInput."""
    return AssessmentInput(
        model=ModelMetadata(
            name="test-model",
            version="1.0.0",
            modality="text",
            use_case=use_case,
            deployment_context="production",
        )
    )


def test_minimal_risk_general_use_case():
    result = assess(_make_input("customer support chatbot"))
    assert result.risk_level == RiskLevel.MINIMAL
    assert result.rules_passed == result.rules_evaluated


def test_high_risk_employment_use_case():
    result = assess(_make_input("employment screening and ranking"))
    assert result.risk_level == RiskLevel.HIGH
    assert result.rules_failed >= 1


def test_high_risk_biometric_use_case():
    result = assess(_make_input("biometric identification system"))
    assert result.risk_level == RiskLevel.HIGH


def test_result_has_evidence():
    result = assess(_make_input("customer support chatbot"))
    assert result.evidence_summary
    assert result.generated_at
    assert len(result.rule_results) > 0


def test_result_rule_counts_consistent():
    result = assess(_make_input("customer support chatbot"))
    assert result.rules_evaluated == result.rules_passed + result.rules_failed


def test_system_manifest_model():
    """SystemManifest must be importable and validatable from core models."""
    from opencomplai_core.models import SystemManifest

    m = SystemManifest(
        system_id="test-sys",
        intended_purpose="customer support chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="abc123",
    )
    assert m.system_id == "test-sys"


def test_scan_status_artifact_model():
    """ScanStatusArtifact must be importable and validatable from core models."""
    from opencomplai_core.models import ScanResult, ScanStatusArtifact

    artifact = ScanStatusArtifact(
        install_id="uuid-1",
        system_id="test-sys",
        commit_ref="abc123",
        result=ScanResult.PASS,
        failed_controls=[],
        evidence_hashes=["sha256:abc"],
        rationale_hash="sha256:def",
        duration_ms=1200,
        pending_verifications_count=0,
    )
    assert artifact.result == ScanResult.PASS
    assert artifact.signature is None  # unsigned in OSS mode
