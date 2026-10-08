# evidence-vault

The system of record for compliance evidence, written in Python on FastAPI with SQLAlchemy. It
holds an append-only, hash-chained event ledger, a content-addressable store (CAS) for evidence
objects, and the state the other services persist through it: the dossier index, HITL review items
and overrides, control state, bias alerts and compliance badges.

It is an **internal service**. In the Docker Compose stack it has no host port; clients reach it
through [gateway-api](../gateway-api/README.md), and [risk-engine](../risk-engine/README.md),
[doc-generator](../doc-generator/README.md) and [egress-proxy](../egress-proxy/README.md) call it
directly.

- **Ledger.** Each event's hash commits to the event and to the previous hash, so editing any
  historical event invalidates every later hash. `GET /v1/evidence/verify-chain` checks the chain.
  On Postgres the request-facing role is denied `UPDATE`, `DELETE` and `TRUNCATE` on the ledger table.
- **CAS.** Objects are stored and retrieved by SHA-256 content hash and are immutable once written.
  The blob store is keyed by hash alone, not by tenant.
- **Tenancy.** Every database-backed `/v1/*` route is scoped to the tenant in its `X-Tenant-Id`
  header, which gateway-api sets from the authenticated caller. With no header the tenant is
  `oss-default`. On Postgres each of those requests runs `SET ROLE evidence_vault_app` and sets the
  `app.tenant_id` setting for the transaction, so row-level security enforces the scope even if a
  query forgets to filter. `GET /v1/evidence/objects/{hash}` is the exception: it reads the CAS
  directly, without a tenant session, so any caller holding a valid service token can fetch an
  object whose hash it knows, whichever tenant stored it.

## Endpoints

| Route | Auth | Purpose |
|---|---|---|
| `GET /health` | none | Static liveness: `{"status":"ok","service":"evidence-vault"}`. |
| `GET /ready` | none | Readiness: checks the database and, on Postgres, that migrations have run (the `evidence_vault_app` role and the ledger table exist). 503 otherwise. Used by the Docker healthcheck. |
| `GET /metrics` | none | Prometheus metrics. |
| `/v1/evidence/events`, `/verify-chain`, `/ledger-root`, `/ledger-history-tips` | service token | Append events and read or verify the chain. |
| `/v1/evidence/objects` | service token | Store and fetch CAS objects. |
| `/v1/dossiers` | service token | Index of generated Annex IV dossiers. |
| `/v1/hitl/*`, `/v1/evals/cache` | service token | Persisted review items, review contexts, accepted overrides and eval results. |
| `/v1/controls`, `/v1/fingerprints` | service token | Per-system control state and manifest fingerprints. |
| `/v1/bias-alerts`, `/v1/admin/purge-bias-data` | service token | Bias alerts and their retention purge. Internal only. |
| `/v1/portfolio` | service token | One entry per system on record for the tenant, with its most recent badge. |
| `/v1/pro/badges/*`, `/v1/pro/ingest/*` | service token | Compliance badges and Pro-tier ingest. |

Every `/v1/*` route requires a signed internal service token (HMAC-SHA256 over
`INTERNAL_SERVICE_TOKEN_SECRET`). With the secret unset those routes answer 503.

## Run locally

From the repo root, with [uv](https://github.com/astral-sh/uv) and Python 3.11:

```bash
uv sync --all-packages
export INTERNAL_SERVICE_TOKEN_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export EVIDENCE_DATA_DIR=./evidence-data
uv run uvicorn opencomplai_evidence_vault.main:app --port 8002
curl http://localhost:8002/ready
```

With `DATABASE_URL` unset the service uses a SQLite file, `./evidence-vault.db`, and creates its
schema on startup. That is the development and test path. For Postgres, set `DATABASE_URL` and
apply the Alembic migrations, which also create the `evidence_vault_app` role the request path needs:

```bash
cd services/evidence-vault
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<db> uv run alembic upgrade head
```

To run the whole stack instead, see [Deployment quickstart](../../docs/src/deployment/quickstart.md).
The Docker image runs `alembic upgrade head` before it starts uvicorn.

## Tests

```bash
uv run pytest services/evidence-vault -v --tb=short
```

CI runs this in the `test-services` job of `.github/workflows/ci-python.yml` against a Postgres 16
service. Without Postgres the suite still runs on SQLite, but the Postgres-only tests (row-level
security and readiness) are skipped. To run them, set both of these to a disposable database:

```bash
export EVIDENCE_VAULT_POSTGRES_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db>
export DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<db>
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `INTERNAL_SERVICE_TOKEN_SECRET` | unset | **Required.** Verifies inbound service tokens. Must match the other services. |
| `DATABASE_URL` | `sqlite:///./evidence-vault.db` | Database connection. `postgresql://` and `postgres://` URLs are switched to the asyncpg driver automatically. Required for the Alembic migrations. |
| `EVIDENCE_DATA_DIR` | `/tmp/evidence` | Directory for CAS objects when the local backend is used. |
| `STORAGE_BACKEND` | `local` | CAS backend: `local` or `vercel_blob`. |
| `BLOB_READ_WRITE_TOKEN` | unset | Credential for the `vercel_blob` backend, which also needs the `vercel-blob` package installed. Not used by `local`. |
| `EVIDENCE_VAULT_AUTO_MIGRATE` | `0` | Set to `1` to run `alembic upgrade head` inside the service at startup. |
| `EVIDENCE_VAULT_SKIP_MIGRATIONS` | `0` | Container entrypoint only. Set to `1` to skip its `alembic upgrade head`, for example when a separate step migrates the database. |
| `EVIDENCE_VAULT_SERVICE_ROOT` | `/app/services/evidence-vault` | Container entrypoint only. Directory the entrypoint runs Alembic from. |
| `OSS_BADGE_PUBLIC_KEY_PATH` | unset | Path to the Ed25519 public key that badge signatures are verified against. When unset, badge signatures are accepted without verification. |
| `OTEL_SERVICE_NAME` | `evidence-vault` | Overrides the service name on telemetry. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | gRPC OTLP endpoint for traces; export is off when unset. |

The Compose file also sets `PORT` and `KEY_DATA_DIR` for this service. The code does not read
either: the listen port comes from the entrypoint (`--port 8002`).

See [Configuration](../../docs/src/deployment/configuration.md) for the stack-wide variables and
[Observability](../../docs/src/deployment/observability.md) for metrics and health monitoring.

## Docker

Built by `infra/docker/evidence-vault.Dockerfile`; the image listens on port 8002, runs
`infra/docker/evidence-vault-entrypoint.sh`, and its healthcheck calls `/ready`. The entrypoint
migrates only when `DATABASE_URL` is set, and exits without starting the server if the migration fails.
