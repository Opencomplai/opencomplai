# Exit codes

Opencomplai uses fixed, contractual exit codes so CI pipelines can reliably gate merges and deployments.

| Code | Constant | When it happens |
|---:|---|---|
| `0` | `PASS` | All critical controls passed. |
| `1` | `CONTROL_FAIL` | One or more critical controls failed (e.g. an Annex III high-risk use case, or a failed pipeline evaluator). |
| `2` | `VALIDATION_FAIL` | Input or manifest validation failed (e.g., missing or invalid `system-manifest.json`). |
| `3` | `POLICY_BLOCK` | A prohibited (Article 5) practice was detected, e.g. `social scoring`. Works in **local** mode. |
| `4` | `TRAP_DETECTED` | Substantial-modification / profiling trap triggered. Raised only in **service-backed mode** (the Docker stack), not by the local CLI engine. |

## Typical CI usage

```yaml
- name: Compliance check
  run: opencomplai check
  # Step fails automatically on exit code 1, 2, 3, or 4.
```

## Remediation

| Exit code | Action |
|---|---|
| `1` | Review failed rules in the human output. Fix the compliance gap, then re-run. |
| `2` | Run `opencomplai init` first, or check that `system-manifest.json` is valid. |
| `3` | Review the policy configuration. Ensure egress destinations are allowed. |
| `4` | Contact your compliance team — a trap may indicate a supply-chain issue. |
