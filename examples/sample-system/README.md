# Sample AI System — OpenComplAI Example

This directory shows how to integrate an AI system with OpenComplAI for EU AI Act compliance.

## Files

| File | Purpose |
|------|---------|
| `manifest.yaml` | System metadata, control list, and bias monitoring config |
| `run-compliance-check.sh` | Shell script that ingests a status artifact, issues a badge, and verifies it |

## Quick start

```bash
# 1. Start the OpenComplAI stack (from repo root)
docker compose up -d

# 2. Run the compliance check
cd examples/sample-system
./run-compliance-check.sh
```

Expected output:

```
[INFO]  Step 1/4 — Gateway health check
[PASS]  Gateway reachable
[INFO]  Step 2/4 — Ingest compliance status artifact
[PASS]  Status artifact ingested — event_id=...
[INFO]  Step 3/4 — Issue compliance badge
[PASS]  Compliance badge issued — badge_id=sha256:...
[INFO]  Step 4/4 — Verify badge
[PASS]  Badge verified valid
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[PASS]  EU AI Act compliance check PASSED
  System:    sample-credit-scoring-v1
  Badge ID:  sha256:...
  SVG badge: http://localhost:3000/v1/pro/badges/sha256:.../svg
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## CI integration

See `.github/workflows/compliance-gate.yml.example` in the repo root for a ready-to-use GitHub Actions workflow.

## Customising `manifest.yaml`

- Set `system.id` to a stable identifier for your system (used to derive `badge_id`).
- Set `system.risk_class` to `"high"`, `"limited"`, or `"minimal"` per EU AI Act Article 6.
- Add or remove `controls` entries to match your technical documentation.
- Set `gateway_url` or export `OPENCOMPLAI_GATEWAY_URL` to point at your deployment.
