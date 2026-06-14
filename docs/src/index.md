# Open-source AI compliance for a trustworthy future.

Opencomplai is an open-source compliance toolkit that helps AI engineering teams assess EU AI Act risk, generate auditable evidence, and gate releases in CI/CD using machine-readable results.

## The problem

The EU AI Act introduces real friction for AI engineering teams. High-Risk classification can be ambiguous at build time, especially when intended purpose and deployment context change. Evidence collection often becomes a manual, spreadsheet-driven process that does not scale with fast iteration. Compliance checks also tend to arrive late and block CI/CD at the worst possible moment.

## Three components

- **opencomplai-core** — the rule engine that evaluates compliance controls and produces structured results.
- **opencomplai CLI** — the developer interface for creating manifests and running checks locally and in CI.
- **opencomplai Python SDK** — the programmatic interface for embedding checks into internal tooling.
- **Docker Compose reference deployment** — the full platform skeleton for services and workflows.

## Why open source?

- **Trust**: deterministic rules and transparent outputs reduce compliance uncertainty.
- **Auditability**: reviewers can inspect rule logic and evidence traces end-to-end.
- **Community**: shared patterns and rules lower the cost of compliance for everyone.

## Who is this for?

AI engineers, ML platform teams, and CTOs at AI startups that need repeatable compliance checks without slowing delivery.

## Supported compliance frameworks

EU AI Act (v0.1). NIST AI RMF and ISO/IEC standards are on the roadmap.

## Get started

[Quick Start](getting-started/quick-start.md) — run your first compliance check in under 15 minutes.
