# opencomplai-core

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![PyPI](https://img.shields.io/pypi/v/opencomplai-core.svg)](https://pypi.org/project/opencomplai-core/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

The compliance engine at the heart of [Opencomplai](https://opencomplai.com).
`opencomplai-core` turns a declared `system-manifest.json` and your source tree into a
deterministic, rule-based EU AI Act risk classification and gap report — no LLM calls,
no network access, fully reproducible. The same evidence also yields a NIST AI RMF 1.0
view, re-projected per subcategory rather than measured separately. 15 frameworks by status, evaluated: EU AI Act, NIST AI RMF 1.0, ISO/IEC 42001:2023 AI management system, ISO/IEC 27090:2026 AI security guidance, ISO/IEC 27001:2022 information security management, SOC 2 Trust Services Criteria (not a SOC 2 report), NIS2 Directive (EU) 2022/2555 cybersecurity measures, DORA Regulation (EU) 2022/2554 digital operational resilience, EBA Guidelines on ICT, outsourcing and loan origination, EIOPA Opinion on AI governance and risk management, GDPR Regulation (EU) 2016/679, duties relevant to AI systems, Cyber Resilience Act Regulation (EU) 2024/2847, ETSI EN 304 223 baseline cyber security for AI, ISO/IEC 42005:2025 AI system impact assessment, ISO/IEC 23894:2023 AI risk management guidance.

It powers risk classification (`UnacceptableRiskRule`, `AnnexIIIClassifierRule`,
`ProfilingDetectionRule`, `SubstantialModificationRule`) and the code-corroboration scan
engine that cross-checks what a manifest *claims* against what the code actually does.

## Install

```bash
pip install opencomplai-core
```

For PDF report generation, install the optional extra:

```bash
pip install "opencomplai-core[reports]"
```

> Most users want the [`opencomplai`](https://pypi.org/project/opencomplai/) meta-package
> (engine + CLI) or the [`opencomplai-cli`](https://pypi.org/project/opencomplai-cli/)
> command-line tool. Install `opencomplai-core` directly when you are embedding the engine
> in your own application.

## Quick start

### Classify a model from a declared manifest

```python
from opencomplai import assess, AssessmentInput, ModelMetadata

result = assess(AssessmentInput(
    model=ModelMetadata(
        name="loan-scorer",
        version="1.0.0",
        modality="tabular",
        use_case="creditworthiness scoring for consumer loans",
        deployment_context="production",
    )
))

print(result.risk_level)        # e.g. RiskLevel.HIGH
for rule in result.rule_results:
    print(rule.rule_id, "PASS" if rule.passed else "FAIL")
```

### Corroborate a manifest against the code

```python
from pathlib import Path
from opencomplai_core.scan_engine import run_scan

report = run_scan(
    repo_root=Path("."),
    commit_ref="HEAD",
)

print(report.summary.result)            # PASS / CONTROL_FAIL / ...
for finding in report.findings:
    print(finding.finding_id, finding.mapped_taxonomy)
```

The scan engine extracts features from the repository, fuses evidence across detectors,
and maps findings to EU AI Act taxonomy (Annex III high-risk areas, Article 5 prohibited
practices, profiling under Article 6).

### Assess several frameworks side by side

```python
from opencomplai_core import FRAMEWORKS, SystemManifest, evaluate_targets

manifest = SystemManifest(
    system_id="loan-scorer",
    intended_purpose="creditworthiness scoring for consumer loans",
    compliance_targets=["EU_AI_ACT", "NIST_AI_RMF"],
)
reports = evaluate_targets(manifest, ["EU_AI_ACT", "NIST_AI_RMF"], commit_ref="HEAD")
for framework, report in reports.items():
    print(FRAMEWORKS[framework].label, len(report.report.articles), "requirements")
```

`FRAMEWORKS` lists what this release can assess. 15 frameworks by status, evaluated: EU AI Act, NIST AI RMF 1.0, ISO/IEC 42001:2023 AI management system, ISO/IEC 27090:2026 AI security guidance, ISO/IEC 27001:2022 information security management, SOC 2 Trust Services Criteria (not a SOC 2 report), NIS2 Directive (EU) 2022/2555 cybersecurity measures, DORA Regulation (EU) 2022/2554 digital operational resilience, EBA Guidelines on ICT, outsourcing and loan origination, EIOPA Opinion on AI governance and risk management, GDPR Regulation (EU) 2016/679, duties relevant to AI systems, Cyber Resilience Act Regulation (EU) 2024/2847, ETSI EN 304 223 baseline cyber security for AI, ISO/IEC 42005:2025 AI system impact assessment, ISO/IEC 23894:2023 AI risk management guidance. See
[Frameworks](https://docs.opencomplai.com/frameworks/).

## What you get

- **Deterministic risk classification** — same inputs always produce the same output, so
  results are auditable and CI-gateable.
- **Code corroboration** — detect when a manifest under-declares (claims minimal risk while
  the code does biometric identification, profiling, etc.).
- **Hash-chained evidence** — findings carry verifiable evidence items for audit trails.

## Documentation

Full docs, the EU AI Act concepts guide, and the SDK reference live at
**[docs.opencomplai.com](https://docs.opencomplai.com)**.

## License

AGPL-3.0-only. See [LICENSE](https://www.gnu.org/licenses/agpl-3.0).
