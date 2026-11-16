# opencomplai

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![PyPI](https://img.shields.io/pypi/v/opencomplai.svg)](https://pypi.org/project/opencomplai/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

The convenience meta-package for [Opencomplai](https://opencomplai.com) — AI compliance
for your AI systems: the EU AI Act, and a NIST AI RMF 1.0 view derived from the same
evidence. 15 frameworks by status, evaluated: EU AI Act, NIST AI RMF 1.0, ISO/IEC 42001:2023 AI management system, ISO/IEC 27090:2026 AI security guidance, ISO/IEC 27001:2022 information security management, SOC 2 Trust Services Criteria (not a SOC 2 report), NIS2 Directive (EU) 2022/2555 cybersecurity measures, DORA Regulation (EU) 2022/2554 digital operational resilience, EBA Guidelines on ICT, outsourcing and loan origination, EIOPA Opinion on AI governance and risk management, GDPR Regulation (EU) 2016/679, duties relevant to AI systems, Cyber Resilience Act Regulation (EU) 2024/2847, ETSI EN 304 223 baseline cyber security for AI, ISO/IEC 42005:2025 AI system impact assessment, ISO/IEC 23894:2023 AI risk management guidance. Installing `opencomplai` gives you both the risk engine and the command-line
tool in one step.

Not sure whether the EU AI Act applies to your AI system? [Try the free EU AI Act checker](https://opencomplai.com/resources/eu-ai-act-checker?utm_source=pypi&utm_medium=description&utm_campaign=checker-launch): rules-based, a few minutes, not legal advice.

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
`RiskLevel`, `RiskResult`, `RuleResult`, `ScanResult`, `ScanStatusArtifact`, `SystemManifest`,
and, for assessing several frameworks side by side, `evaluate_targets`, `resolve_targets`,
`FRAMEWORKS`, `FrameworkPack`, `FrameworkReport` and `GapReport`.

### Runtime events

`RuntimeReporter` records decisions, out-of-mandate actions, metrics and incidents of a
running system, keeps them in a local buffer file and sends them in batches. Only hashes
and metadata leave the machine: the tool input is hashed, never stored or sent.

```python
from opencomplai import RuntimeReporter

with RuntimeReporter("support-bot") as reporter:
    reporter.decision(
        "support-bot", "refund_order", "success", {"order_ref": "ord_7Hq2xK9mWb4vTz1L"}
    )
    reporter.metric("latency_ms", 182.5, unit="ms")
```

It sends with `OPENCOMPLAI_API_KEY` and `OPENCOMPLAI_DASHBOARD_URL`, the same pair
`opencomplai push` uses; without them it only buffers. Use one buffer file per system and
one process per file, and keep `.opencomplai/runtime-events.jsonl*` out of version control
(the same folder holds signed records you do commit). See the
[SDK reference](https://docs.opencomplai.com/sdk/api-reference/) for the buffer, the retries
and the event format.

## Optional: AI intent plugin

For optional intent analysis of code callsites (it includes a deterministic matcher that needs no download; local GGUF
models need the `[deep]` extra), also install
[`opencomplai-ai`](https://pypi.org/project/opencomplai-ai/):

```bash
pip install opencomplai-ai
opencomplai scan --ai-intent   # deterministic matcher (codebert-onnx), no download
```

`scan --ai-intent` and `scan --propose` both use the deterministic matcher unless you
pass `--ai-model` (and `scan --ai-intent` also honours a model saved with
`opencomplai ai configure`). A local GGUF LLM such as `qwen2.5-coder-1.5b` is opt-in and
needs `pip install 'opencomplai-ai[deep]'`.

## Documentation

Full guides, SDK reference, and the EU AI Act concepts at
**[docs.opencomplai.com](https://docs.opencomplai.com)**.

## License

AGPL-3.0-only. See [LICENSE](https://www.gnu.org/licenses/agpl-3.0).
