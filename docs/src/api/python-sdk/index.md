# Python SDK

The Opencomplai Python SDK provides a programmatic interface to the EU AI Act compliance assessment engine.

## Installation

```bash
# Install from PyPI (once published)
pip install opencomplai

# Install from source (pre-release)
git clone https://github.com/Checkref-co/opencomplai
uv pip install -e packages/sdk-python
```

## Quick Start

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
print(result.evidence_summary) # "Risk classification: MINIMAL. ..."
```

## Sections

- [Installation](installation.md) — Install the Python SDK
- [API Reference](api-reference.md) — Complete API documentation

## Related

- [REST API](../rest-api.md) — HTTP gateway API reference
- [Code Examples](../../examples/index.md) — Working examples
