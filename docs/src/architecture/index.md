# Architecture

Opencomplai is a monorepo with three deployment modes: local-only (CLI + SDK), service-backed (CLI gateway API), and full Docker Compose stack.

## Components

| Component | Kind | Language | Responsibility |
|---|---|---|---|
| `opencomplai-core` | Python package | Python 3.11, Pydantic v2 | Rule engine — deterministic risk assessment, no HTTP. |
| `opencomplai-cli` | Python package | Python 3.11, Typer, Rich | CLI tool — `init`, `check`, `risk classify`, `validate-manifest`, `docs generate`, `sync metadata`, `dashboard`. |
| `opencomplai` (SDK) | Python package | Python 3.11 | Stable pip-installable surface wrapping `core`. |
| `gateway-api` | Service | Node.js 20, TypeScript, Fastify | REST API gateway — request validation, routing to backend services. |
| `risk-engine` | Service | Python, FastAPI | Risk classification as a service. |
| `evidence-vault` | Service | Python, FastAPI, PostgreSQL | Append-only Merkle ledger + content-addressed evidence storage. |
| `doc-generator` | Service | Python, FastAPI | Annex IV compliance dossier generation. |
| `egress-proxy` | Service | Python, FastAPI | Allowlisted outbound traffic enforcer (REQ-ARC-001). |

## Two execution modes

### Local mode (no Docker required)

```text
Developer machine
│
└── opencomplai check
    │
    ├── Reads system-manifest.json
    ├── Calls opencomplai-core engine (in-process)
    ├── Produces RiskResult
    └── Writes compliance-artifact.json
```

This is the default. No services, no network.

### Service-backed mode (OPENCOMPLAI_API_URL set)

```text
Developer machine / CI runner
│
└── opencomplai check
    │
    └── HTTP gateway-api :8080
                │
        ┌───────┼───────────┐
        ▼       ▼           ▼
    risk-   evidence-  doc-
    engine  vault      generator
    :8001   :8002      :8003
        │       │
        └───────┘
        egress-proxy :8004
        (allowlist enforcement)
```

## Deployment stack

See [Architecture: System Design](system-design.md) and [Deployment Quickstart](../deployment/quickstart.md).

## Sections

- [System Design](system-design.md) — service interactions and the 10-step scan workflow.
- [Data Model](data-model.md) — Pydantic models that form the shared data contract.
