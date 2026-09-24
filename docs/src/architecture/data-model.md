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
    compliance_target: ComplianceTarget = "EU_AI_ACT"  # legacy single target
    compliance_targets: list[str] | None = None        # frameworks to assess
    framework_inputs: dict[str, FrameworkInputs] = {}  # per-framework declarations
    high_risk_presumption: bool = False
    commit_ref: str = "HEAD"
    # ... Annex IV fields, operator_role, checker_session

class FrameworkInputs(BaseModel):  # rejects unknown keys and empty strings
    excluded: dict[str, str] = {}           # requirement id -> reason
    attested: dict[str, Attestation] = {}   # requirement id -> statement

class Attestation(BaseModel):
    statement: str
    attested_by: str
    attested_at: str  # ISO 8601 date or timestamp
```

`compliance_targets` lists framework registry keys (`EU_AI_ACT`, `NIST_AI_RMF`); when
it is unset, the single `compliance_target` is the target. Both new fields are dropped
from the serialised manifest when unset, so a manifest that does not use them keeps its
exact bytes. See [Frameworks](../frameworks/index.md).

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
    eval_summary: EvalSummary | None = None
    scan_summary: ScanSummary | None = None
    gap_report: GapReport | None = None           # EU AI Act, with --with-gaps
    nist_rmf_report: NistRmfReport | None = None  # with --with-gaps, NIST_AI_RMF targeted
    controls: ControlsSummary | None = None
    framework_reports: dict[str, FrameworkReport] | None = None  # omitted when None
```

`gap_report` and `nist_rmf_report` are permanent: every `check --with-gaps` writes them
exactly as earlier releases did, whatever else it adds. `framework_reports` is added
beside them, one entry per target in target order, only when the targets are something
other than exactly `EU_AI_ACT` or exactly `NIST_AI_RMF`. When it is `None` the key is
left out of the JSON, so such an artifact serialises, and verifies against its
signature, byte for byte as before the field existed.

### `FrameworkReport`

One framework's verdicts in a multi-framework run.

```python
class FrameworkReport(BaseModel):
    framework: str               # registry key, e.g. "NIST_AI_RMF"
    label: str                   # human-readable name
    data_version: str            # short hash of the framework data used
    derived_from: str | None     # e.g. "EU_AI_ACT"; None when evaluated natively
    disclaimer_ref: str          # "DISCLAIMER_V1" (EU AI Act) or "DISCLAIMER_V2"
    gated: bool = False          # True when this framework gated the run
    excluded: dict[str, str] = {}  # requirement id -> reason, from framework_inputs
    report: GapReport            # rows; ids other than the EU AI Act's are "<FW>:<id>"
```

`GapReport` is the same model for every framework. A row's `source` can also be
`attestation` (a provider statement from `framework_inputs`) or `crosswalk`
(re-projected from another framework's rows), and its `confidence_label` can be
`attested`.

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
```

**Evidence objects are stored as plaintext.** Both CAS backends — the local
filesystem store and the Vercel Blob store — write the bytes as given; the
blob store's `access: private` is an access-control setting, not encryption.

- **Integrity** is enforced: `read()` re-hashes the stored bytes and compares
  them against the content hash, so silent corruption or substitution is
  detected.
- **Confidentiality** is delegated to the deployment layer — an encrypted
  volume for the local backend, bucket-level encryption for object storage.

This model previously declared `encryption_profile: str` documented as
`"AES-256-GCM" | "none"`. Nothing ever wrote it, nothing ever read it, and no
backend has ever encrypted anything, so the field's only effect was to tell a
reader of this document — and of the generated OpenAPI, which carried the same
description — that a control existed which did not. It was removed in
EVID-CRYPTO. Encryption at rest, if built, requires a key-management decision
this project has not yet made and changes what the content hash addresses; it
will arrive as an explicit design rather than by reinstating the field.

## Signature domain separation

Every Ed25519 signature this system produces covers domain-separated bytes:

```
opencomplai.sig.v1 \0 <purpose> \0 <canonical payload>
```

where `<purpose>` is one of `scan-status-artifact`, `annex-iv-dossier-bundle`
or `compliance-badge`.

**Why.** One install keypair signs all three message formats, and nothing in
the signed bytes said which was which. Because the artifact signer and the
badge verifier both serialised with `json.dumps(..., sort_keys=True)`, their
preimages were byte-identical: a signature produced by
`opencomplai check --sign` verified, unmodified, as a valid compliance-badge
signature for the same object. One attestation could stand in for another.
Binding the purpose into the signed bytes is what makes a signature mean "this
key attests *this kind of thing*".

Separate keypairs per message type were considered and rejected: all three uses
share the same trust semantics ("this install produced this"), so the tag is the
complete answer and four keypairs would be four rotation problems.

**Migration — this is a hard cutover.** Signatures produced before this change
do not verify, and there is deliberately no flag to accept them. Nothing in this
system re-verifies a stored signature: badge rows are inert attestations,
dossier signatures were never verified in production, and artifact signatures
are checked once at ingest against a freshly presented envelope. An accept-both
window would therefore have protected nothing while continuing to accept exactly
the confusable signatures the change removes. Anything you need to verify again
must be re-signed.

Both implementations of the framing — `opencomplai_core.signing` and the
independent `dashboard_ingest.canonical` mirror — are held byte-identical by a
parity test.

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
