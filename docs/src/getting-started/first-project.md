# First Project: CI compliance gate for an AI model

This tutorial walks through adding an Opencomplai compliance gate to an existing AI project in about 30 minutes.

## What you will build

A GitHub Actions workflow that runs `opencomplai check` on every push, fails the build if compliance controls are not met, and uploads the `compliance-artifact.json` for auditors.

## Prerequisites

- Opencomplai installed ([Installation](installation.md))
- An AI project in a GitHub repository
- Python 3.11+

## Step 1: Create the system manifest

In your AI project repository:

=== "macOS / Linux"
    ```bash
    opencomplai init \
      --system-id "my-project" \
      --intended-purpose "describe your model's actual use case here"
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai init --system-id "my-project" --intended-purpose "describe your model's actual use case here"
    ```

This creates `system-manifest.json`. Commit it:

=== "macOS / Linux"
    ```bash
    git add system-manifest.json
    git commit -m "feat: add EU AI Act system manifest"
    ```

=== "Windows (PowerShell)"
    ```powershell
    git add system-manifest.json
    git commit -m "feat: add EU AI Act system manifest"
    ```

## Step 2: Run a local check

=== "macOS / Linux"
    ```bash
    opencomplai check
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check
    ```

`check` prints an `Opencomplai Compliance Check` block ending in `result: PASS`
(or `CONTROL_FAIL` / `POLICY_BLOCK`) and writes `compliance-artifact.json`. When
a control fails, a `failed_controls:` line names the EU AI Act control that
fired (e.g. `EU_AIA_ART6_HIGH_RISK`). To see the per-rule rationale for a use
case, run `opencomplai risk classify --system-id <id> --intended-purpose "<purpose>"`.
The full outcome-by-purpose table is in the [Quick Start](quick-start.md#try-the-other-compliance-outcomes).

## Step 3: Add to GitHub Actions

Create `.github/workflows/compliance.yml`:

```yaml
name: EU AI Act compliance
on: [push, pull_request]

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Opencomplai
        run: pip install opencomplai

      - name: Run compliance check
        run: opencomplai check --scan-mode ci

      - name: Upload compliance artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: compliance-artifact
          path: compliance-artifact.json
```

## Step 4: Verify the gate works

Push a commit. The workflow will run. If all controls pass, the job exits 0. If a control fails, the job exits 1 and blocks the merge.

## Step 5: Review `compliance-artifact.json`

After a successful run, download the artifact from the Actions tab. It contains the full `ScanStatusArtifact` — the machine-readable signed record suitable for auditors:

```json
{
  "install_id": "...",
  "system_id": "my-project",
  "commit_ref": "abc1234",
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

## Next steps

- Explore [Advanced Patterns](../examples/advanced-patterns.md) — batch checks, `answers`, programmatic gating.
- Set up the full Docker deployment: [Deployment Quickstart](../deployment/quickstart.md).
- Extend the rule set: [Adding Rules](../contributing/adding-rules.md).