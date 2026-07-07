# opencomplai

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![PyPI](https://img.shields.io/pypi/v/opencomplai.svg)](https://pypi.org/project/opencomplai/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

The convenience meta-package for [Opencomplai](https://opencomplai.com) — EU AI Act
compliance for your AI systems. Installing `opencomplai` gives you both the risk engine
and the command-line tool in one step.

## Install

```bash
pip install opencomplai
```

This installs:

- [`opencomplai-core`](https://pypi.org/project/opencomplai-core/) — the deterministic,
  rule-based EU AI Act risk engine and code-corroboration scanner.
- [`opencomplai-cli`](https://pypi.org/project/opencomplai-cli/) — the `opencomplai`
  command-line tool.

## Quick start

### Command line

```bash
opencomplai init      # scaffold a system-manifest.json
opencomplai scan      # corroborate manifest against code
opencomplai check     # run the compliance gate
```

### Python SDK

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
print(result.risk_level)
```

Public API re-exported from `opencomplai`: `assess`, `AssessmentInput`, `ModelMetadata`,
`RiskResult`, `ScanStatusArtifact`, and `SystemManifest`.

## Optional: AI intent plugin

For AI-powered intent classification of code callsites, also install
[`opencomplai-ai`](https://pypi.org/project/opencomplai-ai/):

```bash
pip install opencomplai-ai
opencomplai scan --ai-intent
```

## Documentation

Full guides, SDK reference, and the EU AI Act concepts at
**[docs.opencomplai.com](https://docs.opencomplai.com)**.

## License

AGPL-3.0-only. See [LICENSE](https://www.gnu.org/licenses/agpl-3.0).
