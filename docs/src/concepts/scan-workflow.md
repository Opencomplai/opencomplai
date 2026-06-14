# Scan workflow

What `opencomplai check` actually does, step by step.

## Local mode (no `OPENCOMPLAI_API_URL`)

When the gateway URL is not set, the check runs entirely locally:

```text
1. Read and validate system-manifest.json
2. Construct AssessmentInput from manifest fields
3. Run the rule engine (assess()) RiskResult
4. Build a ScanStatusArtifact from the RiskResult
5. Write compliance-artifact.json
6. Print human-readable output (or JSON if --output json)
7. Exit with the appropriate exit code
```

## Service-backed mode (with `OPENCOMPLAI_API_URL`)

When the gateway URL is set, the CLI orchestrates a full 10-step workflow via the gateway API:

```text
Step 1  — emit compliance_check_started event to evidence ledger
Step 2  — POST /v1/manifests/validate validate manifest
Step 3  — POST /v1/risk/classify run risk classification
Step 4  — trap-gate check (Phase 12)
Step 5  — POST /v1/verify/claims run control checks
Step 6  — GET  /v1/verify/claims/{id} poll for completion
Step 7  — POST /v1/docs/generate generate Annex IV dossier
Step 8  — finalize ScanStatusArtifact (sign if --sign)
Step 9  — POST /v1/evidence/events emit compliance_check_completed
Step 10 — write compliance-artifact.json, print output, exit
```

## Output: `ScanStatusArtifact`

Both modes produce a `ScanStatusArtifact` written to `compliance-artifact.json`:

```json
{
  "install_id": "a1b2c3d4-...",
  "system_id": "my-model",
  "commit_ref": "HEAD",
  "result": "pass",
  "failed_controls": [],
  "evidence_hashes": [],
  "rationale_hash": "sha256:...",
  "duration_ms": 42,
  "pending_verifications_count": 0,
  "signature": null
}
```

## Exit code mapping

| `ScanResult` | Exit code |
|---|---|
| `pass` | `0` |
| `control_fail` | `1` |
| `validation_fail` | `2` |
| `policy_block` | `3` |
| `trap_detected` | `4` |
| `degraded_complete` | `0` (scan completed despite degraded services) |

## Gateway API endpoints (service-backed mode)

| Endpoint | Purpose |
|---|---|
| `POST /v1/manifests/validate` | Validate system manifest |
| `POST /v1/risk/classify` | Run risk classification |
| `POST /v1/verify/claims` | Run control checks |
| `POST /v1/docs/generate` | Generate Annex IV dossier |
| `POST /v1/evidence/events` | Append event to ledger |
| `GET  /v1/sync/metadata` | Sync metadata with upstream |
| `GET  /health` | Health check |
