# OpenComplAI: Compliance-as-Code for AI Pipelines

**Stop manual audits → Start shipping.**

OpenComplAI brings AI compliance directly into your CI/CD pipeline, turning fragmented legal mandates into automated, machine-readable "Pre-Ship Checks." The EU AI Act is evaluated natively; NIST AI RMF 1.0 is derived from the same evidence.

## Why OpenComplAI?

Traditional GRC tools are disconnected dashboards that create "velocity tax." We shift compliance left:

- **Prevent Non-Compliance:** Gate releases by blocking builds that violate safety rules.
- **Automated Evidence:** `opencomplai check` writes `compliance-artifact.json` with evidence hashes for every run; it is signed only when you pass `--sign` and a local signing key exists.
- **Frameworks Side by Side:** Assess one system against the EU AI Act and NIST AI RMF 1.0 side by side (`compliance_targets` in the manifest, or `opencomplai gaps --target EU_AI_ACT --target NIST_AI_RMF`). The EU AI Act is evaluated natively; NIST AI RMF is re-projected per subcategory from that same EU AI Act evidence through a built-in crosswalk, with no scanner of its own (see [NIST AI RMF](concepts/nist-ai-rmf.md)). ISO/IEC 42001 is a native pack of attestation rows that read Unverified until you record an attestation under `framework_inputs` (`--target ISO_IEC_42001`). DORA and EBA are mapped only: `gaps --map-to DORA|EBA` adds a low-confidence citation per EU AI Act article (see [Mapped regimes](concepts/mapped-regimes.md)). Standing line: EU AI Act evaluated; NIST AI RMF derived (partial, unreviewed); ISO 42001 native pack, attestation-led (partial, unreviewed); DORA and EBA mapped only. See [Frameworks](frameworks/index.md).

## How It Works (The 3-Minute Setup)

1. **Define:** Create a compliance manifest for your model.
2. **Integrate:** Add the OpenComplAI action to your GitHub/GitLab pipeline.
3. **Ship:** Get an automated "Pass/Fail" result before your code ever hits production.

[**Check out our Dummy Repo (Sandbox)**](https://github.com/Opencomplai/opencomplai/tree/main/examples/gate-demo) – *Five fictional systems, one per gate outcome (exit codes 3, 4, 1, 1, 0). Illustrative sandbox, not legal advice. It does not scan code.*

## Core Components

- **[opencomplai-core](https://pypi.org/project/opencomplai-core/)** — the rule engine that evaluates compliance controls and produces structured results.
- **[opencomplai-cli](https://pypi.org/project/opencomplai-cli/)** — the developer interface for creating manifests and running checks locally and in CI.
- **[opencomplai](https://pypi.org/project/opencomplai/)** (Python SDK meta-package) — the programmatic interface for embedding checks into internal tooling.

## Quick Start

Get your first compliance check running in **under 15 minutes**:

[Quick Start](getting-started/quick-start.md) — install the CLI, initialise a manifest, and run your first compliance check.

## Community & Feedback

!!! tip "Join the developer community"
    **[Join our Developer Discord](https://discord.gg/egjX5JgQJ)** — the fastest place to get help with EU AI Act workflows, CI/CD integration, and feedback.

The CLI and engine are open source; the hosted dashboard is in private beta. If you are an AI engineer or ML platform lead, we want your feedback.

See **[Support & Community](community/support.md)** for Discord, GitHub issue templates, security reporting, and all contact options.
