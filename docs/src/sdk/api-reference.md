# SDK API Reference

## Exported symbols

```python
from opencomplai import (
    assess,
    AssessmentInput,
    ModelMetadata,
    RiskLevel,
    RiskResult,
    RuleResult,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
    # several frameworks side by side
    evaluate_targets,
    resolve_targets,
    FRAMEWORKS,
    FrameworkPack,
    FrameworkReport,
    GapReport,
)
```

The same framework names are exported by `opencomplai_core`.

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
| `compliance_target` | `ComplianceTarget` | `EU_AI_ACT` | Legacy single target: `EU_AI_ACT` or `NIST_AI_RMF`. Used when `compliance_targets` is unset. |
| `compliance_targets` | `list[str] \| None` | `None` | Framework keys to assess side by side, e.g. `["EU_AI_ACT", "NIST_AI_RMF"]`. Must be non-empty when set. |
| `framework_inputs` | `dict[str, FrameworkInputs]` | `{}` | Per framework: `excluded` (requirement id → reason) and `attested` (requirement id → `Attestation(statement, attested_by, attested_at)`). |
| `high_risk_presumption` | `bool` | `False` | Provider presumes high-risk pending classification. |
| `commit_ref` | `str` | `HEAD` | Git commit reference. |

`compliance_targets` and `framework_inputs` are left out of the serialised manifest when
unset. See [Frameworks](../frameworks/index.md).

---

## Several frameworks side by side

### `resolve_targets(manifest, cli_targets=None) -> list[str]`

The frameworks to assess, in order and without duplicates: `cli_targets` when given,
else `manifest.compliance_targets`, else `[manifest.compliance_target]`. Raises
`ValueError` on a key that is not in `FRAMEWORKS`.

### `evaluate_targets(manifest, targets, *, commit_ref, risk_result=None, corroboration_report=None, eval_report=None, repo_root=None) -> dict[str, FrameworkReport]`

One `FrameworkReport` per framework. The EU AI Act entry always comes first, even when
it is not a target, because it is the evidence derived frameworks are built from; the
other targets follow in order. Each input resolves the rows that depend on it, as in
`opencomplai gaps`: `risk_result` the rule-backed EU AI Act articles,
`corroboration_report` the scan-backed rows, `eval_report` the evaluator-backed rows,
and `repo_root` the documentation probes. A row whose input is missing is
**Unverified**. Requirements excluded in `manifest.framework_inputs` move to
`FrameworkReport.excluded`. Raises `ValueError` on an unknown framework, on
`framework_inputs` for `EU_AI_ACT`, on an excluded or attested id the framework does
not accept, or on a blank exclusion reason.

```python
from pathlib import Path

from opencomplai import (
    AssessmentInput,
    ModelMetadata,
    SystemManifest,
    assess,
    evaluate_targets,
    resolve_targets,
)

manifest = SystemManifest.model_validate_json(Path("system-manifest.json").read_text())
risk_result = assess(AssessmentInput(model=ModelMetadata(
    name=manifest.system_id,
    version="HEAD",
    modality="text",
    use_case=manifest.intended_purpose,
    deployment_context="local",
)))
reports = evaluate_targets(
    manifest,
    resolve_targets(manifest),
    commit_ref="HEAD",
    risk_result=risk_result,
    repo_root=Path("."),
)
for framework, framework_report in reports.items():
    for row in framework_report.report.articles:
        print(framework, row.article, row.status.value)
```

### `FRAMEWORKS: dict[str, FrameworkPack]`

The frameworks this release can assess, keyed by the id used in `compliance_targets`:
`EU_AI_ACT` (evaluated natively) and `NIST_AI_RMF` (derived from EU AI Act evidence).

### `FrameworkPack`

Frozen dataclass describing one framework: `id`, `label`, `disclaimer_ref`, and
either `requirements` (path to a native requirements map) or `derive` (a function
from the EU AI Act `GapReport` to this framework's `GapReport`), plus `data_files`. See
[Adding framework packs](../contributing/adding-framework-packs.md).

### `FrameworkReport`

| Field | Type | Description |
|---|---|---|
| `framework` | `str` | Framework key, e.g. `NIST_AI_RMF`. |
| `label` | `str` | Human-readable framework name. |
| `data_version` | `str` | Short hash of the framework data the verdicts came from. |
| `derived_from` | `str \| None` | Framework whose evidence was re-projected; `None` when evaluated natively. |
| `disclaimer_ref` | `str` | `DISCLAIMER_V1` for the EU AI Act, `DISCLAIMER_V2` for every other framework. |
| `gated` | `bool` | `True` when the framework gated a `check` run. |
| `excluded` | `dict[str, str]` | Requirement id → reason, from `framework_inputs`. |
| `report` | `GapReport` | The framework's rows. |

### `GapReport`

| Field | Type | Description |
|---|---|---|
| `system_id` | `str` | System identifier. |
| `commit_ref` | `str` | Git commit reference. |
| `generated_at` | `str` | ISO 8601 timestamp. |
| `articles` | `list[ArticleGapStatus]` | One row per requirement: `article` (the id; prefixed `<FW>:` outside the EU AI Act), `status` (`met`, `partial`, `missing`, `unverified`), `source`, `evidence_ref`, `rationale`, `confidence`, `confidence_label`. |
| `evidence_hashes` | `list[str]` | Hashes of the evidence the rows cite. |
| `principle_summary` | `PrincipleSummary \| None` | EU AI Act principle rollup, filled in by `opencomplai gaps`. |

---

## Enums

### `RiskLevel`

```python
from opencomplai import RiskLevel

RiskLevel.UNACCEPTABLE  # "unacceptable"
RiskLevel.HIGH          # "high"
RiskLevel.LIMITED       # "limited"
RiskLevel.MINIMAL       # "minimal"
```

### `ScanResult`

```python
from opencomplai import ScanResult

ScanResult.PASS                 # "pass"
ScanResult.CONTROL_FAIL         # "control_fail"
ScanResult.VALIDATION_FAIL      # "validation_fail"
ScanResult.POLICY_BLOCK         # "policy_block"
ScanResult.TRAP_DETECTED        # "trap_detected"
ScanResult.DEGRADED_COMPLETE    # "degraded_complete"
```
