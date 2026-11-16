# Getting Started

Welcome to Opencomplai — an open-source AI compliance toolkit for AI engineering teams. It evaluates the EU AI Act natively and derives a NIST AI RMF 1.0 view from the same evidence (see [Frameworks](../frameworks/index.md)). 15 frameworks by status, evaluated: EU AI Act, NIST AI RMF 1.0, ISO/IEC 42001:2023 AI management system, ISO/IEC 27090:2026 AI security guidance, ISO/IEC 27001:2022 information security management, SOC 2 Trust Services Criteria (not a SOC 2 report), NIS2 Directive (EU) 2022/2555 cybersecurity measures, DORA Regulation (EU) 2022/2554 digital operational resilience, EBA Guidelines on ICT, outsourcing and loan origination, EIOPA Opinion on AI governance and risk management, GDPR Regulation (EU) 2016/679, duties relevant to AI systems, Cyber Resilience Act Regulation (EU) 2024/2847, ETSI EN 304 223 baseline cyber security for AI, ISO/IEC 42005:2025 AI system impact assessment, ISO/IEC 23894:2023 AI risk management guidance.

## What is Opencomplai?

Opencomplai helps you:

- **Classify risk** — determine whether your AI system is Unacceptable, High, Limited, or Minimal risk under the EU AI Act.
- **Generate evidence** — produce structured, auditable evidence bundles from project inputs and automated checks.
- **Gate CI/CD** — run compliance checks on every commit with predictable exit codes that block or pass your pipeline.

This is not a document processing or file upload platform. It is a compliance toolkit for AI system providers.

## Start here

1. **[Requirements](requirements.md)** — Python 3.11+ and (optionally) Docker.
2. **[Installation](installation.md)** — install the CLI and SDK.
3. **[Quick Start](quick-start.md)** — initialise a manifest and run your first compliance check in under 15 minutes.

## Core workflow

```text
opencomplai init    creates system-manifest.json
opencomplai check   reads manifest, evaluates rules, writes compliance-artifact.json
```

`compliance-artifact.json` is the machine-readable signed status artifact consumed by your CI gate.

## Next steps

- **CLI reference** — [init](../cli/init.md) · [check](../cli/check.md) · [validate-manifest](../cli/validate-manifest.md) · [exit codes](../cli/exit-codes.md)
- **SDK quickstart** — [Python SDK](../sdk/quickstart.md)
- **Full Docker deployment** — [Deployment Quickstart](../deployment/quickstart.md)
- **Understand the output** — [Core Concepts](../concepts/risk-levels.md)
- **Not sure if the EU AI Act applies to you?** — [EU AI Act Checker](eu-ai-act-checker.md) (runs in the browser, no account needed)
- **Verify your declared purpose matches your code** — [Detect AI in your code](scanner.md)
