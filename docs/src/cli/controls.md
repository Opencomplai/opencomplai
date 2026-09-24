# controls

Operator surface for the persistent control register: list control
instances, assign an owner and TTL, attach evidence, and print a
CI-consumable status line.

**What:** the "missing/stale evidence queue," made visible and actionable
from the command line.

**When:** after at least one `opencomplai gaps`/`check` run has derived
controls for a system into the vault.

Controls come from the EU AI Act gap report and from every natively evaluated
target framework besides it, whose requirement ids carry a `<FW>:` prefix; a
requirement excluded in the manifest's `framework_inputs` becomes a waived
control with its reason as the rationale. NIST AI RMF is derived from the EU
AI Act evidence and adds no controls. See [Frameworks](../frameworks/index.md).

**Requires:** `OPENCOMPLAI_VAULT_URL`. Every `controls` subcommand refuses
with exit `2` if it isn't set — the register has no vault-less local
fallback (unlike `gaps`/`check`, where vault sync is an optional side
effect). See [Controls lifecycle](../concepts/controls.md) for the full
model, derivation, and freshness rules.

## `controls list`

List control instances for a system, with read-time TTL staleness.

=== "macOS / Linux"
    ```bash
    opencomplai controls list --system-id loan-decision-model
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai controls list --system-id loan-decision-model
    ```

### Options

| Flag | Default | Description |
|---|---|---|
| `--system-id` | *(required)* | System identifier. |
| `--state` | *(none)* | Filter to a single `ControlState` (`satisfied`, `evidence_missing`, `evidence_stale`, `pending_review`, `waived`). |
| `--output` / `-o` | `human` | `human` or `json`. |

Human output is a table (Control ID, Article, State, Owner, Due At, Stale) plus a
one-line summary. `list` always exits `0` on success — only `status` gates CI.

## `controls assign`

Assign an owner (and optionally a per-control TTL override) to a control instance.

=== "macOS / Linux"
    ```bash
    opencomplai controls assign <control-id> \
      --system-id loan-decision-model \
      --owner qa@example.com \
      --ttl-days 45
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai controls assign <control-id> --system-id loan-decision-model --owner qa@example.com --ttl-days 45
    ```

### Options

| Flag | Default | Description |
|---|---|---|
| `<control-id>` | *(required, positional)* | Control instance id. |
| `--system-id` | *(required)* | System identifier. |
| `--owner` | *(required)* | Accountable owner email. |
| `--ttl-days` | *(none)* | Per-control evidence freshness TTL override. Falls back to the [catalog default](../concepts/controls.md#catalog-ttl-defaults) for the control's article when unset. |
| `--output` / `-o` | `human` | `human` or `json`. |

## `controls attach-evidence`

Store a file as evidence (content-addressed, with EVID-PROV provenance
metadata), bind its hash to the control, and re-evaluate the control's
state.

=== "macOS / Linux"
    ```bash
    opencomplai controls attach-evidence <control-id> ./audit-log.pdf \
      --system-id loan-decision-model \
      --source manual \
      --source-version 1
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai controls attach-evidence <control-id> .\audit-log.pdf --system-id loan-decision-model --source manual --source-version 1
    ```

### Options

| Flag | Default | Description |
|---|---|---|
| `<control-id>` | *(required, positional)* | Control instance id. |
| `<path>` | *(required, positional)* | Path to the evidence file. |
| `--system-id` | *(required)* | System identifier. |
| `--source` | `opencomplai-cli` | Identity of the collecting tool. |
| `--source-version` | CLI version | Version of the collecting tool. |
| `--valid-until` | *(none)* | ISO-8601 timestamp after which this evidence is stale. Takes precedence over the TTL-derived due date if earlier. |
| `--output` / `-o` | `human` | `human` or `json`. |

The file's SHA-256 content hash becomes its evidence-vault key. Attaching
evidence moves the control's state to `satisfied` (unless it is currently
`waived`, which is preserved) and prints the computed due date:

```text
Attached sha256:3e2f1a9c1b7d…19… to a1b2c3d4e5f6 (Art. 9) — state satisfied, due 2026-11-18T10:00:00+00:00
```

## `controls status`

One-line control register summary for CI. Exits non-zero when there's
something to look at.

=== "macOS / Linux"
    ```bash
    opencomplai controls status --system-id loan-decision-model
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai controls status --system-id loan-decision-model
    ```

```text
controls: 17 total · 1 satisfied · 15 evidence_missing · 1 evidence_stale · 0 pending_review · 0 waived · 1 stale-by-ttl
```

This example exits `1` — there is real attention needed (missing/stale
evidence). This output is illustrative, not a guarantee about any particular
system's real state.

### Options

| Flag | Default | Description |
|---|---|---|
| `--system-id` | *(required)* | System identifier. |
| `--fail-on-missing` / `--no-fail-on-missing` | `--fail-on-missing` (on) | Whether `evidence_missing` controls also gate exit code `1`. Turn off to only gate on `evidence_stale` / `pending_review` / TTL-expired. |
| `--framework` | `EU_AI_ACT` plus gated frameworks | Count only this framework's controls; repeat for several. Controls of other frameworks have requirement ids prefixed `<FW>:`. Without the flag, the frameworks listed under `gate.frameworks` in `./opencomplai.yaml` (see [`check`](check.md#gating-other-frameworks)) are counted too. An unknown framework exits `2`. |
| `--output` / `-o` | `human` | `human` or `json`. |

Machine-readable form:

=== "macOS / Linux"
    ```bash
    opencomplai controls status --system-id loan-decision-model --output json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai controls status --system-id loan-decision-model --output json
    ```

```json
{
  "system_id": "loan-decision-model",
  "summary": {
    "satisfied": 1,
    "evidence_missing": 15,
    "evidence_stale": 1,
    "pending_review": 0,
    "waived": 0
  },
  "stale_count": 1,
  "exit_code": 1
}
```

## Exit codes

| Code | When it happens |
|---:|---|
| `0` | Every control is satisfied or waived, and none are stale by TTL. |
| `1` | A control is `evidence_missing` (unless `--no-fail-on-missing`), `evidence_stale`, `pending_review`, or stale by TTL. |
| `2` | `OPENCOMPLAI_VAULT_URL` is not set, or an input (control id, file path) was invalid. |
| `3` | The evidence-vault request failed (network/service error). |

`controls list`, `controls assign`, and `controls attach-evidence` always
exit `0` on success — only `controls status` gates CI. See
[Exit codes](exit-codes.md#control-register-opencomplai-controls) for the
full contract.

## See also

- [Controls lifecycle](../concepts/controls.md) — the model, derivation, freshness, and reassessment behind these commands.
- [gaps](gaps.md) — the command that derives control instances in the first place.
