# CI Integration Cookbook

Patterns for integrating Opencomplai checks into CI/CD pipelines efficiently.

## Minimal GitHub Actions step

```yaml
- name: Compliance check
  run: |
    pip install opencomplai
    opencomplai init \
      --system-id "${{ vars.SYSTEM_ID }}" \
      --intended-purpose "${{ vars.INTENDED_PURPOSE }}"
    opencomplai check --scan-mode ci
```

Exit code 0 = pass. Non-zero = fail (see [Exit codes](../cli/exit-codes.md)).

## Upload the compliance artifact

```yaml
- name: Compliance check
  run: opencomplai check --scan-mode ci --output json | tee compliance-artifact.json

- name: Upload compliance artifact
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: compliance-artifact
    path: compliance-artifact.json
```

## Cache the install

```yaml
- name: Cache opencomplai install
  uses: actions/cache@v4
  with:
    path: ~/.opencomplai
    key: opencomplai-install-${{ runner.os }}

- name: Init (once per cache miss)
  run: |
    if [ ! -f ~/.opencomplai/config.yaml ]; then
      opencomplai init --system-id my-model --intended-purpose "..."
    fi
```

## Service-backed mode in CI

If you run the Docker Compose stack as a CI service:

```yaml
services:
  opencomplai:
    image: ghcr.io/opencomplai/opencomplai/gateway-api:latest
    ports: ["8080:8080"]
    env:
      POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}

steps:
  - name: Compliance check (service-backed)
    env:
      OPENCOMPLAI_API_URL: http://localhost:8080
    run: opencomplai check --scan-mode ci --sign
```

## Performance expectations

| Mode | Typical duration |
|---|---|
| Local (no Docker) | < 100 ms |
| Service-backed (Docker Compose) | 200–500 ms per step, ~2 s full workflow |
| Air-gap (service-backed, no outbound) | Same as service-backed |

Local mode is fastest for CI pipelines that only need risk classification and don't require the Annex IV dossier or evidence ledger.
