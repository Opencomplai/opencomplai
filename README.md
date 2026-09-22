# OpenComplAI: Compliance-as-Code for AI Pipelines

**Stop manual audits → Start shipping.**

OpenComplAI brings EU AI Act compliance directly into your CI/CD pipeline, turning fragmented legal mandates into automated, machine-readable "Pre-Ship Checks."

[![CI (Python)](https://github.com/Opencomplai/opencomplai/actions/workflows/ci-python.yml/badge.svg?branch=main)](https://github.com/Opencomplai/opencomplai/actions/workflows/ci-python.yml) [![CI (Node)](https://github.com/Opencomplai/opencomplai/actions/workflows/ci-node.yml/badge.svg?branch=main)](https://github.com/Opencomplai/opencomplai/actions/workflows/ci-node.yml) [![PyPI](https://img.shields.io/pypi/v/opencomplai)](https://pypi.org/project/opencomplai/) [![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE) [![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/) [![Node.js 20+](https://img.shields.io/badge/node-20%2B-339933)](https://nodejs.org/)

### Demo

![OpenComplAI quickstart — opencomplai scan --quick in action](assets/opencomplai-quickstart.gif)

<video src="assets/opencomplai.mp4" controls width="100%">
  Your browser does not support the video tag.
</video>

[Watch the full narrated walkthrough (MP4)](assets/opencomplai.mp4) — the GIF above is the
30-second zero-setup scan; the MP4 is the deeper narrated tour.

## Why OpenComplAI?

Traditional GRC tools are disconnected dashboards that create "velocity tax." We shift compliance left:

- **Prevent Non-Compliance:** Gate releases by blocking builds that violate safety rules.
- **Automated Evidence:** Generate audit-ready logs automatically for every deployment.
- **Framework Crosswalk:** EU AI Act obligations are evaluated natively; NIST AI RMF 1.0 is evaluated too, by re-projecting that same EU AI Act evidence per subcategory through a built-in crosswalk (`opencomplai gaps --target NIST_AI_RMF`, no new scanner — see [NIST AI RMF](docs/src/concepts/nist-ai-rmf.md)). ISO/IEC 42001 stays mapped only: a citation via the same crosswalk (`data/framework_crosswalk.json`), with no computed verdict of its own.

## How It Works (The 3-Minute Setup)

1. **Define:** Create a compliance manifest for your model.
2. **Integrate:** Copy the ready-made [GitHub Actions/GitLab CI workflow](docs/src/guides/ci-integration.md) into your pipeline.
3. **Ship:** Get an automated "Pass/Fail" result before your code ever hits production.

[**Check out our Dummy Repo (Sandbox)**](examples/sample-system/) – *Test how we catch AI errors without risking your production code.*

## Core Components

- `opencomplai-core`: The rule engine that evaluates controls.
- `opencomplai-cli`: Run checks locally in your dev environment.
- `opencomplai`: The Python SDK for embedding compliance into your own tooling — and the
  package `pip install opencomplai` actually installs. It depends on `opencomplai-core` and
  `opencomplai-cli`, so a single `pip install opencomplai` pulls in the whole stack (rule
  engine, CLI, and SDK) in one go.

## Quick Start

Get your first compliance check running in **under 15 minutes**:

```bash
pip install opencomplai
```

This installs the CLI, core rule engine, and SDK with a stable API contract (see
[CHANGELOG](CHANGELOG.md) for exit-code and artifact-schema guarantees).

```bash
opencomplai init --system-id my-model --intended-purpose "customer support chatbot"
opencomplai check
```

That's the local loop. For the full path — CI gate, optional dashboard push, pre-commit
hook, and self-hosted Docker Compose — see the
[Deployment Journey](docs/src/getting-started/deployment-journey.md).

`opencomplai scan` inventories files via a repo-root `.ocignore` (not `.gitignore`),
bootstrapped once from `.gitignore` on first scan unless you pass
`--no-ocignore-bootstrap`. `opencomplai check --scan` bootstraps and uses it the same
way; plain `opencomplai check` never touches it. See
[`.ocignore` scan configuration](https://docs.opencomplai.com/getting-started/scanner/#ocignore).

## Community & Feedback

OpenComplAI is free to use today — `opencomplai scan --quick` and the EU AI Act Checker below
both work with zero setup. We're actively building with early adopters and want your feedback.

- **[Join our Developer Discord](https://discord.gg/egjX5JgQJ)** — discuss EU AI Act workflows, pipeline integration, and stress-test the engine with other MLOps engineers
- [Report a bug](https://github.com/Opencomplai/opencomplai/issues/new?template=bug_report.md) · [Request a feature](https://github.com/Opencomplai/opencomplai/discussions/new?category=ideas)
- [LinkedIn](https://www.linkedin.com/company/opencomplai) · [Reddit research community](https://www.reddit.com/user/akin_opencomplai/m/opencomplai_research/)

## EU AI Act Checker

Not sure whether the EU AI Act applies to your system, or which obligations you carry as a provider versus a deployer? Use the interactive [EU AI Act Checker](https://docs.opencomplai.com/getting-started/eu-ai-act-checker/) — a browser-based wizard covering scope, high-risk classification, GPAI, and obligations. No account needed. Or run it locally:

```bash
opencomplai checker --web          # opens the hosted docs page
opencomplai checker --web --local  # serves a self-contained copy offline
```

## Persistent control register & honest Annex IV documentation

Beyond the per-run pass/fail gate, Opencomplai maintains a **persistent
control register** (requires an evidence vault): one control per EU AI Act
article, tracked across runs with an owner, an evidence-freshness TTL, and a
state (`satisfied` / `evidence_missing` / `evidence_stale` / `pending_review`
/ `waived`). `opencomplai controls status` gives you a CI-consumable summary
of exactly what's missing or gone stale.

The Annex IV dossier generated by `opencomplai docs generate` never claims
more than the code actually does: every field is either automated from your
manifest and risk classification, wired evidence loaded from a real scan/eval
report, or an explicit provider-attestation placeholder when nobody has
supplied it yet. Opencomplai assembles supporting evidence — **it does not
certify that you are compliant**, and a dossier still carrying placeholders
for a HIGH-risk system fails the release gate rather than being presented as
complete. See [Controls Lifecycle](docs/src/concepts/controls.md) and the
[Annex IV Coverage Ledger](docs/src/concepts/annex-iv-coverage.md) for the
full breakdown.

## Architecture overview

| Component | Kind | Responsibility |
|---|---|---|
| core | package | Risk assessment primitives and policy mapping logic (no HTTP). |
| cli | package | Command-line interface that runs local checks and orchestrates workflows. |
| sdk-python | package | Python SDK that wraps the core and provides a stable integration surface. |
| gateway-api | service | HTTP entrypoint for multi-service deployments; request validation and routing. |
| risk-engine | service | Risk classification execution and rules evaluation as a service. |
| evidence-vault | service | Evidence storage with immutability guarantees and content-addressed artifacts. |
| doc-generator | service | Dossier/document generation (e.g. Annex IV-style outputs) from stored evidence. |
| egress-proxy | service | Allowlisted egress enforcement for controlled external connectivity. |

## Repository layout

```text
opencomplai/
├── packages/
│   ├── core/              # Risk assessment engine — Python, Pydantic v2, no HTTP
│   ├── cli/               # CLI tool — Typer + Rich, calls core or gateway-api
│   └── sdk-python/        # Python SDK — pip-installable, wraps core
├── services/
│   ├── gateway-api/       # REST API — Node.js + TypeScript + Fastify (OpenAPI-first)
│   ├── risk-engine/       # Risk classification service — Python + FastAPI
│   ├── evidence-vault/    # Immutable ledger + CAS — Python + FastAPI + PostgreSQL
│   ├── doc-generator/     # Annex IV dossier generator — Python + FastAPI
│   └── egress-proxy/      # Allowlisted egress enforcer — Python + FastAPI
├── tools/
│   └── verify-ledger/     # Evidence ledger chain verification tool
├── infra/
│   ├── docker/            # Dockerfiles (one per service)
│   ├── compose/           # Docker Compose reference deployment + .env.example
│   └── migrations/        # Alembic database migrations
├── docs/                  # MkDocs documentation (published via GitHub Actions)
├── examples/              # Working code examples
├── sync/                  # bootstrap.sh, doctor.py, verify-sbom.sh, demo seed/reset scripts
├── scripts/               # generate_principle_docs.py
└── .github/
    ├── workflows/         # GitHub Actions CI workflows
    ├── ISSUE_TEMPLATE/
    └── pull_request_template.md
```

## Editions

Opencomplai is open-core:

- **Community Edition** — this repository, licensed under **AGPL-3.0**. The full risk
  assessment engine, CLI, SDK, services, and EU AI Act checker.
- **Enterprise Edition** — a hosted premium dashboard, single sign-on, additional
  rule engines, and commercial support, available under a commercial licence. See
  [opencomplai.com](https://opencomplai.com) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, workflow conventions, and code
style. Look for issues labelled `good first issue` to find starter-sized contributions. All
contributors sign the [Contributor Licence Agreement](CLA.md).

## Maintainers

OpenComplAI is currently maintained by [@OpenComplaiCTO](https://github.com/OpenComplaiCTO).
Pull requests are typically reviewed within a few business days — if you haven't heard back
after a week, ping the PR directly or ask in
[GitHub Discussions](https://github.com/Opencomplai/opencomplai/discussions).

## AI use

The core rule engine (`packages/core`) and CLI are fully deterministic and rule-based — no
LLM or ML inference. An optional `packages/ai` plugin adds local ML/LLM inference (an
ONNX/transformers intent classifier, with an optional `[deep]` extra for local GGUF models
via llama-cpp-python); it is not installed or used unless a maintainer or contributor
explicitly opts in.

`pyproject.toml`, `package.json`, and `requirements*.txt` files are scanned in CI for
unapproved AI/LLM packages (excluding `tests/`, `examples/`, `fixtures/`, `node_modules/`,
`.venv/`, and `dist/` paths). See
[docs/security/ai-inventory.md](docs/security/ai-inventory.md) for the full inventory and
the process for approving future AI dependencies.

## Licence

Opencomplai Community Edition is licensed under the GNU Affero General Public Licence v3.0
(AGPL-3.0) — see [LICENSE](LICENSE). For use cases that the AGPL does not fit, a commercial
licence is available as part of the Enterprise Edition; contact us via
[opencomplai.com](https://opencomplai.com).
