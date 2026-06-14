# Getting Started

Welcome to Opencomplai — an open-source EU AI Act compliance toolkit for AI engineering teams.

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
