# Basic Usage Examples

Common patterns for using Opencomplai in the CLI, Python SDK, and CI.

## CLI: check a minimal-risk system

```bash
# 1. Install
pip install opencomplai

# 2. Create manifest
opencomplai init \
  --system-id "support-bot-v1" \
  --intended-purpose "customer support chatbot"

# 3. Run compliance check
opencomplai check
```

Expected output:

```text
Opencomplai Assessment Report
Model:      support-bot-v1 vHEAD
Risk level: MINIMAL
Rules:      4 passed, 0 failed of 4 total
Generated:  2026-05-25T10:00:00+00:00
...
Risk classification: MINIMAL. 4 rules passed, 0 rules failed.
```

## CLI: check a high-risk system

```bash
opencomplai init \
  --system-id "loan-decision-v2" \
  --intended-purpose "automated credit scoring for retail lending"

opencomplai check
```

The `AnnexIIIClassifierRule` will detect "credit scoring" as an Annex III category and fail:

```text
Risk level: HIGH
Rules:      3 passed, 1 failed of 4 total

EU_AIA_ART6_HIGH_RISK — FAIL
   Use case 'automated credit scoring for retail lending' matches Annex III
   categories: essential_services.
   Reference: EU AI Act, Article 6, Annex III
```

Exit code: `1` (`CONTROL_FAIL`).

## CLI: JSON output for scripting

```bash
opencomplai check --output json | jq '.result'
# "control_fail"

opencomplai check --output json | jq '.failed_controls'
# ["EU_AIA_ART6_HIGH_RISK"]
```

## CLI: validate a manifest before check

```bash
opencomplai validate-manifest system-manifest.json
# Manifest is valid.

opencomplai validate-manifest system-manifest.json --output json | jq .
```

## Python SDK: programmatic assessment

```python
from opencomplai import assess, AssessmentInput, ModelMetadata

def check_model(name: str, version: str, use_case: str) -> bool:
    """Return True if model passes all compliance rules."""
    result = assess(AssessmentInput(
        model=ModelMetadata(
            name=name,
            version=version,
            modality="text",
            use_case=use_case,
            deployment_context="production",
        )
    ))

    print(f"Risk level: {result.risk_level}")
    print(f"Rules: {result.rules_passed} passed, {result.rules_failed} failed")

    for rule in result.rule_results:
        status = "" if rule.passed else ""
        print(f"  {status} {rule.rule_id}: {rule.rationale[:80]}")

    return result.rules_failed == 0


# Check a minimal-risk system
ok = check_model("chatbot-v1", "2.0.0", "customer support chatbot")
print("Compliance:", "PASS" if ok else "FAIL")
```

## Python SDK: high-risk with `answers` override

```python
from opencomplai import assess, AssessmentInput, ModelMetadata

# The "credit scoring" use case triggers high-risk.
# If we also flag profiling, two rules will fail.
result = assess(AssessmentInput(
    model=ModelMetadata(
        name="risk-score-model",
        version="1.0.0",
        modality="text",
        use_case="automated credit scoring for retail lending",
        deployment_context="production",
    ),
    answers={
        "profiling_detected": True,  # triggers EU_AIA_ART6_PROFILING
    }
))

for r in result.rule_results:
    if not r.passed:
        print(f"FAIL: {r.rule_id}")
        print(f"      {r.rationale}")
        print(f"      Reference: {r.reference}")
```

## GitHub Actions: compliance gate

```yaml
name: Compliance check
on: [push, pull_request]

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Opencomplai
        run: pip install opencomplai

      - name: Run compliance check
        env:
          MODEL_NAME: my-model
          USE_CASE: "customer support chatbot"
        run: |
          opencomplai init \
            --system-id "$MODEL_NAME" \
            --intended-purpose "$USE_CASE"
          opencomplai check
```

The step fails automatically if the exit code is non-zero.

## Docker Compose: service-backed check

After starting the full stack:

```bash
docker compose -f infra/compose/docker-compose.yml up -d
```

Run the CLI in service-backed mode:

```bash
OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check
```

The gateway API routes the check through all services and writes an evidence ledger entry.
