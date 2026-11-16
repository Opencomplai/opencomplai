# SDK API Reference

## Exported symbols

```python
from opencomplai import (
    assess,
    AgentDecisionLog,
    RuntimeReporter,  # from 0.16.0
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
| `framework_inputs` | `dict[str, FrameworkInputs]` | `{}` | Per framework: `excluded` (requirement id → reason) and `attested` (requirement id → `Attestation(statement, attested_by, attested_at, valid_until, evidence, record_id)`; the last three are optional), and optionally `scope` (`FrameworkScope`: yes/no answers `trains_models`, `uses_retrieval`, `public_api`). |
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

### `evaluate_targets(manifest, targets, *, commit_ref, risk_result=None, corroboration_report=None, eval_report=None, repo_root=None, today=None) -> dict[str, FrameworkReport]`

One `FrameworkReport` per framework. The EU AI Act entry always comes first, even when
it is not a target, because it is the evidence derived frameworks are built from; the
other targets follow in order. Each input resolves the rows that depend on it, as in
`opencomplai gaps`: `risk_result` the rule-backed EU AI Act articles,
`corroboration_report` the scan-backed rows, `eval_report` the evaluator-backed rows,
and `repo_root` the documentation probes. A row whose input is missing is
**Unverified**. Requirements excluded in `manifest.framework_inputs`, and native rows
that its `scope` answers rule out (see [ISO/IEC 27090](../concepts/iso-27090.md#scoping-rows-that-may-not-apply)),
move to `FrameworkReport.excluded`. An attestation is Unverified once its `valid_until`
is before `today` (default: the current UTC date). Raises `ValueError` on an unknown
framework, on `excluded` or `scope` for `EU_AI_ACT` (it takes `attested` for Art. 4
only, and for Art. 20 from 0.16.0), on an excluded or attested id the framework
does not accept, or on a blank exclusion reason.

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

## `AgentDecisionLog`

A tamper-evident, optionally signed log of an agent's decisions: a hash chain with one
entry per decision. Only metadata is stored. The tool input is hashed to
`sha256:<hex>` and never written.

```python
from pathlib import Path

from opencomplai import AgentDecisionLog

log = AgentDecisionLog("agent-log.jsonl", signing_key=Path("keys/agent.pem"))
log.record(
    agent_id="support-bot",
    tool="refund_order",
    intent="Refund order 1042 after a damaged-item report",
    tool_input={"order_id": 1042, "amount": 19.99},
    outcome="success",
    mandate_ref="MANDATE-7",
)
```

**Constructor:** `AgentDecisionLog(path, *, signing_key=None, clock=None)`. `path` is the
JSONL file. `signing_key` is a path to a PEM private key or the PEM bytes; without it,
entries are chained but unsigned.

| Method | Returns | Description |
|---|---|---|
| `record(*, agent_id, tool, intent, tool_input, outcome, mandate_ref=None, outside_mandate=False)` | `dict` | Appends one entry. `outcome` is `success`, `failure` or `blocked`. `intent` is at most 1000 characters. `tool_input` is stored only as its SHA-256. Raises `ValueError` on bad fields. |
| `entries()` | `list[dict]` | Every entry in order, with `seq`, `ts`, `prev_hash`, `hash` and `signature` when signed. |
| `head()` | `str` | Hash of the newest entry. |
| `len(log)` | `int` | Number of entries. |
| `verify(*, public_key=None, require_signed=False, expected_head=None, expected_count=None)` | `LogVerification` | Checks the chain, the schema of every entry and, when `public_key` is given, the signatures. Without a public key it checks chain integrity only. |

**`LogVerification` fields:** `ok`, `count`, `head`, `signed_count`,
`verified_signatures`, `error` and `bad_seq` (the first bad entry, when there is one).

**Truncation ceiling:** a chain cannot detect removal of the newest entries. Store
`head()` and `len(log)` outside the log, then pass them to `verify` as `expected_head`
and `expected_count` to catch truncation.

The same log is checked from the command line with
[`opencomplai agents verify-log`](../cli/agents.md) and
[`opencomplai verify --kind agent-log`](../cli/verify.md).

---

## Runtime events (from 0.16.0)

`RuntimeReporter` records what a running AI system does as small events, keeps them in a
local buffer file and sends them in batches. Only hashes and metadata are sent: ids, tool
names, outcomes, metric values and a SHA-256 of each tool input. The tool input itself,
free text and tool output are never recorded.

```python
from opencomplai import RuntimeReporter

with RuntimeReporter("support-bot") as reporter:
    reporter.decision(
        "support-bot", "refund_order", "success",
        {"order_ref": "ord_7Hq2xK9mWb4vTz1L", "amount": 19.99}, mandate_ref="MANDATE-7",
    )
    reporter.out_of_mandate(
        "support-bot", "delete_account", {"account_ref": "acct_Zk3pQ8vN2xR7wLd4"}
    )
    reporter.metric("latency_ms", 182.5, unit="ms")
    reporter.incident("high", "health_harm")
