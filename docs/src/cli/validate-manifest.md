# validate-manifest

Validate a system manifest file against the required schema.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai validate-manifest <manifest_file> [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai validate-manifest <manifest_file> [OPTIONS]
    ```

## Arguments

| Argument | Description |
|---|---|
| `manifest_file` | Path to a `system-manifest.json` file (positional). |

## Options

| Option | Default | Description |
|---|---|---|
| `--output` / `-o` | `human` | Output format: `human` or `json`. |

## Examples

=== "macOS / Linux"
    ```bash
    # Human-readable validation result
    opencomplai validate-manifest system-manifest.json

    # JSON output (returns the validated manifest)
    opencomplai validate-manifest system-manifest.json --output json
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Human-readable validation result
    opencomplai validate-manifest system-manifest.json

    # JSON output (returns the validated manifest)
    opencomplai validate-manifest system-manifest.json --output json
    ```

## Output

**Human (`--output human`):**

```text
Manifest is valid.
  system_id:             my-model
  intended_purpose:      customer support chatbot
  compliance_target:     EU_AI_ACT
  high_risk_presumption: False
```

**JSON (`--output json`):**

```json
{
  "system_id": "my-model",
  "intended_purpose": "customer support chatbot",
  "compliance_target": "EU_AI_ACT",
  "high_risk_presumption": false,
  "commit_ref": "HEAD"
}
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Manifest is valid. |
| 2 | Manifest file not found or schema validation failed. |
