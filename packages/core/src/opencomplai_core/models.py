"""
Shared Pydantic v2 models for Opencomplai.

This module is the single source of truth for all data contracts across
packages, services, and the CLI. Import from here — never redefine these
elsewhere.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RiskLevel(StrEnum):
    """EU AI Act risk classification levels."""

    UNACCEPTABLE = "unacceptable"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"


class ScanResult(StrEnum):
    """Terminal states for a compliance scan."""

    PASS = "pass"
    CONTROL_FAIL = "control_fail"
    VALIDATION_FAIL = "validation_fail"
    POLICY_BLOCK = "policy_block"
    TRAP_DETECTED = "trap_detected"
    DEGRADED_COMPLETE = "degraded_complete"


class VerificationOutcome(StrEnum):
    """Outcome of a ground-truth verification task."""

    VERIFIED = "verified"
    ALERTED = "alerted"
    PENDING = "pending"


class AlertSeverity(StrEnum):
    """Severity level for bias and verification alerts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OverrideDecision(StrEnum):
    """HITL override decision."""

    APPROVED = "approved"
    REJECTED = "rejected"


class SystemState(StrEnum):
    """Deployment state machine states (PRD Section 8.2)."""

    RUNNING = "running"
    HALTED_PENDING_REVIEW = "halted_pending_review"
    INCIDENT_MODE = "incident_mode"


# ---------------------------------------------------------------------------
# Core assessment models (used by packages/core engine, CLI, SDK)
# ---------------------------------------------------------------------------


class ModelMetadata(BaseModel):
    """Metadata describing the AI model being assessed."""

    name: str = Field(..., description="Human-readable model name")
    version: str = Field(..., description="Model version identifier")
    modality: str = Field(..., description="e.g. text, image, multimodal")
    use_case: str = Field(..., description="Primary intended use case")
    deployment_context: str = Field(
        ..., description="e.g. production, research, internal"
    )


class AssessmentInput(BaseModel):
    """Input to the risk assessment engine."""

    model: ModelMetadata
    answers: dict[str, Any] = Field(
        default_factory=dict,
        description="Rule-specific answers keyed by rule ID",
    )


class RuleResult(BaseModel):
    """Result for a single assessed rule."""

    rule_id: str
    rule_name: str
    passed: bool
    rationale: str
    reference: str = Field(..., description="EU AI Act article or clause reference")


class RiskResult(BaseModel):
    """Output of the risk assessment engine."""

    model_name: str
    model_version: str
    risk_level: RiskLevel
    rules_evaluated: int
    rules_passed: int
    rules_failed: int
    rule_results: list[RuleResult]
    evidence_summary: str
    generated_at: str = Field(..., description="ISO 8601 timestamp")


# ---------------------------------------------------------------------------
# PRD entity models (used by services and CLI for the full workflow)
# ---------------------------------------------------------------------------


class SystemManifest(BaseModel):
    """
    System-of-record description of an AI system under compliance assessment.
    Created by `opencomplai init` and consumed by `opencomplai check`.
    """

    system_id: str = Field(..., description="Unique system identifier")
    intended_purpose: str = Field(
        ...,
        description="Primary intended purpose (maps to Annex III categories)",
    )
    compliance_target: str = Field(
        "EU_AI_ACT", description="Compliance framework target"
    )
    high_risk_presumption: bool = Field(
        False,
        description="True if the provider presumes the system is high-risk pending classification",
    )
    commit_ref: str = Field(
        "HEAD", description="Git commit reference for this assessment"
    )

    # Optional Annex IV Section 2 inputs. Stubbed defaults are acceptable at
    # MINIMAL risk; HIGH-risk providers must override these to avoid producing
    # a dossier that misrepresents the system to an auditor.
    training_data_description: str | None = Field(
        None,
        description=(
            "Free-text summary of training data sources, provenance and curation. "
            "Required for Annex IV Section 2 in HIGH-risk dossiers."
        ),
    )
    model_architecture: str | None = Field(
        None,
        description=(
            "Free-text description of the model architecture and core design. "
            "Required for Annex IV Section 2 in HIGH-risk dossiers."
        ),
    )
    performance_metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Named numerical performance metrics for Annex IV Section 2.",
    )
    known_limitations: list[str] = Field(
        default_factory=list,
        description="Known limitations and failure modes for Annex IV Section 2.",
    )

    # Optional Annex IV Section 3 inputs (human oversight, monitoring, incident
    # response). Same compliance-liability reasoning as Section 2: stubbed
    # defaults are fine at MINIMAL risk; HIGH-risk providers must fill these.
    human_oversight_measures: list[str] = Field(
        default_factory=list,
        description="Concrete human-in-the-loop controls (Annex IV Section 3).",
    )
    monitoring_approach: str | None = Field(
        None,
        description="How the system is monitored in production (Annex IV Section 3).",
    )
    incident_response_procedure: str | None = Field(
        None,
        description="Pointer or description of incident-response procedure (Annex IV Section 3).",
    )

    operator_role: str | None = Field(
        None,
        description="EU AI Act operator role from compliance checker (provider, deployer, etc.).",
    )
    checker_session: CheckerSessionRef | None = Field(
        None,
        description="Reference to the EU AI Act applicability checker session, if run.",
    )


