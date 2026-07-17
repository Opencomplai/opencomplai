# dashboard

Manage enrollment in the Opencomplai Premium Dashboard.

For a **local** scan UI on your laptop (no SaaS), see [`opencomplai serve`](serve.md).

## Subcommands

| Subcommand | Description |
|---|---|
| `dashboard enroll` | Enroll this install in the Premium Dashboard. |
| `dashboard withdraw` | Remove dashboard enrollment for this install. |

---

## dashboard enroll

=== "macOS / Linux"
    ```bash
    opencomplai dashboard enroll --tenant <id> --token <token> [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai dashboard enroll --tenant <id> --token <token> [OPTIONS]
    ```

Opts an OSS install into the Premium Dashboard by:

1. Validating the one-time bootstrap token against the dashboard's enrollment API.
2. Registering the install's Ed25519 public signing key with the tenant.
3. Writing an `EgressConsent` (`consent_scope=dashboard_metadata`) to the local immutable ledger.
4. Adding the dashboard endpoint to `~/.opencomplai/egress_allowlist.json`.
5. Printing the dashboard URL and an audit-event hash the operator can independently verify.

**Prerequisites:** run `opencomplai init` first so `~/.opencomplai/signing.pub` exists.

### Options

| Option | Default | Description |
|---|---|---|
| `--tenant` | *(required)* | Tenant ID from the dashboard signup page. |
| `--token` | *(required)* | One-time bootstrap token generated in the dashboard. Tokens are single-use; a second use returns `TOKEN_CONSUMED`. |
| `--dashboard-url` | *(unset)* | Dashboard base URL. Defaults to `OPENCOMPLAI_DASHBOARD_URL` env var. |

### Environment variables

| Variable | Description |
|---|---|
| `OPENCOMPLAI_DASHBOARD_URL` | Dashboard base URL (e.g. `https://app.opencomplai.com`). Used when `--dashboard-url` is not passed. |

### Example

=== "macOS / Linux"
    ```bash
    opencomplai dashboard enroll \
      --tenant "t_abc123" \
      --token  "bt_xyz789" \
      --dashboard-url "https://app.opencomplai.com"
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai dashboard enroll --tenant "t_abc123" --token "bt_xyz789" --dashboard-url "https://app.opencomplai.com"
    ```

**Output:**

```text
Enrollment successful.
  tenant_id:        t_abc123
  install_id:       a1b2c3d4-...
  audit_event_hash: sha256:7f3e...

Dashboard: https://app.opencomplai.com

Next step: run opencomplai check --sign to emit your first signed artifact.
```

### Idempotency

Re-running `enroll` with the same tenant and install returns the existing enrollment without emitting a new ledger event.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Enrolled successfully (or already enrolled). |
| 2 | `install_id` or `signing.pub` not found — run `opencomplai init` first. Dashboard URL not set. |
| 3 | Dashboard API unreachable, token already consumed (`TOKEN_CONSUMED`), or enrollment rejected. |

---

## dashboard withdraw

=== "macOS / Linux"
    ```bash
    opencomplai dashboard withdraw --tenant <id> [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai dashboard withdraw --tenant <id> [OPTIONS]
    ```

Revokes dashboard enrollment for this install. Emits a `consent_revoked` ledger event and removes the egress allowlist entry within the same command run.

### Options

| Option | Default | Description |
|---|---|---|
| `--tenant` | *(required)* | Tenant ID to withdraw from. |
| `--dashboard-url` | *(unset)* | Dashboard base URL. Used to notify the dashboard of withdrawal (best-effort; failure is non-fatal). |

### Example

=== "macOS / Linux"
    ```bash
    opencomplai dashboard withdraw \
      --tenant "t_abc123"
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai dashboard withdraw --tenant "t_abc123"
    ```

**Output:**

```text
Withdrawal complete. Egress allowlist entry removed for tenant t_abc123.
  consent_revoked ledger event written.
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Withdrawal complete (or install was not enrolled). |
| 2 | `install_id` not found — run `opencomplai init` first. |
