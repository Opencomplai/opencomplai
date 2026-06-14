# Air-gap Deployment

Run the full Opencomplai stack with zero outbound internet access.

## How it works

The `egress-proxy` service enforces an allowlist of outbound destinations. Setting `EGRESS_ALLOWED_DESTINATIONS=` (empty) blocks all outbound traffic from all services. Compliance checks run entirely within the internal Docker network.

## Configuration

In `infra/compose/.env`, set:

```bash
EGRESS_ALLOWED_DESTINATIONS=
```

This is the default for a freshly copied `.env.example`.

## CLI: air-gap scan mode

When running `opencomplai check` against the stack in air-gap mode, pass `--scan-mode airgap`:

```bash
OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check --scan-mode airgap
```

For fully local CLI operation (no Docker stack), the CLI falls back to the local engine automatically when `OPENCOMPLAI_API_URL` is not set — no additional flags needed.

## Pre-pulling images

To deploy without internet access on the target machine, pre-pull images on a connected machine and transfer as tarballs:

```bash
# On connected machine: pull and save
docker compose -f infra/compose/docker-compose.yml pull
docker save \
  ghcr.io/checkref-co/opencomplai/gateway-api:latest \
  ghcr.io/checkref-co/opencomplai/risk-engine:latest \
  ghcr.io/checkref-co/opencomplai/evidence-vault:latest \
  ghcr.io/checkref-co/opencomplai/doc-generator:latest \
  ghcr.io/checkref-co/opencomplai/egress-proxy:latest \
  postgres:16-alpine redis:7-alpine prom/prometheus grafana/grafana \
  | gzip > opencomplai-images.tar.gz

# On air-gapped machine: load
gunzip -c opencomplai-images.tar.gz | docker load
```

Then start the stack normally — Docker Compose will use the locally loaded images.

## Verification

After starting in air-gap mode, verify no outbound requests succeed:

```bash
# Should return an error (destination blocked by egress-proxy)
curl -f http://localhost:8080/v1/sync/metadata
```