class CheckerSessionRef(BaseModel):
    """Embedded reference to a completed FLI-parity checker run."""

    checker_version: str = Field(
        ..., description="Checker catalog version, e.g. fli-2025-07-28"
    )
    session_id: str = Field(..., description="UUID for this checker session")
    completed_at: str = Field(
        ..., description="ISO 8601 timestamp when checker completed"
    )
    report_json_path: str = Field(
        default="",
        description="Optional path to exported checker JSON report",
    )


class ScanRequest(BaseModel):
    """Input to the compliance check workflow."""

    install_id: str = Field(..., description="UUID identifying the install instance")
    system_id: str
    commit_ref: str
    artifact_ref: str = Field(
        ..., description="Image tag, model artifact, or commit hash"
    )
    trigger: str = Field(..., description="install | ci_commit | manual_check")
    scan_mode: str = Field(..., description="ci | local | airgap")
    policy_bundle_version: str | None = None


class ScanStatusArtifact(BaseModel):
    """
    Machine-readable signed status artifact produced at the end of every scan.
    This is the canonical output consumed by CI gates and the premium dashboard.
    """

    install_id: str
    system_id: str
    commit_ref: str
    result: ScanResult
    failed_controls: list[str] = Field(default_factory=list)
    evidence_hashes: list[str] = Field(
        default_factory=list, description="SHA-256 hashes of evidence objects"
    )
    rationale_hash: str = Field(..., description="SHA-256 of the assessment rationale")
    duration_ms: int
    pending_verifications_count: int = 0
    signature: str | None = Field(
        None, description="Base64-encoded signature; None in unsigned OSS mode"
    )
    eval_summary: EvalSummary | None = Field(
        None, description="Pipeline evaluator outcomes when a sample set was supplied"
    )
    scan_summary: ScanSummary | None = Field(
        None, description="Code corroboration scan outcomes when --scan was used"
    )


class LedgerEvent(BaseModel):
    """
    A single event in the append-only Merkle-linked evidence ledger.
    Implemented in full in Phase 8 (Evidence Vault).
    """

    event_id: str = Field(..., description="UUID")
    ts: datetime
    event_type: str
    payload_hash: str = Field(..., description="SHA-256 of the event payload")
    prev_hash: str = Field(
        ..., description="SHA-256 of the previous event's canonical representation"
    )
    signer_id: str | None = Field(
        None, description="Identity of the human signer for HITL events"
    )


class EvidenceObject(BaseModel):
    """
    An immutable content-addressable evidence object stored in the local CAS.
    Implemented in full in Phase 8 (Evidence Vault).
    """

    evidence_id: str
    content_hash: str = Field(..., description="SHA-256; also the CAS storage key")
    storage_uri: str = Field(..., description="Local file path or URI")
    encryption_profile: str = Field(..., description="AES-256-GCM | none")


class VerificationTask(BaseModel):
    """
    A ground-truth verification task queued to Redis Streams.
    Implemented in full in Phase 10 (Risk Engine Enhancements).
    """

    task_id: str
    claim_ref: str
    source_ref: str
    request_hash: str = Field(
        ..., description="SHA-256 of the outbound adapter request"
    )
    response_hash: str | None = Field(
        None, description="SHA-256 of the adapter response; set on completion"
    )
    outcome: VerificationOutcome | None = None


class VerificationProof(BaseModel):
    """
    Immutable proof that a claim was verified against a ground-truth source.
    Produced by resolve_claim when outcome == VERIFIED.
    """

    task_id: str
    claim_ref: str
    evidence_hash: str = Field(
        ..., description="SHA-256 of the hashed adapter response"
    )
    verified_at: str = Field(..., description="ISO 8601 timestamp")


class BiasAlert(BaseModel):
    """Alert raised when a verification mismatch exceeds a severity threshold."""

    alert_id: str
    severity: AlertSeverity
    metric: str
    threshold: float
    linked_event_id: str


