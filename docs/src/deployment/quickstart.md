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

```bash
git clone https://github.com/Checkref-co/opencomplai
cd opencomplai
cp infra/compose/.env.example infra/compose/.env
```

Edit `infra/compose/.env` — at minimum you **must** set `POSTGRES_PASSWORD` or the stack will refuse to start:

```bash
POSTGRES_PASSWORD=use_a_strong_random_password_here
```

See [Configuration](configuration.md) for the full env-var reference.

## Start the stack

```bash
docker compose -f infra/compose/docker-compose.yml up --build -d
```

## Verify all services are healthy

```bash
docker compose -f infra/compose/docker-compose.yml ps
# All services should show "(healthy)"

curl http://localhost:8080/health
# {"status":"ok","service":"gateway-api","version":"0.1.0-dev"}
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

```bash
pip install opencomplai
opencomplai init --system-id "my-model" --intended-purpose "customer support chatbot"
OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check
```

## Stop the stack

```bash
docker compose -f infra/compose/docker-compose.yml down
# To also remove volumes (deletes all evidence data):
docker compose -f infra/compose/docker-compose.yml down -v
```

## Air-gap mode

Set `EGRESS_ALLOWED_DESTINATIONS=` (empty) in `infra/compose/.env` to disable all outbound traffic. All compliance checks run fully locally. See [Air-gap](airgap.md).
