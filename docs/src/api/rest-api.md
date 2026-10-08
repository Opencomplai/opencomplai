# Gateway API — REST Reference

The Opencomplai gateway API is the HTTP entry point for the Docker Compose stack. All endpoints are prefixed `/v1/` except `GET /health`.

**Base URL (default):** `http://localhost:8080`
**Content-Type:** `application/json` for all request and response bodies.
**Authentication:** every endpoint except `GET /health` needs credentials; see [Authentication](#authentication).

A manifest can name several frameworks to assess side by side (`compliance_targets`). Risk classification (`/v1/risk/classify`), dossier generation (`/v1/docs/generate`) and the risk engine's public `/v1/checker/*` routes are **EU AI Act only**.

---

## Authentication

Every endpoint except `GET /health` requires credentials. The gateway is fail-closed: it refuses to start unless authentication is configured, or explicitly switched off for local development with `OPENCOMPLAI_AUTH_DISABLED=1`. A deployment uses one of two modes; see [Authentication](../deployment/authentication.md) to set them up.

| Mode | Send | Notes |
|---|---|---|
| API key (self-hosted) | `x-api-key: <OPENCOMPLAI_API_KEY>` | A shared key authenticates the deployment as a whole, as the tenant named by `OPENCOMPLAI_API_KEY_TENANT_ID` (default `oss-default`). |
| OIDC (multi-user) | `Authorization: Bearer <jwt>` | An RS256 token from your identity provider. It must carry the tenant claim named by `OIDC_TENANT_CLAIM`. |

When `OIDC_JWKS_URI` is set the gateway uses OIDC mode and ignores `OPENCOMPLAI_API_KEY`.

```bash
curl -s http://localhost:8080/v1/portfolio -H "x-api-key: $OPENCOMPLAI_API_KEY"
```

Authentication and rate limiting add these responses to every `/v1` endpoint:

| Status | `error_code` | When |
|---|---|---|
| `401` | `POLICY_DENIED` | Credentials are missing or invalid. |
| `429` | `RATE_LIMITED` | A client made more than 10 failed authentication attempts within 60 seconds (`OPENCOMPLAI_AUTH_FAILURE_RATE_LIMIT_MAX` and `OPENCOMPLAI_AUTH_FAILURE_RATE_LIMIT_WINDOW_MS`). Further failures return `429` instead of `401`. |
| `429` | none | A client made more than 300 requests within 60 seconds (`OPENCOMPLAI_RATE_LIMIT_MAX` and `OPENCOMPLAI_RATE_LIMIT_WINDOW_MS`; the Docker Compose stack sets 1000). Also applies to `GET /health`. |

The first two use the gateway error envelope below. The last is the rate limiter's own body, with a `Retry-After` header in seconds:

```json
{
  "statusCode": 429,
  "error": "Too Many Requests",
  "message": "Rate limit exceeded, retry in 1 minute"
}
```

---

## Error responses

Errors come in three shapes, depending on who produced them.

**Gateway envelope.** The gateway itself answers with this body when authentication fails, when it rejects a request body, and when it cannot reach an internal service:

```json
{
  "error_code": "DEPENDENCY_UNAVAILABLE",
  "message": "Upstream service unavailable: http://risk-engine:8001/v1/risk/classify",
  "category": "dependency",
  "retryable": true,
  "correlation_id": "req-1"
}
```

| Field | Type | Description |
|---|---|---|
| `error_code` | `string` | Machine-readable error identifier (see table below). |
| `message` | `string` | Human-readable description. |
| `category` | `string` | `client` (fix the request), `policy` (authentication or rate limiting refused it), `dependency` (an internal service could not be reached) or `validation` (only `GET /v1/docs`, for a missing `system_id`). |
| `retryable` | `bool` | `true` if the same request may succeed on retry. |
| `correlation_id` | `string` | Request ID; include in support reports. |

| Code | HTTP status | Category | Meaning |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | `client` | The gateway rejected the request body, for example a missing `system_id` or `rationale`. `GET /v1/docs` reports `validation` here. |
| `POLICY_DENIED` | 401 | `policy` | Credentials are missing or invalid. |
| `RATE_LIMITED` | 429 | `policy` | Too many failed authentication attempts. |
| `DEPENDENCY_UNAVAILABLE` | 503 | `dependency` | The gateway could not reach an internal service. |

**Forwarded service errors.** When an internal service answers with an error, the gateway returns that response unchanged, status code included. The services are FastAPI apps, so the body is `{"detail": ...}` where `detail` is a string, an object (for example `{"error_code": "IDEMPOTENCY_CONFLICT", "message": "...", "category": "client", "retryable": false}`) or, for request validation failures, a list of error objects. A `404`, `409`, `422` or `502` on a proxied endpoint therefore usually has this shape rather than the envelope. Each endpoint below says which one it returns.

| Code | HTTP status | Endpoint |
|---|---|---|
| `IDEMPOTENCY_CONFLICT` | 409 | `POST /v1/hitl/overrides`, `POST /v1/hitl/queue/{id}/decide` |
| `ALREADY_COMPLETED` | 409 | `POST /v1/hitl/overrides/{override_id}/second-approval` |
| `RATIONALE_HASH_MISMATCH` | 409 | `POST /v1/hitl/overrides/{override_id}/second-approval` |
| `AUDIT_UNAVAILABLE` | 503 | `POST /v1/hitl/overrides`, `POST /v1/hitl/overrides/{override_id}/second-approval`, `POST /v1/hitl/queue/{id}/decide` |
| `DOSSIER_SCHEMA_INVALID` | 422 | `POST /v1/docs/generate` |

**Egress proxy errors.** The egress proxy's refusals are not wrapped in `detail`: `POST /v1/sync/metadata` returns `EGRESS_BLOCKED` (403) as `{"error_code", "message", "category": "policy", "retryable", "policy_hash"}`.

---

## `GET /health`

Health check for the gateway API process. The only endpoint that needs no credentials.

**Request:** No body.

**Response `200`:**

```json
{
  "status": "ok",
  "service": "gateway-api",
  "version": "0.9.0"
}
```

---

## `POST /v1/manifests/validate`

Validate a system manifest against the `SystemManifest` schema and forward to the risk engine for further validation.

**Request body:**

```json
{
  "system_id": "loan-decision-model",
  "intended_purpose": "automated credit scoring for retail lending",
  "compliance_targets": ["EU_AI_ACT", "NIST_AI_RMF"],
  "framework_inputs": {
    "NIST_AI_RMF": {
      "excluded": {"NIST_AI_RMF:MAP 1.1": "Internal tool, no external users"}
    }
  },
  "high_risk_presumption": false,
  "commit_ref": "abc1234"
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `system_id` | `string` | | — | Unique system identifier. |
| `intended_purpose` | `string` | | — | Primary intended purpose. |
| `compliance_target` | `string` | | `EU_AI_ACT` | Legacy single framework (`EU_AI_ACT` or `NIST_AI_RMF`). Ignored when `compliance_targets` is set. |
| `compliance_targets` | `string[]` | | — | Frameworks to assess side by side, e.g. `["EU_AI_ACT", "NIST_AI_RMF"]`. Must be non-empty. |
| `framework_inputs` | `object` | | `{}` | Per framework id: `excluded` (requirement id → reason) and `attested` (requirement id → `{statement, attested_by, attested_at}`). Requirement ids carry the framework prefix, e.g. `NIST_AI_RMF:GOVERN 1.1`. |
| `high_risk_presumption` | `bool` | | `false` | Provider presumes high risk. |
| `commit_ref` | `string` | | `HEAD` | Git commit reference. |

**Response `200`:**

```json
{
  "valid": true,
  "manifest": {
    "system_id": "loan-decision-model",
    "intended_purpose": "automated credit scoring for retail lending",
    "compliance_targets": ["EU_AI_ACT", "NIST_AI_RMF"],
    "high_risk_presumption": false,
    "commit_ref": "abc1234"
  }
}
```

`manifest` is the validated manifest with defaults applied; the example is shortened.

**Response `422`:** `VALIDATION_ERROR` in the gateway envelope when the gateway rejects the body: a required field missing or empty, a wrong type, or an empty `compliance_targets` list. An unknown framework id is rejected by the risk engine instead and comes back as `{"detail": "<message>"}`.

---

## `POST /v1/risk/classify`

**EU AI Act only.** Classify the risk level of an AI system under EU AI Act Annex III.

**Request body:**

```json
{
  "system_id": "loan-decision-model",
  "intended_purpose": "automated credit scoring for retail lending"
}
```

**Response `200`:**

```json
{
  "risk_class": "high",
  "trap_detected": false,
  "profiling_detected": false,
  "rationale_hash": "sha256:3e2f1a...",
  "evidence_event_id": "evt_sha256:9c1d4f..."
}
```

| Field | Type | Description |
|---|---|---|
| `risk_class` | `string` | `unacceptable`, `high`, `limited`, or `minimal`. |
| `trap_detected` | `bool` | `true` if the substantial-modification trap rule triggered. |
| `profiling_detected` | `bool` | `true` if an Art. 6 profiling signal was detected. |
| `rationale_hash` | `string` | SHA-256 of the assessment rationale. |
| `evidence_event_id` | `string` | Deterministic `evt_sha256:<hex>` digest of the classification request (system_id, intended_purpose, features, change_context, rationale_hash). It is **not** the id of a ledger event — `POST /v1/risk/classify` does not append anything to the evidence-vault ledger. |

---

## `POST /v1/verify/claims`

Submit a ground-truth verification task (REQ-GTVG-001).

**Request body:**

```json
{
  "system_id": "loan-decision-model",
  "claim_ref": "accuracy-claim-2026-05",
  "source_ref": "https://internal-benchmarks/accuracy",
  "expected_value": "0.94"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `system_id` | `string` | | System identifier. |
| `claim_ref` | `string` | | Reference identifying the claim. |
| `source_ref` | `string` | | Ground-truth source URI. |
| `expected_value` | `string` | | Expected value for assertion-style verification. |

**Response `200`:**

```json
{
  "task_id": "b7f3a1e2-...",
  "claim_ref": "accuracy-claim-2026-05",
  "source_ref": "https://internal-benchmarks/accuracy",
  "outcome": "pending"
}
```

`outcome` is `pending` until the verification task worker completes. Poll or wait for the `compliance_check_completed` event.

---

## `POST /v1/hitl/overrides`

Submit a human-in-the-loop override with a mandatory rationale (REQ-HITL-001). The decision is written to the evidence ledger before it is accepted; if the ledger is unavailable the request fails with `503` `AUDIT_UNAVAILABLE` and nothing is recorded.

**Request body:**

```json
{
  "case_id": "case-2026-0142",
  "actor_id": "j.doe@example.com",
  "rationale": "Applicant income verified manually against payslips.",
  "decision": "approved"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `case_id` | `string` | | Identifier of the case being overridden. |
| `actor_id` | `string` | | Who made the decision. The gateway replaces it with the authenticated caller's identity (the JWT `sub` claim, or `api-key-caller` in API-key mode); your value is kept only when authentication is disabled or the token has no `sub` claim. See [Authentication](../deployment/authentication.md). |
| `rationale` | `string` | | Why the decision was made. Must contain non-whitespace characters. Only its hash is stored. |
| `decision` | `string` | | `approved` or `rejected`. |
| `requires_dual_approval` | `boolean` | | Optional. When `true`, the response `status` is `pending_second_approval` until a second approver completes it with `POST /v1/hitl/overrides/{override_id}/second-approval`. |
| `idempotency_key` | `string` | | Same key and same payload returns the original response; same key with a different payload is rejected with `409`. Derived from the payload when omitted. |

**Response `201`:**

```json
{
  "override_id": "ovr_sha256:7a0c19...",
  "rationale_hash": "sha256:3e2f1a...",
  "status": "accepted",
  "vault_event_id": "e1a2b3c4-..."
}
```

**Response `422`:** `VALIDATION_ERROR` — `case_id`, `actor_id` or `rationale` is missing or empty, or `decision` is not `approved` or `rejected`. A whitespace-only `rationale` is rejected by the risk engine and comes back as `{"detail": {...}}` instead of the envelope.

**Response `409`:** `IDEMPOTENCY_CONFLICT` — `idempotency_key` was already used with a different payload. Returned as `{"detail": {...}}`.

---

## `POST /v1/hitl/overrides/{override_id}/second-approval`

Complete a dual-control override that was started with `requires_dual_approval`. A second approver, distinct from the first, confirms or rejects it. The `override_second_approved` event is written to the evidence ledger before the request is accepted; if the ledger is unavailable the request fails with `503` `AUDIT_UNAVAILABLE` and the override stays pending, so the call can be retried. In API-key mode every caller is the same principal (`api-key-caller`), so two distinct approvers need JWT/OIDC authentication.

**Request body:**

```json
{
  "actor_id": "m.roe@example.com",
  "rationale": "Reviewed the payslips and agree with the first approver.",
  "rationale_hash": "sha256:3e2f1a...",
  "decision": "approved"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `actor_id` | `string` | | Who is approving. The gateway replaces it with the authenticated caller's identity, as in `POST /v1/hitl/overrides`. |
| `rationale` | `string` | | Mandatory; must contain non-whitespace characters. Only its hash is stored. |
| `rationale_hash` | `string` | | The `rationale_hash` returned by the first approval. |
| `decision` | `string` | | `approved` (default) or `rejected`. |

**Response `201`:**

```json
{
  "override_id": "ovr_sha256:7a0c19...",
  "rationale_hash": "sha256:9d4b02...",
  "status": "accepted",
  "vault_event_id": "e1a2b3c4-..."
}
```

`status` is `accepted` or, when the second approver rejects, `rejected`; `rationale_hash` is the hash of the second rationale.

**Response `403`:** `POLICY_DENIED` — the second approver is the same actor as the first. **Response `404`:** no pending override with this id. **Response `409`:** `ALREADY_COMPLETED` or `RATIONALE_HASH_MISMATCH`. **Response `422`:** `VALIDATION_ERROR`. **Response `503`:** `AUDIT_UNAVAILABLE`.

---

## `GET /v1/hitl/queue`

List items in the human-review queue.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `state` | `string` | | Only items in this state: `queued`, `assigned`, `decided` or `expired`. |
| `assigned_to` | `string` | | Only items assigned to this reviewer. |

**Response `200`:**

```json
{
  "items": [
    {
      "review_id": "rev_sha256:5b1c8e...",
      "tenant_id": "default",
      "system_id": "loan-decision-model",
      "commit_ref": "abc1234",
      "reason": "evaluator_fail",
      "state": "assigned",
      "payload_ref": "sha256:9c1d4f...",
      "context_ref": "sha256:3e2f1a...",
      "reviewer_group": "compliance-reviewers",
      "assigned_to": "compliance-reviewers:member-0",
      "idempotency_key": "rev_sha256:5b1c8e...",
      "created_at": "2026-05-25T10:00:00+00:00",
      "expires_at": "2026-05-28T10:00:00+00:00",
      "decided_at": null,
      "linked_override_id": null
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `review_id` | `string` | Deterministic `rev_sha256:<hex>` id of the item. |
| `reason` | `string` | Why the item was queued: `low_confidence`, `evaluator_fail`, `modification_trap`, `policy_block`, `manual`, `manifest_discrepancy`, `evidence_stale` or `manifest_change`. |
| `state` | `string` | `queued`, `assigned`, `decided` or `expired`. |
| `payload_ref` | `string` | Reference to the payload under review. |
| `context_ref` | `string` | Reference to the item's redacted reviewer context. |
| `reviewer_group`, `assigned_to` | `string` or `null` | Group the item was routed to and the reviewer it is assigned to. |
| `expires_at`, `decided_at` | `string` or `null` | ISO 8601 timestamps. |
| `linked_override_id` | `string` or `null` | Override recorded by the decision, once decided. |

The remaining fields (`tenant_id`, `system_id`, `commit_ref`, `idempotency_key`, `created_at`) identify the item and when it was created.

---

## `GET /v1/hitl/queue/{id}`

Get one review item together with its redacted reviewer context. The context never carries raw prompts, outputs or personal data.

**Response `200`:**

```json
{
  "item": {
    "review_id": "rev_sha256:5b1c8e...",
    "tenant_id": "default",
    "system_id": "loan-decision-model",
    "commit_ref": "abc1234",
    "reason": "evaluator_fail",
    "state": "assigned",
    "payload_ref": "sha256:9c1d4f...",
    "context_ref": "sha256:3e2f1a...",
    "reviewer_group": "compliance-reviewers",
    "assigned_to": "compliance-reviewers:member-0",
    "idempotency_key": "rev_sha256:5b1c8e...",
    "created_at": "2026-05-25T10:00:00+00:00",
    "expires_at": "2026-05-28T10:00:00+00:00",
    "decided_at": null,
    "linked_override_id": null
  },
  "context": {
    "review_id": "pending",
    "reason": "evaluator_fail",
    "detector_ids": ["..."],
    "masked_excerpts": [],
    "aggregate_counts": {"failed": 1},
    "evidence_hashes": ["sha256:9c1d4f..."]
  }
}
```

`context` is `null` when no context is stored for the item.

**Response `404`:** the review item does not exist. Returned as `{"detail": "Review item not found"}`.

---

## `POST /v1/hitl/queue/{id}/assign`

Assign a review item to a reviewer.

**Request body:**

```json
{
  "reviewer_id": "j.doe@example.com"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `reviewer_id` | `string` | | Reviewer to assign. The gateway replaces it with the authenticated caller's identity, as it does `actor_id` in `POST /v1/hitl/overrides`. |

**Response `200`:** `{"item": {...}}` — the updated review item, now `assigned` to the reviewer.

**Response `404`:** the review item does not exist. **Response `422`:** `VALIDATION_ERROR` — `reviewer_id` missing or empty.

---

## `POST /v1/hitl/queue/{id}/decide`

Record the decision on a review item. This submits a HITL override with the review id as the case (same rules as `POST /v1/hitl/overrides`) and marks the item `decided`.

**Request body:**

```json
{
  "actor_id": "j.doe@example.com",
  "decision": "rejected",
  "rationale": "Evaluator failure confirmed on manual re-run."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `actor_id` | `string` | | Who made the decision. The gateway replaces it with the authenticated caller's identity, as in `POST /v1/hitl/overrides`. |
| `decision` | `string` | | `approved` or `rejected`. |
| `rationale` | `string` | | Mandatory; must contain non-whitespace characters. |
| `idempotency_key` | `string` | | Defaults to `decide-<review id>`, so a second decision on the same item replays the first unless its payload differs. |

**Response `201`:** `{"item": {...}, "override": {...}}` — the updated review item (`decided`, with `linked_override_id` set) and the override as returned by `POST /v1/hitl/overrides`.

**Response `404`:** the review item does not exist. **Response `409`:** `IDEMPOTENCY_CONFLICT`. **Response `422`:** `VALIDATION_ERROR`. **Response `503`:** `AUDIT_UNAVAILABLE` — the ledger write failed and the decision was not recorded.

---

## `POST /v1/docs/generate`

**EU AI Act only.** Generate an EU AI Act Annex IV technical documentation dossier (REQ-DOC-001). The gateway forwards the body unchanged to the doc generator, which validates it. The dossier is stored in the evidence vault and can be fetched later with `GET /v1/docs/{dossier_id}`.

**Request body:**

```json
{
  "system_id": "loan-decision-model",
  "commit_ref": "abc1234",
  "intended_purpose": "automated credit scoring for retail lending",
  "provider_name": "ACME Financial AI"
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `system_id` | `string` | yes | — | System identifier. |
| `commit_ref` | `string` | yes | — | Git commit reference. There is no default. |
| `intended_purpose` | `string` | | `Not specified` | Primary intended purpose. |
| `provider_name` | `string` | | `Unknown Provider` | Legal name of the provider. |
| `compliance_target` | `string` | | `EU_AI_ACT` | Framework target recorded in the dossier. Must be `EU_AI_ACT` or `NIST_AI_RMF`; any other value fails with `500` `SYSTEM_ERROR`. |
| `high_risk_presumption` | `bool` | | `false` | Provider presumes high risk. |
| `allow_incomplete` | `bool` | | `false` | Accept a dossier that fails the Annex IV schema check (the response then has `schema_valid: false`) instead of refusing it with `422`. |

The request also accepts the optional Annex IV inputs `training_data_description`, `model_architecture`, `performance_metrics` (an object of numbers), `known_limitations`, `human_oversight_measures`, `monitoring_approach`, `incident_response_procedure`, `metrics_appropriateness_rationale`, `lifecycle_changes`, `change_log_reference`, `harmonised_standards`, `alternative_solutions`, `eu_declaration_of_conformity_ref`, `post_market_monitoring_plan_ref` and `post_market_monitoring_summary`, which are recorded in the dossier as given, and the full `eval_report` and `corroboration_report` objects, which are validated before use.

**Response `200`:**

```json
{
  "dossier_id": "d4f9c2a1-...",
  "bundle_checksum": "sha256:3e2f1a...",
  "status": "generated",
  "duration_ms": 142,
  "signature": null,
  "schema_valid": true,
  "content_hash": "sha256:7d2e90...",
  "ledger_event_id": "e1a2b3c4-..."
}
```

| Field | Type | Description |
|---|---|---|
| `dossier_id` | `string` | Pass it to `GET /v1/docs/{dossier_id}`. |
| `bundle_checksum` | `string` | Checksum of the dossier bundle. |
| `status` | `string` | Always `generated`; a failure comes back as an error status instead. |
| `duration_ms` | `int` | Generation time in milliseconds. |
| `signature` | `string` or `null` | Signature carried by the dossier, if any. |
| `schema_valid` | `bool` | `false` only when `allow_incomplete` was set and the dossier failed the Annex IV schema check. |
| `content_hash`, `ledger_event_id` | `string` or `null` | Content hash of the stored dossier and the ledger event that records it. |

**Response `422`:** returned as `{"detail": ...}`. By default a dossier that fails the Annex IV schema check is refused with `DOSSIER_SCHEMA_INVALID`. It is still stored, and `detail` carries `dossier_id`, `bundle_checksum`, `content_hash`, `ledger_event_id` and `schema_valid: false`, so you can retrieve what failed with `GET /v1/docs/{dossier_id}`; set `allow_incomplete` to receive `200` instead. `INVALID_EVAL_REPORT` and `INVALID_CORROBORATION_REPORT` mean the matching report object did not validate, and a missing `system_id` or `commit_ref` returns a list of validation errors.

**Response `500`:** `SYSTEM_ERROR` — generation failed unexpectedly. **Response `502`:** the dossier was generated but could not be stored in the evidence vault.

---

## `GET /v1/docs`

**EU AI Act only.** List the dossiers generated for a system, newest first.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `system_id` | `string` | yes | System whose dossiers to list. |

**Response `200`:**

```json
{
  "system_id": "loan-decision-model",
  "count": 1,
  "dossiers": [
    {
      "dossier_id": "d4f9c2a1-...",
      "system_id": "loan-decision-model",
      "commit_ref": "abc1234",
      "content_hash": "sha256:7d2e90...",
      "bundle_checksum": "sha256:3e2f1a...",
      "ledger_event_id": "e1a2b3c4-...",
      "created_at": "2026-05-25T10:00:00+00:00"
    }
  ]
}
```

**Response `422`:** `VALIDATION_ERROR` — `system_id` is missing.

---

## `GET /v1/docs/{dossier_id}`

**EU AI Act only.** Retrieve a previously generated dossier by the `dossier_id` that `POST /v1/docs/generate` returned.

**Response `200`:** the index fields shown for `GET /v1/docs` plus the stored dossier:

```json
{
  "dossier_id": "d4f9c2a1-...",
  "system_id": "loan-decision-model",
  "commit_ref": "abc1234",
  "bundle_checksum": "sha256:3e2f1a...",
  "content_hash": "sha256:7d2e90...",
  "ledger_event_id": "e1a2b3c4-...",
  "created_at": "2026-05-25T10:00:00+00:00",
  "dossier": {}
}
```

`dossier` is the Annex IV dossier JSON as it was generated. `bundle_checksum` and `ledger_event_id` let you verify it and trace the ledger event that anchors it.

**Response `404`:** no such dossier for the caller's tenant. Returned as `{"detail": "Dossier not found: <dossier_id>"}`. **Response `502`:** the dossier index or its stored content could not be read.

---

## `POST /v1/evidence/events`

Append an event to the append-only Merkle-linked evidence ledger.

**Request body:**

```json
{
  "event_type": "compliance_check_started",
  "payload": {
    "install_id": "a1b2c3d4-...",
    "system_id": "loan-decision-model",
    "commit_ref": "abc1234",
    "scan_mode": "ci"
  },
  "signer_id": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `event_type` | `string` | yes | Event type identifier (e.g. `compliance_check_started`). |
| `payload` | `object` | yes | Event-specific payload object. |
| `signer_id` | `string` or `null` | | Identity of the human signer for HITL events. |

**Response `201`:**

```json
{
  "event_id": "e1a2b3c4-...",
  "payload_hash": "sha256:9c1d4f...",
  "prev_hash": "sha256:41ab07..."
}
```

`prev_hash` is the chain tip the new event links to.

---

## `GET /v1/evidence/verify-chain`

Verify the integrity of the caller's evidence ledger. Each tenant has its own independent chain.

**Response `200`:**

```json
{
  "valid": true
}
```

`valid` is `true` when every event still links to its predecessor.

---

## `GET /v1/evidence/ledger-root`

Return the current Merkle tip of the ledger: the hash an Annex IV dossier anchors to, so later tampering with older events can be detected.

**Response `200`:**

```json
{
  "ledger_root_hash": "sha256:9c1d4f..."
}
```

For an empty ledger this is the genesis hash, the SHA-256 of the empty string.

---

## `GET /v1/evidence/ledger-history-tips`

Return the rolling Merkle tip after every event, so you can confirm that a dossier's recorded `ledger_root_hash` is a real point in the chain. Read the chain a page at a time with `limit` and `after_seq`; without them the whole list comes back in one response, which is only allowed for ledgers of up to 10,000 events.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `limit` | `integer` | | Number of per-event tips to return, 1 to 5000. Selects the paged response. |
| `after_seq` | `integer` | | Return tips only for events after this sequence number (default `0`, from the start). Take it from the previous page's `next_after_seq`. Requires `limit`; without it the request fails with `422`. |

**Response `200`, without `limit`:**

```json
{
  "tips": ["sha256:e3b0c4...", "sha256:9c1d4f..."],
  "count": 2
}
```

`tips` lists the genesis hash first, then the tip after each event in append order.

**Response `200`, with `limit`:**

```json
{
  "genesis": "sha256:e3b0c4...",
  "tips": ["sha256:9c1d4f...", "sha256:41ab07..."],
  "count": 2,
  "next_after_seq": 2
}
```

`genesis` is the hash of an empty ledger and is not part of `tips`, which holds only the per-event tips of this page. Pass `next_after_seq` back as `after_seq` to fetch the next page; it is `null` on the last page. Each page is read from the database with a bounded query, so memory use does not grow with the ledger.

**Response `413`:** the ledger has more than 10,000 events and the request did not use `limit`. Page through it with `limit` and `after_seq`.

**Response `422`:** `after_seq` was given without `limit`, or a parameter is out of range.

---

## `POST /v1/sync/metadata`

Sync allowlisted metadata to the Premium Dashboard via the egress proxy. The proxy accepts only these fields: `system_id`, `commit_ref`, `policy_bundle_version`, `risk_class`, `control_pass_rate`, `control_fail_rate`, `pending_verifications_count`, `bundle_checksum`, `size_bytes`, `signed_by`, `timestamp`, `pass_count`, `fail_count`, `trap_frequency`, `override_rate`, `eval_set_id`, `eval_overall_outcome` and `eval_failed_evaluator_ids`. A body with any other key is refused whole.

**Request body:**

```json
{
  "system_id": "loan-decision-model"
}
```

**Response `200`:** when no dashboard is configured (`PRO_DASHBOARD_URL` unset) nothing is sent anywhere; the proxy only confirms that the body is allowed:

```json
{
  "status": "synced",
  "destination": null,
  "fields_validated": true,
  "field_count": 1
}
```

`field_count` is the number of fields in the request body. When a dashboard is configured the proxy forwards the body to it and returns the dashboard's own response and status.

**Response `403`:** `EGRESS_BLOCKED` — the body has a field outside the allowlist, or the dashboard URL is not an allowed destination. The body is `{"error_code": "EGRESS_BLOCKED", "message": "...", "category": "policy", "retryable": false, "policy_hash": "sha256:..."}`. See [Air-gap](../deployment/airgap.md).

**Response `503`:** `DEPENDENCY_UNAVAILABLE` — the configured dashboard could not be reached.

---

## `GET /v1/status`

Aggregate status of every downstream service. Probes risk-engine, evidence-vault, doc-generator and egress-proxy and reports each one. This is not a liveness probe; use `GET /health` for that.

**Query parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `strict` | `string` | | `1` or `true` returns `503` instead of `200` whenever any service is not `ok`. The body is the same either way. |

**Response `200`:** an object with `status`, `service`, `version`, `checked_at` and a `services` map with one entry per downstream service. The response fields, the `strict` flag and how to monitor with them are described in [Observability — `GET /v1/status`](../deployment/observability.md).

---

## `GET /v1/portfolio`

List the AI systems on record for the caller's tenant, each with its most recently issued compliance badge. A system appears only once it has at least one badge.

**Response `200`:**

```json
{
  "systems": [
    {
      "system_id": "loan-decision-model",
      "badge_id": "sha256:5b1c8e...",
      "bundle_checksum": "sha256:3e2f1a...",
      "issued_at": "2026-05-25T10:00:00+00:00",
      "status": "compliant"
    }
  ],
  "count": 1
}
```

Entries are sorted by `system_id`.

---

## `POST /v1/pro/badges/issue`

Issue a compliance badge for a passing scan status artifact. Idempotent: issuing the same `system_id` and `bundle_checksum` again returns the existing badge.

**Request body:**

```json
{
  "system_id": "loan-decision-model",
  "bundle_checksum": "sha256:3e2f1a...",
  "artifact": {
    "result": "pass",
    "pending_verifications_count": 0
  },
  "signature": null
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `system_id` | `string` | | 1 to 128 characters from `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`. |
| `bundle_checksum` | `string` | | Checksum of the dossier bundle the artifact describes. |
| `artifact` | `object` | | The scan status artifact. Must have `result` of `pass` and `pending_verifications_count` of `0`; a missing count counts as pending. |
| `signature` | `string` or `null` | | Required when the evidence vault has a badge public key configured (`OSS_BADGE_PUBLIC_KEY_PATH`); must then verify against it. |

**Response `201`:**

```json
{
  "badge_id": "sha256:5b1c8e...",
  "system_id": "loan-decision-model",
  "issued_at": "2026-05-25T10:00:00+00:00",
  "status_artifact_hash": "sha256:9c1d4f...",
  "created": true
}
```

`created` is `false` when the badge already existed; the status is still `201`.

**Response `422`:** the artifact does not meet the issuance criteria, the signature is missing or invalid, or the body failed validation. Returned as `{"detail": ...}`.

---

## `GET /v1/pro/badges/verify/{badgeId}`

Return a badge's metadata without exposing the raw artifact.

**Response `200`:**

```json
{
  "badge_id": "sha256:5b1c8e...",
  "system_id": "loan-decision-model",
  "bundle_checksum": "sha256:3e2f1a...",
  "issued_at": "2026-05-25T10:00:00+00:00",
  "status_artifact_hash": "sha256:9c1d4f...",
  "valid": true
}
```

**Response `404`:** no such badge for the caller's tenant. Returned as `{"detail": "Badge not found: <badgeId>"}`.

---

## `GET /v1/pro/badges/{badgeId}/svg`

Return the badge's SVG markup. The evidence vault serves the badge as `image/svg+xml`, but the gateway does not forward that body as it is: it wraps the SVG text in a JSON object and returns it as `application/json`. Like every `/v1` endpoint it needs credentials, so the URL cannot be used directly as the `src` of a README image; fetch it with a credential and use the `raw` value.

**Response `200`:**

```json
{
  "raw": "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"200\" height=\"20\">...</svg>"
}
```

`raw` is the complete SVG document as a string.

**Response `404`:** no such badge for the caller's tenant. Returned as `{"detail": "Badge not found: <badgeId>"}`.

---

## `POST /v1/pro/ingest/status-artifact`

Record a scan status artifact in the evidence ledger (a `pro_status_artifact_ingested` event). The request goes through the egress proxy to the evidence vault.

**Request body:**

```json
{
  "system_id": "loan-decision-model",
  "commit_ref": "abc1234",
  "result": "pass",
  "failed_controls": [],
  "pending_verifications_count": 0
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `system_id` | `string` | | — | System identifier. |
| `result` | `string` | | — | Scan result. |
| `commit_ref` | `string` or `null` | | — | Git commit reference. |
| `failed_controls` | `string[]` | | `[]` | Controls that failed. |
| `pending_verifications_count` | `int` | | `0` | Verification tasks still pending. |
| `rationale_hash` | `string` or `null` | | — | Hash of the assessment rationale. |
| `bundle_checksum` | `string` or `null` | | — | Checksum of the dossier bundle. |
| `risk_class` | `string` or `null` | | — | Risk class of the system. |
| `timestamp` | `string` or `null` | | — | When the artifact was produced. |

**Response `201`:**

```json
{
  "event_id": "e1a2b3c4-...",
  "payload_hash": "sha256:9c1d4f..."
}
```

---

## `POST /v1/pro/ingest/dossier-metadata`

Record dossier metadata in the evidence ledger (a `pro_dossier_metadata_ingested` event). The request goes through the egress proxy to the evidence vault.

**Request body:**

```json
{
  "system_id": "loan-decision-model",
  "policy_bundle_version": "2026.05",
  "bundle_checksum": "sha256:3e2f1a...",
  "size_bytes": 48213
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `system_id` | `string` | | System identifier. |
| `policy_bundle_version` | `string` or `null` | | Version of the policy bundle. |
| `bundle_checksum` | `string` or `null` | | Checksum of the dossier bundle. |
| `size_bytes` | `int` or `null` | | Size of the bundle in bytes. |
| `signed_by` | `string` or `null` | | Who signed the bundle. |
| `timestamp` | `string` or `null` | | When the dossier was produced. |

**Response `201`:** `{"event_id": "...", "payload_hash": "sha256:..."}`, as for `POST /v1/pro/ingest/status-artifact`.

---

## `POST /v1/pro/ingest/metrics`

Record compliance metrics in the evidence ledger (a `pro_metrics_ingested` event). The request goes through the egress proxy to the evidence vault.

**Request body:**

```json
{
  "system_id": "loan-decision-model",
  "pass_count": 41,
  "fail_count": 2,
  "control_pass_rate": 0.95
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `system_id` | `string` | | System identifier. |
| `pass_count`, `fail_count` | `int` or `null` | | Number of controls that passed and failed. |
| `control_pass_rate`, `control_fail_rate` | `number` or `null` | | Fraction of controls that passed and failed. |
| `trap_frequency` | `number` or `null` | | How often the substantial-modification trap fired. |
| `override_rate` | `number` or `null` | | Rate of human overrides. |
| `timestamp` | `string` or `null` | | When the metrics were computed. |

**Response `201`:** `{"event_id": "...", "payload_hash": "sha256:..."}`, as for `POST /v1/pro/ingest/status-artifact`.

---

## Endpoint summary

| Method | Path | Service | Description |
|---|---|---|---|
| `GET` | `/health` | gateway-api | Health check (no credentials) |
| `POST` | `/v1/manifests/validate` | risk-engine | Validate system manifest |
| `POST` | `/v1/risk/classify` | risk-engine | Classify risk level (EU AI Act only) |
| `POST` | `/v1/verify/claims` | risk-engine | Submit verification task |
| `POST` | `/v1/hitl/overrides` | risk-engine | Submit HITL override |
| `POST` | `/v1/hitl/overrides/{override_id}/second-approval` | risk-engine | Complete a dual-control override |
| `GET` | `/v1/hitl/queue` | risk-engine | List review queue items |
| `GET` | `/v1/hitl/queue/{id}` | risk-engine | Get review item with redacted context |
| `POST` | `/v1/hitl/queue/{id}/assign` | risk-engine | Assign review item to a reviewer |
| `POST` | `/v1/hitl/queue/{id}/decide` | risk-engine | Record decision on a review item |
| `POST` | `/v1/docs/generate` | doc-generator | Generate Annex IV dossier (EU AI Act only) |
| `GET` | `/v1/docs` | doc-generator | List a system's dossiers (EU AI Act only) |
| `GET` | `/v1/docs/{dossier_id}` | doc-generator | Retrieve a dossier (EU AI Act only) |
| `POST` | `/v1/evidence/events` | evidence-vault | Append ledger event |
| `GET` | `/v1/evidence/verify-chain` | evidence-vault | Verify ledger chain integrity |
| `GET` | `/v1/evidence/ledger-root` | evidence-vault | Current Merkle tip |
| `GET` | `/v1/evidence/ledger-history-tips` | evidence-vault | Merkle tip after every event |
| `POST` | `/v1/sync/metadata` | egress-proxy | Sync metadata to dashboard |
| `GET` | `/v1/status` | gateway-api | Aggregate downstream status |
| `GET` | `/v1/portfolio` | evidence-vault | Systems on record with latest badge |
| `POST` | `/v1/pro/badges/issue` | evidence-vault | Issue compliance badge |
| `GET` | `/v1/pro/badges/verify/{badgeId}` | evidence-vault | Badge metadata |
| `GET` | `/v1/pro/badges/{badgeId}/svg` | evidence-vault | Badge SVG markup, wrapped in JSON |
| `POST` | `/v1/pro/ingest/status-artifact` | egress-proxy | Record status artifact |
| `POST` | `/v1/pro/ingest/dossier-metadata` | egress-proxy | Record dossier metadata |
| `POST` | `/v1/pro/ingest/metrics` | egress-proxy | Record compliance metrics |