class OverrideAction(BaseModel):
    """
    A HITL override action with mandatory rationale.
    Rejected without a non-empty rationale_hash (REQ-HITL-001).
    Implemented in full in Phase 11 (HITL Orchestrator).
    """

    override_id: str
    case_id: str
    actor_id: str
    rationale_hash: str = Field(
        ..., description="SHA-256 of the rationale text; never empty"
    )
    decision: OverrideDecision


# ---------------------------------------------------------------------------
# Pipeline evaluators (Workstream A)
# ---------------------------------------------------------------------------


class EvaluatorCategory(StrEnum):
    SAFETY = "safety"
    BIAS = "bias"
    DATA_LEAKAGE = "data_leakage"


class EvaluatorOutcome(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIPPED = "skipped"


class EvalSampleSet(BaseModel):
    """Customer-supplied evidence evaluators run against (airgap-safe)."""

    eval_set_id: str
    system_id: str
    commit_ref: str = "HEAD"
    task_type: str = "binary_classification"
    prompts: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    predictions: list[float] = Field(default_factory=list)
    labels: list[float] = Field(default_factory=list)
    protected_attributes: dict[str, list[str]] = Field(default_factory=dict)
    declared_output_fields: list[str] = Field(default_factory=list)
    threshold_overrides: dict[str, float] = Field(default_factory=dict)


class EvaluatorResult(BaseModel):
    evaluator_id: str
    category: EvaluatorCategory
    outcome: EvaluatorOutcome
    score: float
    threshold: float
    metric_name: str
    sample_count: int
    skip_reason: str | None = None
    findings: list[str] = Field(default_factory=list)
    reference: str
    evidence_hash: str


class EvalReport(BaseModel):
    system_id: str
    commit_ref: str
    eval_set_id: str
    eval_set_version: str
    threshold_policy_hash: str
    results: list[EvaluatorResult]
    evaluators_run: int
    evaluators_failed: int
    evaluators_skipped: int
    overall_outcome: EvaluatorOutcome
    generated_at: str


class EvalSummary(BaseModel):
    """Compact eval block embedded in ScanStatusArtifact."""

    eval_set_id: str
    eval_set_version: str
    threshold_policy_hash: str
    overall_outcome: EvaluatorOutcome
    failed_evaluator_ids: list[str] = Field(default_factory=list)
    skipped_evaluators: dict[str, str] = Field(default_factory=dict)
    evidence_hashes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# HITL reviewer queue (Workstream B)
# ---------------------------------------------------------------------------


class ReviewItemState(StrEnum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    DECIDED = "decided"
    EXPIRED = "expired"


class ReviewReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    EVALUATOR_FAIL = "evaluator_fail"
    MODIFICATION_TRAP = "modification_trap"
    POLICY_BLOCK = "policy_block"
    MANUAL = "manual"
    MANIFEST_DISCREPANCY = "manifest_discrepancy"


class ReviewItem(BaseModel):
    review_id: str
    tenant_id: str
    system_id: str
    commit_ref: str
    reason: ReviewReason
    state: ReviewItemState
    payload_ref: str
    context_ref: str
    reviewer_group: str | None = None
    assigned_to: str | None = None
    idempotency_key: str
    created_at: str
    expires_at: str | None = None
    decided_at: str | None = None
    linked_override_id: str | None = None


class ReviewDecisionRequest(BaseModel):
    review_id: str
    actor_id: str
    decision: OverrideDecision
    rationale: str
    idempotency_key: str


class RedactedReviewContext(BaseModel):
    """Reviewer-safe context — no raw prompts, outputs, or PII."""

    review_id: str
    reason: ReviewReason
    detector_ids: list[str] = Field(default_factory=list)
    masked_excerpts: list[str] = Field(default_factory=list)
    aggregate_counts: dict[str, int] = Field(default_factory=dict)
    evidence_hashes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Data-flow lineage (Workstream C)
# ---------------------------------------------------------------------------


class FlowNodeType(StrEnum):
    SOURCE = "source"
    RISK_ENGINE = "risk_engine"
    EVALUATOR = "evaluator"
    EVIDENCE_VAULT = "evidence_vault"
    EGRESS = "egress"
    DASHBOARD = "dashboard"


class FlowEdge(BaseModel):
    from_node: str
    to_node: str
    fields: list[str]
    evidence_hashes: list[str] = Field(default_factory=list)
    blocked: bool = False
    event_count: int = 0


class FlowNode(BaseModel):
    node_id: str
    node_type: FlowNodeType
    label: str


class LineageEvent(BaseModel):
    lineage_event_id: str
    system_id: str
    commit_ref: str | None = None
    from_node: str
    to_node: str
    fields: list[str]
    evidence_hashes: list[str] = Field(default_factory=list)
    blocked: bool = False
    occurred_at: str


class DataFlowGraph(BaseModel):
    system_id: str
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    generated_at: str
    ledger_root_hash: str | None = None


# ---------------------------------------------------------------------------
# Hybrid scanner (Workstream Scanner)
# ---------------------------------------------------------------------------


class EvidenceKind(StrEnum):
    DEPENDENCY = "dependency"
    LOCKFILE_PACKAGE = "lockfile_package"
    IMPORT = "import"
    CALLSITE = "callsite"
    ENDPOINT = "endpoint"
    CONFIG_KEY = "config_key"
    MODEL_ARTIFACT = "model_artifact"
    NOTEBOOK_CELL = "notebook_cell"
    PROMPT_TEMPLATE = "prompt_template"
    DATAFLOW_HINT = "dataflow_hint"
    ROUTE_REACHABILITY = "route_reachability"


class SignalCategory(StrEnum):
    AI_SDK = "ai_sdk"
    ML_FRAMEWORK = "ml_framework"
    LLM_ORCHESTRATION = "llm_orchestration"
    INFERENCE_ENDPOINT = "inference_endpoint"
    MODEL_ARTIFACT = "model_artifact"
    EMBEDDINGS_VECTOR = "embeddings_vector"
    PROMPT_AGENT = "prompt_agent"
    BIOMETRIC = "biometric"
    SCORING_PROFILING = "scoring_profiling"
    PII_DATAFLOW = "pii_dataflow"


class DiscrepancySeverity(StrEnum):
    NONE = "none"
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class EvidenceScope(StrEnum):
    PROD = "prod"
    TEST = "test"
    DEV = "dev"
    DOCS = "docs"
    GENERATED = "generated"
    VENDOR = "vendor"
    UNKNOWN = "unknown"


class Reachability(StrEnum):
    REACHABLE_ENTRYPOINT = "reachable_entrypoint"
    INTERNAL_CALLCHAIN = "internal_callchain"
    IMPORT_ONLY = "import_only"
    MANIFEST_ONLY = "manifest_only"
    UNKNOWN = "unknown"


class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_kind: EvidenceKind
    category: SignalCategory
    token_hash: str
    token_label: str
    locations: list[str]
    scope: EvidenceScope
    reachability: Reachability
    detector_id: str
    detector_version: str
    redaction_level: str
    rationale_code: str
    confidence: float
    intent_annotation: Any = None  # IntentAnnotation when opencomplai-ai is installed


class DetectionFinding(BaseModel):
    finding_id: str
    signal_category: SignalCategory
    evidence_ids: list[str]
    locations: list[str]
    mapped_taxonomy: list[str]
    strength: float
    scope: EvidenceScope
    reachability: Reachability
    confidence_rationale: list[str]
    reviewer_prompt: str


class ScoreBreakdown(BaseModel):
    detector_confidence: float
    evidence_strength: float
    scope_weight: float
    reachability_weight: float
    taxonomy_weight: float
    final_score: float
    rationale_codes: list[str]


class CorroborationReport(BaseModel):
    scan_id: str
    system_id: str
    commit_ref: str
    scanner_version: str
    input_digest: str
    config_hash: str
    detector_versions: dict[str, str]
    declared_purpose: str
    declared_categories: list[str]
    evidence: list[EvidenceItem]
    findings: list[DetectionFinding]
    detected_categories: list[str]
    discrepancies: list[str]
    score_breakdown: dict[str, ScoreBreakdown]
    severity: DiscrepancySeverity
    feature_summary: dict[str, int]
    cache_summary: dict[str, int]
    skipped_paths: list[str]
    skip_reasons: dict[str, int] = Field(default_factory=dict)
    limits_hit: list[str]
    warnings: list[str]
    detector_errors: list[str]
    baseline_ref: str | None
    generated_at: str
    report_hash: str


class ScanSummary(BaseModel):
    """Compact scan block embedded in ScanStatusArtifact."""

    scan_id: str
    scanner_version: str
    severity: DiscrepancySeverity
    detected_categories: list[str] = Field(default_factory=list)
    discrepancies: list[str] = Field(default_factory=list)
    report_hash: str
    evidence_hashes: list[str] = Field(default_factory=list)
