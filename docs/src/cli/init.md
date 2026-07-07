# init

Create a system manifest and set up the local signing keypair.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai init --system-id <id> --intended-purpose <purpose> [OPTIONS]
    opencomplai init --interactive [--skip-checker] [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai init --system-id <id> --intended-purpose <purpose> [OPTIONS]
    opencomplai init --interactive [--skip-checker] [OPTIONS]
    ```

## Options

| Option | Default | Description |
|---|---|---|
| `--system-id` | *(required unless `--interactive`)* | Unique identifier for the AI system. |
| `--intended-purpose` | *(required unless `--interactive`)* | Primary intended purpose — maps to EU AI Act Annex III categories. |
| `--interactive` | `False` | Run the EU AI Act applicability checker wizard, then prompt for manifest fields. |
| `--skip-checker` | `False` | With `--interactive`, skip the checker wizard. |
| `--compliance-target` | `EU_AI_ACT` | Compliance framework target. |
| `--high-risk-presumption` / `--no-high-risk-presumption` | `False` | Set to `True` if the provider presumes the system is high-risk pending classification. |
| `--training-data-description` | *(none)* | Annex IV §2 free-text training-data summary. **Required for HIGH-risk systems.** |
| `--model-architecture` | *(none)* | Annex IV §2 free-text architecture description. **Required for HIGH-risk systems.** |
| `--monitoring-approach` | *(none)* | Annex IV §3 production monitoring summary. |
| `--incident-response-procedure` | *(none)* | Annex IV §3 incident-response pointer or summary. |
| `--section-extras-file` | *(none)* | Path to a JSON file with structured Section 2/3 inputs (`performance_metrics`, `known_limitations`, `human_oversight_measures`) merged into the manifest. |
| `--output` / `-o` | `system-manifest.json` | Output path for the manifest file. |

## Examples

=== "macOS / Linux"
    ```bash
    # Interactive onboarding with EU AI Act checker
    opencomplai init --interactive

    # Flag-based init
    opencomplai init \
      --system-id "credit-scoring-v2" \
      --intended-purpose "automated credit scoring for retail lending" \
      --high-risk-presumption
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Interactive onboarding with EU AI Act checker
    opencomplai init --interactive

    # Flag-based init
    opencomplai init --system-id "credit-scoring-v2" --intended-purpose "automated credit scoring for retail lending" --high-risk-presumption
    ```

## What it does

1. On first run, generates an Ed25519 signing keypair in `~/.opencomplai/` and writes a config file (`~/.opencomplai/config.yaml`) containing the `install_id` and the gateway URL.
2. Writes a `SystemManifest` JSON to `--output` (default `system-manifest.json`).

## Output format (`system-manifest.json`)

`init` always writes the full `SystemManifest`, including the optional Annex IV
Section 2/3 fields (with `null`/empty defaults when not supplied):

```json
{
  "system_id": "credit-scoring-v2",
  "intended_purpose": "automated credit scoring for retail lending",
  "compliance_target": "EU_AI_ACT",
  "high_risk_presumption": true,
  "commit_ref": "HEAD",
  "training_data_description": null,
  "model_architecture": null,
  "performance_metrics": {},
  "known_limitations": [],
  "human_oversight_measures": [],
  "monitoring_approach": null,
  "incident_response_procedure": null,
  "operator_role": "deployer",
  "checker_session": {
    "checker_version": "checker-2025-07-28",
    "session_id": "uuid",
    "completed_at": "2026-06-09T12:00:00+00:00",
    "report_json_path": "./eu-ai-act-result.json"
  }
}
```

When present, `checker_session` records an EU AI Act applicability checker run. See [checker](checker.md).

## Next step

Run `opencomplai check` to assess compliance using the manifest.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Manifest written successfully. |
| 2 | Invalid input — bad `--section-extras-file` JSON, or manifest field validation failed. |
