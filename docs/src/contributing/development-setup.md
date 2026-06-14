# Development Setup

Set up Opencomplai for local development. The project is a Python monorepo managed with `uv`, with a Node.js service (`gateway-api`) managed with `pnpm`, and an optional Docker Compose stack for integration work.

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | [python.org](https://www.python.org/) |
| uv | Latest | `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| Node.js | 20 LTS | [nodejs.org](https://nodejs.org/) |
| pnpm | 9+ | `npm install -g pnpm` |
| Docker | 24+ | [docs.docker.com](https://docs.docker.com/get-docker/) |
| pre-commit | Latest | `pip install pre-commit` |
| Git | 2.20+ | [git-scm.com](https://git-scm.com/) |

## 1. Clone the repository

```bash
git clone https://github.com/Checkref-co/opencomplai
cd opencomplai
```

## 2. One-command bootstrap

```bash
./scripts/bootstrap.sh
```

This script:

1. Verifies tool versions (`scripts/doctor.py`).
2. Creates `uv` virtual environments and installs all Python packages in editable mode.
3. Installs Node.js dependencies with `pnpm`.
4. Installs `pre-commit` hooks.

If any step fails, re-run after fixing the reported issue.

## 3. Manual setup (if bootstrap fails)

### Python packages

```bash
# Install all three packages in editable mode
uv pip install -e packages/core
uv pip install -e packages/cli
uv pip install -e packages/sdk-python
```

### Node.js (gateway-api)

```bash
cd services/gateway-api
pnpm install
cd ../..
```

### pre-commit hooks

```bash
pre-commit install
```

## 4. Run the test suite

### Python

```bash
# All packages
uv run pytest

# Specific package
uv run pytest packages/core/tests/
uv run pytest packages/cli/tests/
uv run pytest packages/sdk-python/tests/
```

### Node.js (gateway-api)

```bash
cd services/gateway-api
pnpm test
```

## 5. Run linters

```bash
# Python (ruff + mypy)
uv run ruff check .
uv run mypy packages/

# Node.js
cd services/gateway-api && pnpm lint
```

## 6. Optional: start the full Docker Compose stack

For integration work involving multiple services:

```bash
cp infra/compose/.env.example infra/compose/.env
# Set POSTGRES_PASSWORD in infra/compose/.env
docker compose -f infra/compose/docker-compose.yml up --build -d
```

See [Deployment Quickstart](../deployment/quickstart.md) for details.

## Repository layout

```text
opencomplai/
├── packages/
│   ├── core/              # Risk assessment engine — Python, Pydantic v2
│   ├── cli/               # CLI tool — Typer + Rich
│   └── sdk-python/        # Python SDK — wraps core
├── services/
│   ├── gateway-api/       # REST API — Node.js + TypeScript + Fastify
│   ├── risk-engine/       # Risk classification — Python + FastAPI
│   ├── evidence-vault/    # Merkle ledger + CAS — Python + FastAPI + PostgreSQL
│   ├── doc-generator/     # Annex IV dossier generator — Python + FastAPI
│   └── egress-proxy/      # Allowlisted egress enforcer — Python + FastAPI
├── infra/
│   ├── docker/            # Dockerfiles
│   ├── compose/           # Docker Compose + .env.example
│   └── migrations/        # Alembic migrations
├── docs/                  # MkDocs documentation
├── scripts/               # bootstrap.sh, doctor.py
└── .github/workflows/     # CI (ci-python.yml, ci-node.yml, ci-docker.yml)
```

## Troubleshooting

### `uv` not found

```bash
pip install uv
# or on macOS:
brew install uv
```

### `pnpm` not found

```bash
npm install -g pnpm
```

### Pre-commit hook fails

```bash
# See exactly what failed
pre-commit run --all-files

# Fix and re-commit (do NOT use --no-verify on real commits)
```

### Docker Compose services not healthy

```bash
docker compose -f infra/compose/docker-compose.yml logs --tail=50 <service-name>
```

Common cause: `POSTGRES_PASSWORD` not set in `infra/compose/.env`.
