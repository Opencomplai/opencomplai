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

`--scan-mode airgap` is a label only: it is recorded in the artifact and does not itself block network access. Network isolation comes from the `egress-proxy` allowlist described above. To run `opencomplai check` against the stack, set `OPENCOMPLAI_API_URL`:

=== "macOS / Linux"
    ```bash
    OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check --scan-mode airgap
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"
    opencomplai check --scan-mode airgap
    ```

For fully local CLI operation (no Docker stack), the CLI falls back to the local engine automatically when `OPENCOMPLAI_API_URL` is not set — no additional flags needed.

## Transferring images

The OpenComplAI services are built from source by `infra/compose/docker-compose.yml`; prebuilt GHCR images are not documented as available. On a connected machine, build the images and save every image the compose file names, then transfer the tarball:

=== "macOS / Linux"
    ```bash
    # On connected machine: build and save
    docker compose -f infra/compose/docker-compose.yml build
    docker save $(docker compose -f infra/compose/docker-compose.yml config --images) \
      | gzip > opencomplai-images.tar.gz

    # On air-gapped machine: load
    gunzip -c opencomplai-images.tar.gz | docker load
    ```

=== "Windows (PowerShell)"
    ```powershell
    # On connected machine: build and save
    docker compose -f infra/compose/docker-compose.yml build
    $images = docker compose -f infra/compose/docker-compose.yml config --images
    docker save $images -o opencomplai-images.tar

    # On air-gapped machine: load
    docker load -i opencomplai-images.tar
    ```

Then start the stack normally — Docker Compose will use the locally loaded images.

## Verification

After starting in air-gap mode, verify no outbound requests succeed:

=== "macOS / Linux"
    ```bash
    # Should return an error (destination blocked by egress-proxy)
    curl -f http://localhost:8080/v1/sync/metadata
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Should return an error (destination blocked by egress-proxy)
    Invoke-WebRequest -Uri "http://localhost:8080/v1/sync/metadata"
    ```
