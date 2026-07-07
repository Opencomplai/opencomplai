# Common Issues

Real issues encountered during setup and CI integration, with exact remediation steps.

---

## `POSTGRES_PASSWORD` not set — stack refuses to start

**Symptom:**

```text
Error response from daemon: No configuration found for service "postgres"
```

or the PostgreSQL container exits immediately with:

```text
error: database is uninitialized and superuser password is not specified
```

**Cause:** `POSTGRES_PASSWORD` has no default and Docker Compose will not start the PostgreSQL container without it.

**Fix:**

=== "macOS / Linux"
    ```bash
    cd infra/compose
    cp .env.example .env
    # Edit .env and set a real password:
    # POSTGRES_PASSWORD=use_a_strong_random_password_here
    ```

=== "Windows (PowerShell)"
    ```powershell
    cd infra/compose
    Copy-Item .env.example .env
    # Edit .env and set a real password:
    # POSTGRES_PASSWORD=use_a_strong_random_password_here
    ```

---

## Port 8080 is already in use

**Symptom:**

```text
Error starting userland proxy: listen tcp4 0.0.0.0:8080: bind: address already in use
```

**Fix:** Change `GATEWAY_PORT` in `infra/compose/.env`:

```bash
GATEWAY_PORT=8081
```

Then restart the stack and update `OPENCOMPLAI_API_URL` accordingly:

=== "macOS / Linux"
    ```bash
    export OPENCOMPLAI_API_URL=http://localhost:8081
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_API_URL = "http://localhost:8081"
    ```

---

## `OPENCOMPLAI_API_URL` not set — running in local mode unexpectedly

**Symptom:** `opencomplai check` passes even though you expect it to route through the Docker Compose services.

**Cause:** When `OPENCOMPLAI_API_URL` is unset, the CLI silently falls back to local engine mode (no services required). This is correct behaviour for quickstart use, but not for service-backed CI.

**Fix:**

=== "macOS / Linux"
    ```bash
    export OPENCOMPLAI_API_URL=http://localhost:8080
    opencomplai check
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"
    opencomplai check
    ```

Confirm service-backed mode is active by looking for gateway service calls in the output, or by checking `compliance-artifact.json` for non-empty `evidence_hashes`.

---

## `opencomplai init` — "signing keypair already exists"

**Symptom:**

```text
Signing keypair already exists at /home/user/.opencomplai
```

**Cause:** `opencomplai init` is idempotent — it skips key generation if `~/.opencomplai/signing.key` already exists. This is not an error.

**If you want a fresh keypair** (e.g. rotating keys):

=== "macOS / Linux"
    ```bash
    rm ~/.opencomplai/signing.key ~/.opencomplai/signing.pub ~/.opencomplai/config.yaml
    opencomplai init --system-id <id> --intended-purpose <purpose>
    ```

=== "Windows (PowerShell)"
    ```powershell
    Remove-Item "$env:USERPROFILE\.opencomplai\signing.key", "$env:USERPROFILE\.opencomplai\signing.pub", "$env:USERPROFILE\.opencomplai\config.yaml" -ErrorAction SilentlyContinue
    opencomplai init --system-id <id> --intended-purpose <purpose>
    ```

---

## Manifest validation error (exit code 2)

**Symptom:**

```text
Manifest validation error: <field> field required
```

**Cause:** The `system-manifest.json` is missing a required field (`system_id`, `intended_purpose`, etc.), or the JSON is malformed.

**Fix:**

=== "macOS / Linux"
    ```bash
    # Validate and see the error
    opencomplai validate-manifest system-manifest.json

    # Regenerate a valid manifest
    opencomplai init \
      --system-id "my-system" \
      --intended-purpose "automated credit scoring"
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Validate and see the error
    opencomplai validate-manifest system-manifest.json

    # Regenerate a valid manifest
    opencomplai init --system-id "my-system" --intended-purpose "automated credit scoring"
    ```

---

## `opencomplai check` exits with code 1 (CONTROL_FAIL)

**Cause:** One or more critical compliance controls failed. This is the expected blocking behaviour in CI — the pipeline should fail when controls fail.

**Fix:**

1. Check `compliance-artifact.json` for the `failed_controls` list.
2. Review the relevant rule in `packages/core/src/opencomplai_core/rules.py`.
3. Either remediate the system to pass the control, or update `system-manifest.json` to provide the correct `answers` for that rule.

---

## `opencomplai check` exits with code 4 (TRAP_DETECTED)

**Cause:** The `SubstantialModificationRule` (`EU_AIA_ART25_MODIFICATION_TRAP`) triggered — the model or system was found to have substantially changed in a way that triggers Art. 25 re-assessment obligations.

**Fix:** Review the system change against EU AI Act Article 25 obligations. If the modification is intentional and documented, set:

```python
answers={"substantial_modification": False}
```

only after completing the appropriate conformity assessment.

---

## `opencomplai check` exits with code 3 (POLICY_BLOCK)

**Cause:** The system was classified as `unacceptable` risk under EU AI Act Title II (Art. 5). Prohibited AI practices produce this result regardless of other controls.

**Fix:** Review your `intended_purpose` — if it describes a prohibited practice (social scoring, real-time biometric identification in public spaces, etc.), the block is correct by design.

---

## Signing fails — `cryptography` not installed

**Symptom:**

```text
Warning: signing disabled — cryptography not installed. Run: pip install cryptography
```

**Fix:**

=== "macOS / Linux"
    ```bash
    pip install cryptography
    # or, in the editable install:
    uv pip install cryptography
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install cryptography
    # or, in the editable install:
    uv pip install cryptography
    ```

---

## Exit code reference

| Code | `ScanResult` | Meaning |
|---|---|---|
| 0 | `pass` | All controls passed. |
| 1 | `control_fail` | One or more critical controls failed. |
| 2 | `validation_fail` | Manifest or input validation error. |
| 3 | `policy_block` | Egress or policy enforcement blocked the operation. |
| 4 | `trap_detected` | Substantial modification or profiling trap triggered. |

See [Exit codes](../cli/exit-codes.md) for the full table.
