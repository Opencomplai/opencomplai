# Debugging

## CLI debugging techniques

### Verbose service calls

The CLI does not expose a `--verbose` flag, but you can inspect the gateway API directly with `curl`:

```bash
# Check gateway health
curl http://localhost:8080/health

# Manually call risk classify
curl -s -X POST http://localhost:8080/v1/risk/classify \
  -H "Content-Type: application/json" \
  -d '{"system_id": "my-model", "intended_purpose": "customer support chatbot"}' \
  | jq .
```

### Inspect the compliance artifact

After every `check` run, `compliance-artifact.json` is written to the current directory. Read it to understand what the CLI produced:

```bash
cat compliance-artifact.json | jq .
```

Key fields to inspect:

| Field | What to look for |
|---|---|
| `result` | The terminal state (`pass`, `control_fail`, etc.) |
| `failed_controls` | IDs of failing controls — look these up in `rules.py` |
| `evidence_hashes` | Empty in local mode; populated in service-backed mode |
| `pending_verifications_count` | > 0 means the service stack has pending ground-truth tasks |
| `signature` | `null` in unsigned OSS mode; base64 string if `--sign` was passed |

### Run the rule engine directly (SDK)

```python
from opencomplai import assess, AssessmentInput, ModelMetadata

result = assess(AssessmentInput(
    model=ModelMetadata(
        name="my-model",
        version="1.0",
        modality="text",
        use_case="customer support chatbot",
        deployment_context="production",
    ),
    answers={"chatbot_disclosure": True},
))

for rule in result.rule_results:
    status = "" if rule.passed else ""
    print(f"{status} [{rule.rule_id}] {rule.rationale}")
```

This runs entirely in-process without any network calls or Docker stack.

---

## Docker Compose debugging

### Check service status

```bash
docker compose -f infra/compose/docker-compose.yml ps
```

All services should be `running`. If any show `exited`, check their logs.

### Tail logs for a specific service

```bash
# Gateway API
docker compose -f infra/compose/docker-compose.yml logs -f gateway-api

# Risk engine
docker compose -f infra/compose/docker-compose.yml logs -f risk-engine

# Evidence vault
docker compose -f infra/compose/docker-compose.yml logs -f evidence-vault
```

### Common log patterns

| Log message | Meaning |
|---|---|
| `database is uninitialized` (postgres) | `POSTGRES_PASSWORD` not set in `.env` |
| `connection refused` (any service) | PostgreSQL not ready yet — wait 5 s and retry, or check postgres logs |
| `EGRESS_BLOCKED` (egress-proxy) | Outbound request was blocked; expected in air-gap mode |
| `SignatureVerificationError` | Artifact signature does not match the registered signing key |

### Verify the evidence ledger

```bash
python3 tools/verify-ledger/verify_ledger.py \
  --gateway-url http://localhost:8080
```

Expected output:

```text
[INFO]  Checking ledger integrity at: http://localhost:8080/v1/evidence/verify-chain
[PASS]  Evidence ledger chain is valid — no tampering detected
```

---

## Python environment debugging

### Verify installed packages

```bash
uv pip list | grep opencomplai
```

Expected output:

```
opencomplai          0.1.0-dev
opencomplai-cli      0.1.0-dev
opencomplai-core     0.1.0-dev
```

### Check the rule registry

```python
from opencomplai_core.rules import RULE_REGISTRY

for rule in RULE_REGISTRY:
    print(f"{rule.rule_id}: {rule.rule_name}")
```

### Reset local state

```bash
# Remove signing keypair and config (forces fresh init)
rm -rf ~/.opencomplai/

# Remove local compliance artifacts
rm -f compliance-artifact.json system-manifest.json
```

---

## CI debugging

### GitHub Actions — check exit code

Add `--output json` to capture the full artifact:

```yaml
- name: Compliance check
  run: |
    OPENCOMPLAI_API_URL=${{ vars.OPENCOMPLAI_API_URL }} \
    opencomplai check --scan-mode ci --output json | tee compliance-artifact.json
  continue-on-error: false
```

### Upload compliance artifact

```yaml
- name: Upload compliance artifact
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: compliance-artifact
    path: compliance-artifact.json
```

### Inspect exit code meaning

```bash
opencomplai check; echo "Exit code: $?"
# 0 = pass, 1 = control_fail, 2 = validation_fail, 3 = policy_block, 4 = trap_detected
```

See [Exit codes](../cli/exit-codes.md) for the full table.
