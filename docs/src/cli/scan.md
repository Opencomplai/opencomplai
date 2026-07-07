# `opencomplai scan`

Cross-check your declared `intended_purpose` against AI capability signals detected in the repository.

## Important

- **Declaration is authoritative.** The scanner corroborates your manifest; it never auto-classifies risk.
- **No AI detected is not a compliance verdict.** The CLI reports *"no local AI signals detected"* — not *"compliant."*

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai scan --manifest system-manifest.json --repo-root .
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --manifest system-manifest.json --repo-root .
    ```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--manifest` | `system-manifest.json` | System manifest path |
| `--repo-root` | `.` | Repository root to scan |
| `--commit-ref` | `HEAD` | Commit reference for provenance |
| `--emit-evidence` | on | Append `code_corroboration` ledger event |
| `--enqueue-review` | off | Route major/critical gaps to HITL |
| `--baseline` | — | JSON file with `accepted_categories` |
| `--fail-on` | `none` | CI gating: `none`, `new-major`, `major`, `critical` |
| `--output` | `human` | `human` or `json` |
| `--output-file` / `-f` | — | Write results to `.json` or `.md` file (stdout unchanged) |
| `--ocignore` | repo-root `.ocignore` | Custom scan config path (must be inside `--repo-root`) |
| `--ocignore-bootstrap` / `--no-ocignore-bootstrap` | bootstrap on | Create default `.ocignore` on first scan if missing |
| `--ai-intent` | off | Run local AI intent classification on extracted callsites (requires `opencomplai-ai`) |
| `--ai-model` | configured default | Override the active model for this scan (e.g. `codebert-onnx`, `qwen2.5-coder-1.5b`) |

## AI intent analysis (`--ai-intent`)

`--ai-intent` runs a second pass after signature detection: each extracted callsite is embedded by a local model and classified on three EU AI Act dimensions — `decision_autonomy`, `subject_type`, and `consequential` — producing a per-callsite `eu_obligation` list.

### Install

**ONNX (CPU, no C compiler):**

=== "macOS / Linux"
    ```bash
    pip install opencomplai-ai 'optimum[onnxruntime]'
    opencomplai ai configure --model codebert-onnx --set-default
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai-ai "optimum[onnxruntime]"
    opencomplai ai configure --model codebert-onnx --set-default
    ```

**GGUF (optional, supports larger models):**

=== "macOS / Linux"
    ```bash
    pip install 'opencomplai-ai[deep]'
    opencomplai ai configure --model qwen2.5-coder-1.5b --set-default
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install "opencomplai-ai[deep]"
    opencomplai ai configure --model qwen2.5-coder-1.5b --set-default
    ```

### Usage

=== "macOS / Linux"
    ```bash
    # Use the configured default model
    opencomplai scan --manifest system-manifest.json --repo-root . --ai-intent

    # Override model for this scan only
    opencomplai scan --manifest system-manifest.json --repo-root . \
      --ai-intent --ai-model codebert-onnx
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Use the configured default model
    opencomplai scan --manifest system-manifest.json --repo-root . --ai-intent

    # Override model for this scan only
    opencomplai scan --manifest system-manifest.json --repo-root . --ai-intent --ai-model codebert-onnx
    ```

### Available models

| `--ai-model` value | Size | Runtime | Install extra |
|---|---|---|---|
| `codebert-onnx` | 440 MB | onnxruntime | `optimum[onnxruntime]` |
| `qwen2.5-coder-0.5b` | 400 MB | llama-cpp | `[deep]` |
| `qwen2.5-coder-1.5b` | 1 GB | llama-cpp | `[deep]` |
| `smollm2-1.7b` | 1.1 GB | llama-cpp | `[deep]` |
| `phi-3.5-mini` | 2.2 GB | llama-cpp | `[deep]` |
| `mistral-7b` | 4.1 GB | llama-cpp | `[deep]` |
| `saas` | — | http | — |

### Output

The `AI Intent Analysis` block appears at the end of `--output human`:

```
AI Intent Analysis:
  src/face.py:5  autonomy=display_only  subject=legal_entity  conf=0.9397
  src/face.py:7  autonomy=display_only  subject=legal_entity  conf=0.9378
```

`conf` is the average cosine similarity across all three dimensions. Scores above `0.90` are reliable.

### First run — `codebert-onnx` export

The first scan with `codebert-onnx` exports the PyTorch checkpoint to ONNX and caches it at `~/.cache/opencomplai/models/codebert-base/model.onnx`. The CLI prompts before downloading (~440 MB). Subsequent scans run fully offline from the cache.

See the [scanner guide](../getting-started/scanner.md#local-ai-intent-analysis---ai-intent) for a full walkthrough.

## Opt-in on other commands

=== "macOS / Linux"
    ```bash
    opencomplai init --system-id my-sys --intended-purpose "..." --scan
    opencomplai check --manifest system-manifest.json --scan
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai init --system-id my-sys --intended-purpose "..." --scan
    opencomplai check --manifest system-manifest.json --scan
    ```

`check --scan` does **not** change exit codes unless `--fail-on` is set.

## Example fixtures

See `examples/sample-system/under-declared-*` for deliberately under-declared manifests.
