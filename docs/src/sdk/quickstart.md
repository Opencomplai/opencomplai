# Python SDK Quickstart

Run assessments programmatically using the Opencomplai Python SDK.

## Install

```bash
pip install opencomplai
```

!!! note "Pre-release"
    See [Installation](../getting-started/installation.md) for source-install fallback.

## Minimal example

```python
from opencomplai import assess, AssessmentInput, ModelMetadata

assessment = AssessmentInput(
    model=ModelMetadata(
        name="my-model",
        version="1.0.0",
        modality="text",
        use_case="customer support chatbot",
        deployment_context="production",
    )
)

result = assess(assessment)

print(result.risk_level)          # "minimal"
print(result.evidence_summary)    # "Risk classification: MINIMAL. ..."
for rule in result.rule_results:
    print(rule.rule_id, rule.passed, rule.rationale)
```

## Full output example

```python
from opencomplai import assess, AssessmentInput, ModelMetadata

result = assess(AssessmentInput(
    model=ModelMetadata(
        name="loan-decision-model",
        version="2.3.1",
        modality="text",
        use_case="automated credit scoring for retail lending",
        deployment_context="production",
    )
))

print(f"Risk level: {result.risk_level}")
print(f"Rules evaluated: {result.rules_evaluated}")
print(f"Rules passed: {result.rules_passed}")
print(f"Rules failed: {result.rules_failed}")
print(f"Evidence: {result.evidence_summary}")
print()
for r in result.rule_results:
    status = "" if r.passed else ""
    print(f"{status} [{r.rule_id}] {r.rule_name}")
    print(f"   Rationale: {r.rationale}")
    print(f"   Reference: {r.reference}")
```

## API Reference

See [SDK API Reference](api-reference.md) for full type signatures and model documentation.
