# Data Model

All data contracts are defined as **Pydantic v2 models** in `packages/core/src/opencomplai_core/models.py`. This is the single source of truth for all packages, services, and the CLI.

## Assessment models (CLI, SDK, core engine)

### `ModelMetadata`

Describes the AI model being assessed.

```python
class ModelMetadata(BaseModel):
    name: str               # Human-readable model name
    version: str            # Model version identifier
    modality: str           # "text" | "image" | "multimodal"
    use_case: str           # Primary intended use case
    deployment_context: str # "production" | "research" | "internal"
```

### `AssessmentInput`

Input to `assess()`.

```python
class AssessmentInput(BaseModel):
    model: ModelMetadata
    answers: dict[str, Any] = {}   # Rule-specific answers keyed by rule ID
```

### `RuleResult`

Result of a single rule evaluation.

```python
class RuleResult(BaseModel):
    rule_id: str      # e.g. "EU_AIA_ART6_HIGH_RISK"
    rule_name: str    # Human-readable name
    passed: bool
    rationale: str    # Why the rule passed or failed
    reference: str    # EU AI Act article reference
```

### `RiskResult`

Output of `assess()`. Contains the aggregate risk classification.

```python
class RiskResult(BaseModel):
    model_name: str
    model_version: str
    risk_level: RiskLevel      # UNACCEPTABLE | HIGH | LIMITED | MINIMAL
    rules_evaluated: int
    rules_passed: int
    rules_failed: int
    rule_results: list[RuleResult]
    evidence_summary: str
    generated_at: str          # ISO 8601
```

### `SystemManifest`

Created by `opencomplai init`. Consumed by `opencomplai check`.

```python
class SystemManifest(BaseModel):
    system_id: str
    intended_purpose: str
    compliance_target: str = "EU_AI_ACT"
    high_risk_presumption: bool = False
    commit_ref: str = "HEAD"
```

### `ScanStatusArtifact`

The CI-gate output. Written to `compliance-artifact.json` by `opencomplai check`.

```python
class ScanStatusArtifact(BaseModel):
    install_id: str
    system_id: str
    commit_ref: str
    result: ScanResult         # "pass" | "control_fail" | ...
    failed_controls: list[str]
    evidence_hashes: list[str] # SHA-256 hashes of evidence objects
    rationale_hash: str        # SHA-256 of assessment rationale
    duration_ms: int
    pending_verifications_count: int = 0
    signature: str | None      # Base64-encoded Ed25519 signature; None = unsigned
```

## Service models (gateway API, evidence vault)

### `ScanRequest`

Input to the service-backed scan workflow.

```python
class ScanRequest(BaseModel):
    install_id: str
    system_id: str
    commit_ref: str
    artifact_ref: str   # Image tag, model artifact, or commit hash
    trigger: str        # "install" | "ci_commit" | "manual_check"
    scan_mode: str      # "ci" | "local" | "airgap"
    policy_bundle_version: str | None = None
```

### `LedgerEvent`

A single entry in the append-only Merkle-linked evidence ledger.

```python
class LedgerEvent(BaseModel):
    event_id: str       # UUID
    ts: datetime
    event_type: str     # e.g. "compliance_check_started"
    payload_hash: str   # SHA-256 of event payload
    prev_hash: str      # SHA-256 of previous event (Merkle chain)
    signer_id: str | None
```

### `EvidenceObject`

An immutable content-addressable evidence object in the CAS.

```python
class EvidenceObject(BaseModel):
    evidence_id: str
    content_hash: str   # SHA-256; also the storage key
    storage_uri: str    # Local file path or URI
    encryption_profile: str  # "AES-256-GCM" | "none"
```

## Enumerations

```python
class RiskLevel(str, Enum):
    UNACCEPTABLE = "unacceptable"
    HIGH = "high"
    LIMITED = "limited"
    MINIMAL = "minimal"

class ScanResult(str, Enum):
    PASS = "pass"
    CONTROL_FAIL = "control_fail"
    VALIDATION_FAIL = "validation_fail"
    POLICY_BLOCK = "policy_block"
    TRAP_DETECTED = "trap_detected"
    DEGRADED_COMPLETE = "degraded_complete"

class VerificationOutcome(str, Enum):
    VERIFIED = "verified"
    ALERTED = "alerted"
    PENDING = "pending"

class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SystemState(str, Enum):
    RUNNING = "running"
    HALTED_PENDING_REVIEW = "halted_pending_review"
    INCIDENT_MODE = "incident_mode"
```
