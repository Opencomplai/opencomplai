# Gateway API — REST Reference

The Opencomplai gateway API is the HTTP entry point for the Docker Compose stack. All endpoints are prefixed `/v1/` except `GET /health`.

**Base URL (default):** `http://localhost:8080`
**Content-Type:** `application/json` for all request and response bodies.

---

## Error envelope

All error responses use the same envelope:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "system_id is required",
  "category": "client",
  "retryable": false,
  "correlation_id": "req-uuid"
}
```

| Field | Type | Description |
|---|---|---|
| `error_code` | `string` | Machine-readable error identifier (see table below). |
| `message` | `string` | Human-readable description. |
| `category` | `string` | `client` (fix the request) or `server` (retry may help). |
| `retryable` | `bool` | `true` if the same request may succeed on retry. |
| `correlation_id` | `string` | Request ID; include in support reports. |

**Common error codes:**

| Code | HTTP status | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Request body failed schema validation. |
| `NOT_FOUND` | 404 | Resource does not exist. |
| `SERVICE_UNAVAILABLE` | 503 | A downstream service (risk-engine, evidence-vault, etc.) is not reachable. |
| `POLICY_BLOCK` | 403 | Egress proxy blocked the operation. |

---

## `GET /health`

Health check for the gateway API process.

**Request:** No body.

**Response `200`:**

```json
{
  "status": "ok",
  "service": "gateway-api",
  "version": "0.1.0-dev"
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
  "compliance_target": "EU_AI_ACT",
  "high_risk_presumption": false,
  "commit_ref": "abc1234"
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `system_id` | `string` | | — | Unique system identifier. |
| `intended_purpose` | `string` | | — | Primary intended purpose. |
| `compliance_target` | `string` | | `EU_AI_ACT` | Compliance framework. |
| `high_risk_presumption` | `bool` | | `false` | Provider presumes high risk. |
| `commit_ref` | `string` | | `HEAD` | Git commit reference. |

**Response `200`:** validated manifest object (same shape as request).

**Response `422`:** `VALIDATION_ERROR` — one or more required fields missing or wrong type.

---

## `POST /v1/risk/classify`

Classify the risk level of an AI system under EU AI Act Annex III.

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
  "evidence_event_id": "b7f3a1e2-..."
}
```

| Field | Type | Description |
|---|---|---|
| `risk_class` | `string` | `unacceptable`, `high`, `limited`, or `minimal`. |
| `trap_detected` | `bool` | `true` if the substantial-modification trap rule triggered. |
| `profiling_detected` | `bool` | `true` if an Art. 6 profiling signal was detected. |
| `rationale_hash` | `string` | SHA-256 of the assessment rationale. |
| `evidence_event_id` | `string` | UUID of the appended ledger event (if evidence-vault is reachable). |

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

## `POST /v1/docs/generate`

Generate an EU AI Act Annex IV technical documentation dossier (REQ-DOC-001).

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
| `system_id` | `string` | | — | System identifier. |
| `commit_ref` | `string` | | `HEAD` | Git commit reference. |
| `intended_purpose` | `string` | | `Not specified` | Primary intended purpose. |
| `provider_name` | `string` | | `Unknown Provider` | Legal name of the provider. |

**Response `200`:**

```json
{
  "dossier_id": "d4f9c2a1-...",
  "bundle_checksum": "sha256:3e2f1a...",
  "schema_valid": true,
  "duration_ms": 142
}
```

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
| `event_type` | `string` | | Event type identifier (e.g. `compliance_check_started`). |
| `payload` | `object` | | Event-specific payload object. |
| `signer_id` | `string \| null` | | Identity of the human signer for HITL events. |

**Response `200`:**

```json
{
  "event_id": "e1a2b3c4-...",
  "ts": "2026-05-25T10:00:00Z",
  "prev_hash": "sha256:000000..."
}
```

---

## `POST /v1/sync/metadata`

Sync allowlisted metadata to the Premium Dashboard via the egress proxy.

**Request body:**

```json
{
  "system_id": "loan-decision-model"
}
```

**Response `200`:**

```json
{
  "synced": true,
  "system_id": "loan-decision-model",
  "fields_synced": ["install_id", "system_id", "commit_ref", "result", "duration_ms"]
}
```

**Response `403`:** `POLICY_BLOCK` — egress proxy blocked the request. Check `EGRESS_ALLOWED_DESTINATIONS` in `.env`.

---

## Endpoint summary

| Method | Path | Service | Description |
|---|---|---|---|
| `GET` | `/health` | gateway-api | Health check |
| `POST` | `/v1/manifests/validate` | risk-engine | Validate system manifest |
| `POST` | `/v1/risk/classify` | risk-engine | Classify risk level |
| `POST` | `/v1/verify/claims` | risk-engine | Submit verification task |
| `POST` | `/v1/docs/generate` | doc-generator | Generate Annex IV dossier |
| `POST` | `/v1/evidence/events` | evidence-vault | Append ledger event |
| `POST` | `/v1/sync/metadata` | egress-proxy | Sync metadata to dashboard |
