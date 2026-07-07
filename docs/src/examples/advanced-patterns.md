# Advanced Patterns

## Batch assessment across multiple systems

```python
from opencomplai import assess, AssessmentInput, ModelMetadata
from dataclasses import dataclass

@dataclass
class SystemSpec:
    system_id: str
    use_case: str
    version: str = "1.0.0"
    answers: dict | None = None

SYSTEMS = [
    SystemSpec("chatbot-v1", "customer support chatbot"),
    SystemSpec("loan-model-v2", "automated credit scoring for retail lending"),
    SystemSpec("hr-screener-v1", "recruitment and hiring screening candidates"),
    SystemSpec("fraud-detect-v3", "payment fraud detection"),
]

results = []
for spec in SYSTEMS:
    result = assess(AssessmentInput(
        model=ModelMetadata(
            name=spec.system_id,
            version=spec.version,
            modality="text",
            use_case=spec.use_case,
            deployment_context="production",
        ),
        answers=spec.answers or {},
    ))
    results.append((spec.system_id, result))
    print(f"{spec.system_id:30} {result.risk_level:15} "
          f"({result.rules_passed}/{result.rules_evaluated} passed)")
```

## Programmatic CI gate

```python
import sys
from opencomplai import assess, AssessmentInput, ModelMetadata

def compliance_gate(system_id: str, use_case: str) -> int:
    """Return exit code suitable for CI: 0 = pass, 1 = fail."""
    result = assess(AssessmentInput(
        model=ModelMetadata(
            name=system_id,
            version="HEAD",
            modality="text",
            use_case=use_case,
            deployment_context="production",
        )
    ))

    if result.rules_failed > 0:
        print("COMPLIANCE FAIL — the following rules failed:")
        for r in result.rule_results:
            if not r.passed:
                print(f"  [{r.rule_id}] {r.rule_name}")
                print(f"     {r.rationale}")
                print(f"     Reference: {r.reference}")
        return 1

    print(f"COMPLIANCE PASS — {result.risk_level} risk, "
          f"{result.rules_passed}/{result.rules_evaluated} rules passed.")
    return 0


if __name__ == "__main__":
    import os
    sys.exit(compliance_gate(
        system_id=os.environ["MODEL_NAME"],
        use_case=os.environ["USE_CASE"],
    ))
```

## Using `answers` for rule customisation

Some rules check `AssessmentInput.answers` for explicit signal declarations:

| Answer key | Type | Effect |
|---|---|---|
| `profiling_detected` | `bool` | Set `True` forces `EU_AIA_ART6_PROFILING` to fail |
| `substantial_modification` | `bool` | Set `True` triggers `EU_AIA_ART25_MODIFICATION_TRAP` |
| `chatbot_disclosure` | `bool` | Set `True` satisfies `EU_AIA_ART52_TRANSPARENCY` (if implemented) |

```python
from opencomplai import assess, AssessmentInput, ModelMetadata

# Declare that this model has undergone a substantial modification
# compliance check will surface the re-assessment obligation
result = assess(AssessmentInput(
    model=ModelMetadata(
        name="my-model",
        version="2.0.0",
        modality="text",
        use_case="automated employee performance evaluation",
        deployment_context="production",
    ),
    answers={"substantial_modification": True},
))
```

## Working with `ScanStatusArtifact` in CI

```python
import json
from pathlib import Path
from opencomplai_core.models import ScanStatusArtifact, ScanResult

artifact = ScanStatusArtifact.model_validate(
    json.loads(Path("compliance-artifact.json").read_text())
)

match artifact.result:
    case ScanResult.PASS:
        print("Compliance check passed.")
    case ScanResult.CONTROL_FAIL:
        print(f"Failed controls: {artifact.failed_controls}")
    case ScanResult.VALIDATION_FAIL:
        print("Manifest validation failed.")
    case ScanResult.TRAP_DETECTED:
        print("Substantial modification trap — re-assessment required.")
    case _:
        print(f" Result: {artifact.result}")
```

## Service-backed mode with custom gateway URL

=== "macOS / Linux"
    ```bash
    # Against local Docker Compose stack
    OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check

    # Against a remote deployment
    OPENCOMPLAI_API_URL=https://compliance.internal.example.com \
      opencomplai check --sign --scan-mode ci
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Against local Docker Compose stack
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"
    opencomplai check

    # Against a remote deployment
    $env:OPENCOMPLAI_API_URL = "https://compliance.internal.example.com"
    opencomplai check --sign --scan-mode ci
    ```

## Airgap check

=== "macOS / Linux"
    ```bash
    opencomplai check --scan-mode airgap
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check --scan-mode airgap
    ```

In airgap mode, `opencomplai check` uses the local engine even when `OPENCOMPLAI_API_URL` is set, and `egress-proxy` in the Docker stack blocks all outbound traffic.
