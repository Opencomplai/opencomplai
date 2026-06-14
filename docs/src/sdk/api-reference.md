# SDK API Reference

## Exported symbols

```python
from opencomplai import (
    assess,
    AssessmentInput,
    ModelMetadata,
    RiskResult,
    ScanStatusArtifact,
    SystemManifest,
)
```

---

## `assess(input: AssessmentInput) -> RiskResult`

Run the rule engine against an `AssessmentInput` and return a `RiskResult`.

```python
result = assess(assessment_input)
```

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `input` | `AssessmentInput` | The assessment input containing model metadata and optional rule answers. |

**Returns:** `RiskResult`

---

## `AssessmentInput`

Input to the risk assessment engine.

| Field | Type | Default | Description |
|---|---|---|---|
| `model` | `ModelMetadata` | *(required)* | Metadata describing the AI model. |
| `answers` | `dict[str, Any]` | `{}` | Rule-specific answers keyed by rule ID. |

---

## `ModelMetadata`

Metadata describing the AI model being assessed.

| Field | Type | Description |
|---|---|---|
| `name` | `str` | Human-readable model name. |
| `version` | `str` | Model version identifier. |
| `modality` | `str` | e.g. `text`, `image`, `multimodal`. |
| `use_case` | `str` | Primary intended use case. |
| `deployment_context` | `str` | e.g. `production`, `research`, `internal`. |

---

## `RiskResult`

Output of the risk assessment engine.

| Field | Type | Description |
|---|---|---|
| `model_name` | `str` | Model name from input. |
| `model_version` | `str` | Model version from input. |
| `risk_level` | `RiskLevel` | One of `unacceptable`, `high`, `limited`, `minimal`. |
| `rules_evaluated` | `int` | Total number of rules evaluated. |
| `rules_passed` | `int` | Number of passing rules. |
| `rules_failed` | `int` | Number of failing rules. |
| `rule_results` | `list[RuleResult]` | Per-rule pass/fail with rationale. |
| `evidence_summary` | `str` | Human-readable evidence summary. |
| `generated_at` | `str` | ISO 8601 timestamp. |

---

## `RuleResult`

Result for a single assessed rule.

| Field | Type | Description |
|---|---|---|
| `rule_id` | `str` | Unique rule identifier (e.g. `EU_AIA_ART6_HIGH_RISK`). |
| `rule_name` | `str` | Human-readable rule name. |
| `passed` | `bool` | `True` if the rule passed. |
| `rationale` | `str` | Explanation of the outcome. |
| `reference` | `str` | EU AI Act article or clause reference. |

---

## `ScanStatusArtifact`

Machine-readable signed status artifact produced by `opencomplai check`.
This is the CI-gate output written to `compliance-artifact.json`.

| Field | Type | Description |
|---|---|---|
| `install_id` | `str` | UUID identifying the install instance. |
| `system_id` | `str` | System identifier from manifest. |
| `commit_ref` | `str` | Git commit reference. |
| `result` | `ScanResult` | `pass`, `control_fail`, `validation_fail`, `policy_block`, `trap_detected`, or `degraded_complete`. |
| `failed_controls` | `list[str]` | IDs of failing control checks. |
| `evidence_hashes` | `list[str]` | SHA-256 hashes of evidence objects. |
| `rationale_hash` | `str` | SHA-256 of the assessment rationale. |
| `duration_ms` | `int` | Check duration in milliseconds. |
| `pending_verifications_count` | `int` | Number of outstanding verification tasks. |
| `signature` | `str \| None` | Base64-encoded signature; `None` in unsigned OSS mode. |

---

## `SystemManifest`

System-of-record description of the AI system. Created by `opencomplai init`.

| Field | Type | Default | Description |
|---|---|---|---|
| `system_id` | `str` | *(required)* | Unique system identifier. |
| `intended_purpose` | `str` | *(required)* | Primary intended purpose (maps to Annex III categories). |
| `compliance_target` | `str` | `EU_AI_ACT` | Compliance framework target. |
| `high_risk_presumption` | `bool` | `False` | Provider presumes high-risk pending classification. |
| `commit_ref` | `str` | `HEAD` | Git commit reference. |

---

## Enums

### `RiskLevel`

```python
from opencomplai_core.models import RiskLevel

RiskLevel.UNACCEPTABLE  # "unacceptable"
RiskLevel.HIGH          # "high"
RiskLevel.LIMITED       # "limited"
RiskLevel.MINIMAL       # "minimal"
```

### `ScanResult`

```python
from opencomplai_core.models import ScanResult

ScanResult.PASS                 # "pass"
ScanResult.CONTROL_FAIL         # "control_fail"
ScanResult.VALIDATION_FAIL      # "validation_fail"
ScanResult.POLICY_BLOCK         # "policy_block"
ScanResult.TRAP_DETECTED        # "trap_detected"
ScanResult.DEGRADED_COMPLETE    # "degraded_complete"
```
