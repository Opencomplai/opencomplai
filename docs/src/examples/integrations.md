# Integration Examples

## GitHub Actions compliance gate

Add Opencomplai to any CI pipeline with three steps:

```yaml
# .github/workflows/compliance.yml
name: EU AI Act compliance
on: [push, pull_request]

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Opencomplai
        run: pip install opencomplai

      - name: Initialise manifest
        run: |
          opencomplai init \
            --system-id "${{ vars.MODEL_NAME }}" \
            --intended-purpose "${{ vars.USE_CASE }}"

      - name: Run compliance check
        run: opencomplai check --scan-mode ci

      - name: Upload compliance artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: compliance-artifact
          path: compliance-artifact.json
```

The step fails automatically on exit code `1` (CONTROL_FAIL).

## GitLab CI compliance gate

```yaml
# .gitlab-ci.yml
compliance:
  stage: test
  image: python:3.11-slim
  script:
    - pip install opencomplai
    - opencomplai init
        --system-id "$MODEL_NAME"
        --intended-purpose "$USE_CASE"
    - opencomplai check --scan-mode ci
  artifacts:
    when: always
    paths:
      - compliance-artifact.json
```

## Pre-commit hook (block commits on compliance failure)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: opencomplai-check
        name: EU AI Act compliance check
        entry: opencomplai check
        language: system
        pass_filenames: false
        always_run: true
```

## Python project: call `assess` in unit tests

```python
# tests/test_compliance.py
import pytest
from opencomplai import assess, AssessmentInput, ModelMetadata
from opencomplai_core.models import RiskLevel


@pytest.fixture
def model_input():
    return AssessmentInput(
        model=ModelMetadata(
            name="my-model",
            version="1.0",
            modality="text",
            use_case="customer support chatbot",
            deployment_context="test",
        )
    )


def test_model_is_not_high_risk(model_input):
    result = assess(model_input)
    assert result.risk_level != RiskLevel.HIGH, (
        f"Model unexpectedly classified as HIGH risk. "
        f"Failed rules: {[r.rule_id for r in result.rule_results if not r.passed]}"
    )


def test_all_rules_pass(model_input):
    result = assess(model_input)
    failed = [r for r in result.rule_results if not r.passed]
    assert not failed, f"Failing rules: {[r.rule_id for r in failed]}"
```

## Docker Compose + CLI: one-command local check

```bash
# Start the full stack once
docker compose -f infra/compose/docker-compose.yml up -d

# Run checks against it repeatedly
OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check
```

The stack retains evidence in a PostgreSQL volume across runs.

## Makefile integration

```makefile
.PHONY: compliance

compliance: system-manifest.json
	opencomplai check

system-manifest.json:
	opencomplai init \
	  --system-id "$(MODEL_NAME)" \
	  --intended-purpose "$(USE_CASE)"
```