# leaving the block sends what was buffered
```

**Constructor:** `RuntimeReporter(system_id, *, api_key=None, base_url=None,
buffer_path=".opencomplai/runtime-events.jsonl", batch_size=100, max_buffered=10_000,
max_retries=3, backoff_s=0.5, timeout_s=10.0, total_timeout_s=30.0, transport=None,
clock=None, sleep=time.sleep)`. `system_id` is 1 to 200 characters. `batch_size` is 1 to 100.
`transport` and `clock` exist for tests: a transport takes `(url, headers, body,
timeout_s)` and returns the HTTP status, and a clock returns a `datetime`.

`api_key` and `base_url` default to the `OPENCOMPLAI_API_KEY` and
`OPENCOMPLAI_DASHBOARD_URL` environment variables, the same pair
[`opencomplai push`](../cli/push.md) uses. A URL must be `https`, or `http` to `localhost`,
`127.0.0.1` or `::1`, and a key may contain only printable ASCII characters; anything else
raises `ValueError` when the reporter is built. A request to an `http` address on this
machine never goes through a proxy set in the environment, so the key stays on the machine;
an `https` request follows the environment's proxy settings. With the key or the URL
missing the reporter is local-only: it keeps buffering and `flush()` reports
`not_configured`.

| Method | Description |
|---|---|
| `decision(agent_id, tool, outcome, tool_input, mandate_ref=None)` | One agent decision. `outcome` is `success`, `failure` or `blocked`. |
| `out_of_mandate(agent_id, tool, tool_input, mandate_ref=None)` | An action outside the agent's mandate. |
| `metric(name, value, unit=None)` | A number. `name` matches `[a-z][a-z0-9_.]{0,63}`, `value` is finite and between -1e15 and 1e15, `unit` matches `[a-z%/_]{1,16}`. |
| `incident(severity, incident_class)` | `severity` is `low`, `medium`, `high` or `critical`. `incident_class` is one of `unclassified`, `death`, `health_harm`, `critical_infrastructure`, `fundamental_rights`, `property_environment` or `widespread_infringement`. |
| `flush()` | Sends the buffer and returns a `FlushResult`. |
| `stats()` | `{"buffered", "dropped", "configured"}`. |
| `close()` | Flushes with a single attempt and no waiting between attempts. The context manager calls it on exit. |

`agent_id`, `tool` and `mandate_ref` are 1 to 128 characters. These and `system_id` hold no
control characters (C0 or C1), none of the characters that hide or reorder text (the same set a
[custom pack](../reference/custom-pack-format.md) refuses in its text, such as zero-width
characters, direction marks and line separators) and no unpaired surrogates (a character that has
no UTF-8 form). A label made only of white space is refused too.
Each recording method checks its arguments (`ValueError` on bad input or a metric value
that is not finite or is out of range), hashes `tool_input` the way `AgentDecisionLog` does, and appends one line to
the buffer. It makes no network call and starts no thread.

**What is sent.** `flush()` posts JSON to `{base_url}/v1/runtime-events` with an
`Authorization: Bearer` header, in batches of at most `batch_size` events and at most
200 000 bytes of UTF-8 text, whichever comes first. A batch holds
the `system_id`, the SDK version and the events; each event has a random `event_id` that
lets the receiver ignore a repeat, a `kind` (`decision_log`, `out_of_mandate`, `metric` or
`incident`), an `occurred_at` time in UTC, and only the fields listed above. The format is
the packaged JSON Schema `opencomplai/data/runtime_event.schema.json`, listed under
[Published schemas](../concepts/published-schemas.md). A receiver that stores a batch
answers `202` with `{"accepted": n, "duplicates": n}`.

**Buffering and retries.**

- The buffer is a JSON Lines file. It survives a restart, and a later `flush()` sends what
  an earlier run left behind. Use one buffer file per system and one process per file: a
  second reporter for another system on the same file raises `ValueError` in the same
  process, but nothing checks across processes. The buffer folder is created readable by
  its owner only (mode `0o700`) and the buffer, rejected and temporary files likewise
  (`0o600`); where the platform allows it, a symbolic link in place of one of them is
  refused rather than followed. Keep the buffer files
  (`.opencomplai/runtime-events.jsonl*`, including the `.rejected.jsonl` and `.tmp` files)
  out of version control. The same folder holds signed records that are meant to be
  committed, so do not ignore all of `.opencomplai/`.
- At `max_buffered` events, new events are dropped, counted in `stats()["dropped"]` and
  logged once as a warning.
- A sent batch leaves the buffer. On `408`, `429`, `5xx` or a network error `flush()`
  retries up to `max_retries` times, waiting `backoff_s * 2**attempt` seconds (never more
  than 60), then stops with `unreachable` and keeps the events. A single `flush()` also has
  a soft time limit: it gives up once `total_timeout_s` seconds have passed, across
  attempts and batches, and each network step waits at most the time that is left. The limit
  is soft: a slow name lookup or a peer that sends very slowly can run past it. `close()`
  makes one attempt, so closing a reporter never waits on a receiver that is down. `404`,
  `405` and `410` are handled the same way, because they usually mean a wrong address rather
  than a bad batch, and so is any other unexpected status. Redirects are never followed.
- On `401` or `403` it stops with `unauthorized` and keeps the events.
- A buffer line that is not a valid event is dropped, and counted in `rejected` once, when
  it leaves the buffer.
- On any other `4xx` the batch moves to `<buffer_path>.rejected.jsonl` (the newest
  `max_buffered` lines are kept), counts as rejected, and sending continues.

**`FlushResult` fields:** `sent` (events the receiver took), `rejected`, `remaining` and
`error`. `error` is `None` or one of `not_configured`, `unreachable`, `unauthorized` or
`buffer_error`. These are fixed codes: no exception text, response body or API key is ever
put in them, and `flush()` does not raise for a network problem. The reporter writes to
the `opencomplai.runtime` logger and never prints.

**Choose inputs with care.** A hash of a short or guessable tool input can be reversed by
trying candidates. Do not pass low-entropy inputs you consider sensitive, such as a
yes/no answer or a small numeric id, as `tool_input`. Pass something with enough free
content to resist guessing, such as a long opaque reference.

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
