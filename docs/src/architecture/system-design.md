# System Design

## Local scan flow

When `OPENCOMPLAI_API_URL` is not set, the entire scan runs in-process:

```text
opencomplai check
    │
    1. Read + validate system-manifest.json SystemManifest
    2. Build AssessmentInput from manifest fields
    3. assess(input) run RULE_REGISTRY against input RiskResult
    4. Build ScanStatusArtifact from RiskResult
    5. Sign artifact (if --sign and signing key exists)
    6. Write compliance-artifact.json
    7. Print human/JSON output
    8. sys.exit(exit_code)
```

No database, no Docker, no network.

## Service-backed scan flow (10 steps)

When `OPENCOMPLAI_API_URL=http://localhost:8080` is set, the CLI orchestrates services:

```text
Step  1 — emit compliance_check_started event POST /v1/evidence/events
Step  2 — validate manifest               POST /v1/manifests/validate
Step  3 — risk classify                   POST /v1/risk/classify
Step  4 — trap-gate check (substantial modification / profiling)
Step  5 — run controls                    POST /v1/verify/claims
Step  6 — poll for verification results   GET  /v1/verify/claims/{id}
Step  7 — generate Annex IV dossier       POST /v1/docs/generate
Step  8 — finalise + sign ScanStatusArtifact
Step  9 — emit compliance_check_completed POST /v1/evidence/events
Step 10 — write compliance-artifact.json, exit
```

## Network topology (Docker Compose)

```text
Host
  │  :8080
  │
  ▼
gateway-api (frontend + internal networks)
  │
  ├── /v1/risk/*      risk-engine    :8001 (internal)
  ├── /v1/verify/*    evidence-vault :8002 (internal)
  ├── /v1/docs/*      doc-generator  :8003 (internal)
  └── /v1/evidence/*  evidence-vault :8002 (internal)
                              │
                        egress-proxy   :8004 (internal + external)
                        (only service with outbound internet access)

postgres :5432  (internal — evidence-vault + risk-engine)
redis    :6379  (internal — risk-engine verification task queue)
```

- **`internal` network**: fully isolated, no host internet access.
- **`external` network**: only `egress-proxy` is attached. All outbound traffic must pass through it.
- **`frontend` network**: only `gateway-api` is exposed to the host.

## Security properties

| Property | Implementation |
|---|---|
| Egress allowlisting | `EGRESS_ALLOWED_DESTINATIONS` in `.env`; empty = fully air-gapped |
| Signed artifacts | Ed25519 keypair in `~/.opencomplai/`; `--sign` flag on `check` |
| Immutable evidence | Content-addressed storage (SHA-256 keyed) in evidence-vault |
| Tamper detection | Merkle-linked `LedgerEvent` chain; verifiable with `tools/verify-ledger/` |
| Read-only containers | All service containers run `read_only: true` with `tmpfs: /tmp` |
| Non-root | All containers run as UID 1001 |

## CI/CD integration

```yaml
# GitHub Actions example
- name: Opencomplai compliance check
  run: |
    pip install opencomplai
    opencomplai init \
      --system-id "${{ env.MODEL_NAME }}" \
      --intended-purpose "${{ env.USE_CASE }}"
    opencomplai check
```

- Exit `0` = pass (merge proceeds).
- Exit `1` = control failure (merge blocked).
- Exit `2` = validation failure (manifest missing or invalid).

See [Exit codes](../cli/exit-codes.md) for the complete table.

## Observability

In the Docker Compose stack:

- **Prometheus** scrapes `/metrics` from all services.
- **Grafana** provides operator dashboards (default port 3001).
- **OpenTelemetry** traces can be exported by setting `OTEL_EXPORTER_OTLP_ENDPOINT`.
