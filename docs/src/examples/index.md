# Examples

Working code examples for Opencomplai CLI and Python SDK.

## [Basic Usage](basic-usage.md)

Common workflows:

- CLI: check a minimal-risk system
- CLI: check a high-risk system
- CLI: JSON output for scripting
- Python SDK: programmatic assessment
- Python SDK: high-risk with `answers`
- GitHub Actions compliance gate
- Docker Compose service-backed check

## [Advanced Patterns](advanced-patterns.md)

Production-ready patterns:

- Batch assessment across multiple systems
- Programmatic CI gate (Python)
- Using `answers` for rule customisation
- Working with `ScanStatusArtifact` in CI
- Service-backed mode with custom gateway URL
- Air-gap check

## [Integrations](integrations.md)

Integrate with CI/CD and tooling:

- GitHub Actions compliance gate
- GitLab CI compliance gate
- Pre-commit hook
- Python unit tests with `assess`
- Docker Compose + CLI one-command check
- Makefile integration

---

## Quick example

```python
from opencomplai import assess, AssessmentInput, ModelMetadata

result = assess(AssessmentInput(
    model=ModelMetadata(
        name="my-model",
        version="1.0.0",
        modality="text",
        use_case="customer support chatbot",
        deployment_context="production",
    )
))

print(result.risk_level)       # "minimal"
print(result.rules_passed)     # 4
```
