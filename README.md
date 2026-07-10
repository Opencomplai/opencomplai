# OpenComplAI: Compliance-as-Code for AI Pipelines

**Stop manual audits → Start shipping.**

OpenComplAI brings EU AI Act compliance directly into your CI/CD pipeline, turning fragmented legal mandates into automated, machine-readable "Pre-Ship Checks."

[![CI (Python)](https://github.com/Opencomplai/opencomplai/actions/workflows/ci-python.yml/badge.svg)](https://github.com/Opencomplai/opencomplai/actions/workflows/ci-python.yml) [![CI (Node)](https://github.com/Opencomplai/opencomplai/actions/workflows/ci-node.yml/badge.svg)](https://github.com/Opencomplai/opencomplai/actions/workflows/ci-node.yml) [![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/) [![Node.js](https://img.shields.io/badge/node-20%20LTS-339933.svg)](https://nodejs.org/)

## Why OpenComplAI?

Traditional GRC tools are disconnected dashboards that create "velocity tax." We shift compliance left:

- **Prevent Non-Compliance:** Gate releases by blocking builds that violate safety rules.
- **Automated Evidence:** Generate audit-ready logs automatically for every deployment.
- **Framework-Agnostic:** Built to adapt to evolving global standards (EU AI Act, NIST RMF, ISO).

## How It Works (The 3-Minute Setup)

1. **Define:** Create a compliance manifest for your model.
2. **Integrate:** Add the OpenComplAI action to your GitHub/GitLab pipeline.
3. **Ship:** Get an automated "Pass/Fail" result before your code ever hits production.

[**Check out our Dummy Repo (Sandbox)**](examples/sample-system/) – *Test how we catch AI errors without risking your production code.*

## Core Components

- `opencomplai-core`: The rule engine that evaluates controls.
- `opencomplai-cli`: Run checks locally in your dev environment.
- `opencomplai-sdk`: Programmatically embed compliance into your custom internal tooling.

## Quick Start

Get your first compliance check running in **under 15 minutes**:

The packages are pre-release and not yet published to PyPI, so `pip install opencomplai`
does not resolve yet. Install from source — the `core`, `cli`, and `sdk-python` packages
must be installed together:

```bash
git clone https://github.com/Opencomplai/opencomplai
cd opencomplai
pip install -e packages/core -e packages/cli -e packages/sdk-python
# or, with uv:  uv sync
```

Then run a first assessment:

```bash
opencomplai init --system-id my-model --intended-purpose "customer support chatbot"
opencomplai check
```

[View Full Documentation](https://docs.opencomplai.com/getting-started/quick-start/)

Full Docker-based deployment is documented in
[docs/src/deployment/quickstart.md](docs/src/deployment/quickstart.md).

## Community & Feedback

We are currently in a **Closed Beta Pilot**. If you are an AI engineer or ML platform lead, we want your feedback.

- **[Join our Developer Discord](https://discord.gg/egjX5JgQJ)** — discuss EU AI Act workflows, pipeline integration, and stress-test the engine with other MLOps engineers
- [Report a bug](https://github.com/Opencomplai/opencomplai/issues/new?template=bug_report.md) · [Request a feature](https://github.com/Opencomplai/opencomplai/discussions/new?category=ideas)
- [LinkedIn](https://www.linkedin.com/company/opencomplai) · [Reddit research community](https://www.reddit.com/user/akin_opencomplai/m/opencomplai_research/)

## EU AI Act Checker

Not sure whether the EU AI Act applies to your system, or which obligations you carry as a provider versus a deployer? Use the interactive [EU AI Act Checker](https://docs.opencomplai.com/getting-started/eu-ai-act-checker/) — a browser-based wizard covering scope, high-risk classification, GPAI, and obligations. No account needed. Or run it locally:

```bash
opencomplai checker --web          # opens the hosted docs page
opencomplai checker --web --local  # serves a self-contained copy offline
```

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
├── scripts/               # bootstrap.sh, doctor.py, verify-sbom.sh
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

## AI use

Opencomplai's classification logic is fully deterministic and rule-based. No LLM or ML
inference is used in production.

All dependency files are scanned in CI to enforce this policy. See
[docs/security/ai-inventory.md](docs/security/ai-inventory.md) for the full inventory and
the process for approving future AI dependencies.

## Licence

Opencomplai Community Edition is licensed under the GNU Affero General Public Licence v3.0
(AGPL-3.0) — see [LICENSE](LICENSE). For use cases that the AGPL does not fit, a commercial
licence is available as part of the Enterprise Edition; contact us via
[opencomplai.com](https://opencomplai.com).
