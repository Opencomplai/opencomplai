# CI integration

OpenComplAI runs in GitHub Actions and GitLab CI via the CLI and connector scripts.

## GitHub Actions

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
- run: pip install opencomplai
- run: |
    opencomplai check \
      --manifest system-manifest.json \
      --sample-set examples/eval_set.json \
      --sign \
      --scan-mode ci
  env:
    OPENCOMPLAI_API_URL: ${{ secrets.OPENCOMPLAI_API_URL }}
    OPENCOMPLAI_DASHBOARD_URL: ${{ secrets.OPENCOMPLAI_DASHBOARD_URL }}
    OPENCOMPLAI_AUTH_TOKEN: ${{ secrets.OPENCOMPLAI_AUTH_TOKEN }}
    OPENCOMPLAI_TENANT_ID: ${{ secrets.OPENCOMPLAI_TENANT_ID }}
```

Or use the connector:

```yaml
- run: opencomplai-gha-connector
  env:
    OPENCOMPLAI_DASHBOARD_URL: ${{ secrets.OPENCOMPLAI_DASHBOARD_URL }}
    OPENCOMPLAI_AUTH_TOKEN: ${{ secrets.OPENCOMPLAI_AUTH_TOKEN }}
    OPENCOMPLAI_TENANT_ID: ${{ secrets.OPENCOMPLAI_TENANT_ID }}
```

Pass `--sample-set` through `check_args` when wrapping the connector locally.

## GitLab CI

```yaml
compliance:
  image: python:3.11
  script:
    - pip install opencomplai
    - opencomplai check --manifest system-manifest.json --sample-set examples/eval_set.json --sign --scan-mode ci
```

## Scope

v1 focuses on the EU AI Act. OpenComplAI produces structured evidence, not legal sign-off. Pipeline evaluators (safety, bias, data-leakage) require a customer-supplied `EvalSampleSet` JSON; when omitted, evals are skipped and rule checks still run.
