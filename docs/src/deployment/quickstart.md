# Deployment Quickstart

Reference Docker deployment for the full Opencomplai platform.

!!! warning
    Never commit your `.env` file. It contains database credentials.

## Prerequisites

- Docker 24+
- Docker Compose v2
- 4 GB RAM
- 10 GB free disk

## Clone and configure

=== "macOS / Linux"
    ```bash
    git clone https://github.com/Opencomplai/opencomplai
    cd opencomplai
    cp infra/compose/.env.example infra/compose/.env
    ```

=== "Windows (PowerShell)"
    ```powershell
    git clone https://github.com/Opencomplai/opencomplai
    cd opencomplai
    Copy-Item infra/compose/.env.example infra/compose/.env
    ```

Edit `infra/compose/.env` — at minimum you **must** set `POSTGRES_PASSWORD` or the stack will refuse to start:

```bash
POSTGRES_PASSWORD=use_a_strong_random_password_here
```

See [Configuration](configuration.md) for the full env-var reference.

## Start the stack

=== "macOS / Linux"
    ```bash
    docker compose -f infra/compose/docker-compose.yml up --build -d
    ```

=== "Windows (PowerShell)"
    ```powershell
    docker compose -f infra/compose/docker-compose.yml up --build -d
    ```

## Database migrations

evidence-vault runs its Alembic migrations automatically at container boot,
before it starts serving traffic — the container's entrypoint runs `alembic
upgrade head` against `DATABASE_URL` and refuses to start (non-zero exit,
container stays unhealthy) if that fails, rather than serving requests
against an unmigrated database. `docker compose up` needs no separate
migration step.

To skip this (e.g. you run migrations yourself as a separate step), set
`EVIDENCE_VAULT_SKIP_MIGRATIONS=1` in `infra/compose/.env` for the
evidence-vault service. To run migrations manually instead, see
[infra/migrations/README.md](https://github.com/Opencomplai/opencomplai/blob/main/infra/migrations/README.md):

```bash
cd services/evidence-vault
DATABASE_URL=postgresql://<user>:<password>@localhost:5432/<db> alembic upgrade head
```

## Verify all services are healthy

=== "macOS / Linux"
    ```bash
    docker compose -f infra/compose/docker-compose.yml ps
    # All services should show "(healthy)"

    curl http://localhost:8080/health
    # {"status":"ok","service":"gateway-api","version":"0.9.0"}
    ```

=== "Windows (PowerShell)"
    ```powershell
    docker compose -f infra/compose/docker-compose.yml ps
    # All services should show "(healthy)"

    Invoke-WebRequest -Uri "http://localhost:8080/health"
    # {"status":"ok","service":"gateway-api","version":"0.9.0"}
    ```

## Service ports (default)

| Service | Port | Description |
|---|---|---|
| gateway-api | 8080 | Main entry point — all external traffic |
| risk-engine | 8001 | Risk classification (internal only) |
| evidence-vault | 8002 | Append-only Merkle ledger + CAS (internal only) |
| doc-generator | 8003 | Annex IV dossier generator (internal only) |
| egress-proxy | 8004 | Allowlisted outbound enforcer (internal only) |
| prometheus | 9090 | Metrics scraper (host-accessible) |
| grafana | 3001 | Operator dashboards (host-accessible) |

## Run a compliance check against the stack

=== "macOS / Linux"
    ```bash
    pip install opencomplai
    opencomplai init --system-id "my-model" --intended-purpose "customer support chatbot"
    OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai
    opencomplai init --system-id "my-model" --intended-purpose "customer support chatbot"
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"
    opencomplai check
    ```

## Stop the stack

=== "macOS / Linux"
    ```bash
    docker compose -f infra/compose/docker-compose.yml down
    # To also remove volumes (deletes all evidence data):
    docker compose -f infra/compose/docker-compose.yml down -v
    ```

=== "Windows (PowerShell)"
    ```powershell
    docker compose -f infra/compose/docker-compose.yml down
    # To also remove volumes (deletes all evidence data):
    docker compose -f infra/compose/docker-compose.yml down -v
    ```

## Air-gap mode

Set `EGRESS_ALLOWED_DESTINATIONS=` (empty) in `infra/compose/.env` to disable all outbound traffic. All compliance checks run fully locally. See [Air-gap](airgap.md).
