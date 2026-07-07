# Error Handling

## CLI exit codes

`opencomplai check` produces deterministic exit codes. Use them directly in CI scripts:

| Code | `ScanResult` | Meaning | Action |
|---|---|---|---|
| 0 | `pass` | All controls passed | Proceed |
| 1 | `control_fail` | One or more critical controls failed | Block; review `failed_controls` in `compliance-artifact.json` |
| 2 | `validation_fail` | Manifest or input validation error | Fix `system-manifest.json`; re-run `opencomplai validate-manifest` |
| 3 | `policy_block` | Egress or policy enforcement blocked | Review `intended_purpose`; check `EGRESS_ALLOWED_DESTINATIONS` |
| 4 | `trap_detected` | Substantial modification trap triggered | Review Art. 25 obligations; re-assess if intentional change |

The `degraded_complete` state exits with code `0` in local mode and `1` in CI mode.

## Handling `control_fail` in CI

When `check` exits 1, inspect the artifact:

=== "macOS / Linux"
    ```bash
    opencomplai check --scan-mode ci --output json | tee compliance-artifact.json
    cat compliance-artifact.json | python3 -c \
      "import json,sys; a=json.load(sys.stdin); [print(c) for c in a['failed_controls']]"
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check --scan-mode ci --output json | Tee-Object compliance-artifact.json
    python -c "import json,sys; a=json.load(open('compliance-artifact.json')); [print(c) for c in a['failed_controls']]"
    ```

Then look up the rule in `packages/core/src/opencomplai_core/rules.py` and follow the `rationale` in the rule result to understand what needs to change.

## Gateway API error envelope

All gateway API errors return the standard envelope:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "system_id is required",
  "category": "client",
  "retryable": false,
  "correlation_id": "req-abc123"
}
```

`category: "client"` means fix the request. `category: "server"` means retry may help.

## Common error codes

| `error_code` | HTTP | When |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Request body failed schema validation |
| `NOT_FOUND` | 404 | Resource does not exist |
| `SERVICE_UNAVAILABLE` | 503 | A downstream service (risk-engine, evidence-vault, etc.) is unreachable |
| `POLICY_BLOCK` | 403 | Egress proxy blocked the outbound call |

## Service connectivity errors

If `OPENCOMPLAI_API_URL` is set but the service is unreachable, the CLI prints:

```text
Service call failed: <error>
```

and exits with code 3. Check:

1. `docker compose -f infra/compose/docker-compose.yml ps` — all services should be `running`.
2. `OPENCOMPLAI_API_URL` matches the actual gateway port (default `http://localhost:8080`).
3. Firewall / network rules are not blocking the port.

See [Common Issues](../troubleshooting/common-issues.md) for remediation steps.
