# Quick Start

Run your first Opencomplai compliance check in under 15 minutes.

## Prerequisites

Python 3.11+ and pip.

=== "macOS / Linux"
    ```bash
    python3 --version  # must be 3.11 or higher
    ```

=== "Windows (PowerShell)"
    ```powershell
    python --version   # must be 3.11 or higher
    ```

!!! note "`python` vs `python3`"
    On Windows the interpreter is usually `python`/`pip`; on macOS/Linux it is
    usually `python3`/`pip3`. Use whichever resolves on your machine.

## Install the SDK and CLI

=== "macOS / Linux"
    ```bash
    pip install opencomplai
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai
    ```

!!! note "Install from source"
    For development or if PyPI is unreachable, install from source — see
    [Installation](installation.md#install-from-source). The local `core` and `cli`
    packages must be installed in the **same command** as the SDK.

The install provides the `opencomplai` command. Verify it (there is **no**
`--version` flag — use `--help`):

=== "macOS / Linux"
    ```bash
    opencomplai --help
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai --help
    ```

## Try it with zero setup first

Before creating a manifest, run a **discovery-only** scan against any repo — no
manifest required, and it can never fail your build:

=== "macOS / Linux"
    ```bash
    opencomplai scan --quick .
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --quick .
    ```

```text
Discovery only — not a compliance verdict. No manifest was loaded and no CI gate was evaluated.

Detected categories: openai, vector_embedding

Suggested next step:
  opencomplai init --system-id <your-system-id> --intended-purpose "openai, vector_embedding"
```

`scan --quick` always exits `0` and never writes `compliance-artifact.json` — it exists
purely to answer *"does this repo look like it touches AI at all?"* before you commit to
declaring a system. Contrast this with `opencomplai check` below: `check` is the
command that actually gates CI and produces the compliance artifact. See the
[scan reference](../cli/scan.md#zero-config-discovery---quick) for the full flag
behavior.

## Initialise your system manifest

=== "macOS / Linux"
    ```bash
    opencomplai init \
      --system-id "my-model" \
      --intended-purpose "customer support chatbot"
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai init --system-id "my-model" --intended-purpose "customer support chatbot"
    ```

!!! tip "Line continuations differ by shell"
    bash/zsh continue a command with a trailing backslash `\`. PowerShell uses a
    backtick `` ` ``. The simplest cross-platform form is to keep the whole
    command on **one line**, as shown in the PowerShell tab.

This creates `system-manifest.json` in the current directory and sets up
`~/.opencomplai/` (Ed25519 signing keypair + config) on first run. Expected
output:

```text
Signing keypair generated C:\Users\you\.opencomplai
  install_id: 7f3c...
Manifest written to system-manifest.json
  system_id:         my-model
  intended_purpose:  customer support chatbot
  compliance_target: EU_AI_ACT

Next step: run opencomplai check to assess compliance.
```

On subsequent runs the first line instead reads
`Signing keypair already exists at ...` — that is expected and harmless.

## Run your first compliance check

=== "macOS / Linux"
    ```bash
    opencomplai check
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check
    ```

Expected output for the `customer support chatbot` purpose (a **MINIMAL**-risk
use case, so the check **passes**):

```text
Evals: no eval sample set supplied (skipped)

Opencomplai Compliance Check
  system_id:    my-model
  commit_ref:   HEAD
  result:       PASS
  duration_ms:  0
  signed:       no (OSS unsigned)

  Artifact written to compliance-artifact.json
```

The `Evals: no eval sample set supplied (skipped)` line appears only when you do
**not** pass `--sample-set` (see [Run pipeline evaluators](#run-pipeline-evaluators-on-your-own-data) below).

A `compliance-artifact.json` is written to the current directory — this is the
machine-readable `ScanStatusArtifact` consumed by CI gates.

!!! warning "Exit codes"
    `0` = `PASS`, `1` = `CONTROL_FAIL`, `2` = `VALIDATION_FAIL`,
    `3` = `POLICY_BLOCK`, `4` = `TRAP_DETECTED`. See
    [Exit codes](../cli/exit-codes.md) for the full table.

## Try the other compliance outcomes

The result is driven by the manifest's `intended_purpose`. Re-run `init` with a
different purpose, then `check`, to see each EU AI Act outcome. (Each `init`
overwrites `system-manifest.json` in the current directory.)

| `intended_purpose` | EU AI Act basis | `result` | `failed_controls` | Exit |
|---|---|---|---|---|
| `customer support chatbot` | Minimal risk | `PASS` | — | `0` |
| `recruitment screening of candidates` | Annex III high-risk (employment) | `CONTROL_FAIL` | `EU_AIA_ART6_HIGH_RISK` | `1` |
| `social scoring of citizens` | Article 5 prohibited practice | `POLICY_BLOCK` | `EU_AIA_ART5_UNACCEPTABLE` | `3` |

Example — the high-risk case:

=== "macOS / Linux"
    ```bash
    opencomplai init --system-id "hiring" \
      --intended-purpose "recruitment screening of candidates"
    opencomplai check
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai init --system-id "hiring" --intended-purpose "recruitment screening of candidates"
    opencomplai check
    ```

```text
Opencomplai Compliance Check
  system_id:    hiring
  commit_ref:   HEAD
  result:       CONTROL_FAIL
  duration_ms:  0
  signed:       no (OSS unsigned)
  failed_controls: EU_AIA_ART6_HIGH_RISK

  Artifact written to compliance-artifact.json
```

!!! note "`TRAP_DETECTED` (exit 4)"
    The substantial-modification trap (`EU_AIA_ART25_MODIFICATION_TRAP`) is only
    raised in **service-backed mode** (the Docker stack), not by the local CLI
    engine. See [Deployment Quickstart](../deployment/quickstart.md).

## Run pipeline evaluators on your own data

To check **safety, bias, and data-leakage** against real model outputs, pass an
`EvalSampleSet` JSON with `--sample-set`. Its `system_id` must match the
manifest. A clean sample passes; outputs containing toxic text, prompt
injection, or PII (SSN, secrets, credit cards) fail.

Create `eval-set.json`:

```json
{
  "eval_set_id": "demo-clean-v1",
  "system_id": "my-model",
  "commit_ref": "HEAD",
  "outputs": [
    "The system classified the request as low risk.",
    "No sensitive data was included in the model response."
  ],
  "prompts": ["Summarize the compliance status for this release."],
  "declared_output_fields": ["answer", "confidence", "risk_class"]
}
```

=== "macOS / Linux"
    ```bash
    opencomplai check --sample-set eval-set.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check --sample-set eval-set.json
    ```

```text
Opencomplai Compliance Check
  system_id:    my-model
  commit_ref:   HEAD
  result:       PASS
  duration_ms:  0
  signed:       no (OSS unsigned)
  eval_outcome:      pass

  Artifact written to compliance-artifact.json
```

If an output contained, say, `SSN 123-45-6789` or
`ignore previous instructions`, the result would be `CONTROL_FAIL` with
`failed_controls: EVAL_SAFETY_LEXICAL_V1, EVAL_DATA_LEAKAGE_V1` (exit `1`).

## JSON output for CI

=== "macOS / Linux"
    ```bash
    opencomplai check --output json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check --output json
    ```

The `--output json` flag prints the full `ScanStatusArtifact` to stdout:

```json
{
  "install_id": "a1b2c3d4-...",
  "system_id": "my-model",
  "commit_ref": "HEAD",
  "result": "pass",
  "failed_controls": [],
  "evidence_hashes": [],
  "rationale_hash": "sha256:...",
  "duration_ms": 0,
  "pending_verifications_count": 0,
  "signature": null,
  "eval_summary": null
}
```

`eval_summary` is `null` unless you passed `--sample-set`; `signature` is `null`
unless you passed `--sign`.

## Use in GitHub Actions

```yaml
- name: Opencomplai compliance check
  run: |
    pip install opencomplai
    opencomplai init \
      --system-id "${{ env.MODEL_NAME }}" \
      --intended-purpose "${{ env.USE_CASE }}"
    opencomplai check --scan-mode ci
```

A non-zero exit code automatically fails the CI step.

## Full Docker deployment

For the full platform (Evidence Vault, Documentation Generator, badges, and
service-backed workflows including `TRAP_DETECTED`), see
[Deployment Quickstart](../deployment/quickstart.md).

## Next steps

- CLI reference: [check](../cli/check.md) · [init](../cli/init.md) · [exit codes](../cli/exit-codes.md)
- Deployment guide: [Deployment Quickstart](../deployment/quickstart.md)
- Extending rules: [Adding Rules](../contributing/adding-rules.md)
- Not sure which EU AI Act obligations apply? [EU AI Act Checker](eu-ai-act-checker.md)
- Cross-check your manifest's declared purpose against code signals: [Detect AI in your code](scanner.md)
