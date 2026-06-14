# verify-output

Verify an AI output claim against ground-truth sources (REQ-GTVG-001).

## Synopsis

```bash
opencomplai verify-output --system-id <id> [OPTIONS]
```

## Options

| Option | Default | Description |
|---|---|---|
| `--system-id` | *(required)* | System identifier from the manifest. |
| `--claim-ref` | `manual` | Reference string identifying the claim to verify. |
| `--source-ref` | `offline://manual` | Source reference URI for the ground-truth data. |
| `--expected-value` | *(unset)* | Expected value string for assertion-style verification. |
| `--claim-file` | *(unset)* | Path to a file whose name becomes `claim_ref` and whose path becomes `source_ref`. |

## Requirements

`verify-output` requires the Docker Compose stack (`OPENCOMPLAI_API_URL` must be set). It calls `POST /v1/verify/claims` on the gateway API.

```bash
export OPENCOMPLAI_API_URL=http://localhost:8080
```

## Examples

```bash
# Verify a named claim
opencomplai verify-output \
  --system-id "loan-model" \
  --claim-ref "accuracy-claim-2026-05" \
  --source-ref "https://internal-benchmarks/accuracy" \
  --expected-value "0.94"

# Verify from a local file
opencomplai verify-output \
  --system-id "loan-model" \
  --claim-file ./claims/accuracy.json
```

## Output

Returns a JSON verification task record from the gateway API:

```json
{
  "task_id": "b7f3a1e2-...",
  "claim_ref": "accuracy-claim-2026-05",
  "source_ref": "https://internal-benchmarks/accuracy",
  "outcome": "pending"
}
```

`outcome` values:

| Value | Meaning |
|---|---|
| `pending` | Verification task queued; poll later or wait for `compliance_check_completed` event. |
| `verified` | Claim verified against ground truth; a `VerificationProof` is available. |
| `alerted` | Verification mismatch detected above the configured severity threshold. |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Task submitted successfully. |
| 2 | Validation error (invalid options). |
| 3 | Service unreachable or policy blocked (set `OPENCOMPLAI_API_URL` and start the stack). |
