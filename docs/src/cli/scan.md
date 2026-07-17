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
| `--framework-detectors` | off | Opt-in AST-level detection of orchestration-framework object construction + invocation (see below) |
| `--quick` | off | Zero-config discovery scan — no manifest, never gates CI, never emits evidence (see below) |
| `--sarif-output` | — | Write scan evidence as a SARIF 2.1.0 document, for GitHub code scanning / GHAS upload (see [SARIF integration](../guides/sarif-integration.md)) |

## Zero-config discovery (`--quick`)

`opencomplai scan --quick` is a discovery-only scan meant as the very first command a
new user runs against a repo — before `init`, before a manifest exists at all:

=== "macOS / Linux"
    ```bash
    opencomplai scan --quick .
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --quick .
    ```

`--quick` forces `--fail-on none`, disables evidence emission (`--emit-evidence`),
disables HITL review enqueueing (`--enqueue-review`), and **always exits `0`** — it is
discovery, not a compliance verdict, and it never writes `compliance-artifact.json`.
Contrast this explicitly with `opencomplai check`: `scan --quick` cannot fail your
build even if it finds AI signals everywhere, because there is no manifest to check
findings against yet.

Output ends with a suggested next step based on what it found:

```text
Discovery only — not a compliance verdict. No manifest was loaded and no CI gate was evaluated.

Detected categories: openai, vector_embedding

Suggested next step:
  opencomplai init --system-id <your-system-id> --intended-purpose "openai, vector_embedding"
```

If nothing is detected, it prints a note that `init` is still available whenever you
have a system to declare — `--quick` finding nothing is not itself a pass/fail signal.

## Framework object detection (`--framework-detectors`)

`--framework-detectors` is an opt-in AST-level detector that distinguishes **importing**
an orchestration library from **constructing and invoking** one of its runtime objects —
a materially stronger signal than the pre-existing lexical import scan, which fires on
any `import langchain` regardless of whether the code actually builds an agent.

=== "macOS / Linux"
    ```bash
    opencomplai scan --manifest system-manifest.json --repo-root . --framework-detectors
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --manifest system-manifest.json --repo-root . --framework-detectors
    ```

### What it recognizes

The detector (`DET_FRAMEWORK_AST_V1`) fires when code instantiates one of these classes
**and** invokes it — not on a bare import:

| Library | Recognized classes |
|---|---|
| LangChain | `AgentExecutor`, `Chain`, `LLMChain`, `ConversationChain`, `SequentialChain` |
| CrewAI | `Crew`, `Agent`, `Task` |
| AutoGen | `ConversableAgent`, `AssistantAgent`, `UserProxyAgent`, `GroupChat` |
| LangGraph | `StateGraph`, `MessageGraph` |

Evidence is tagged with the `SignalCategory.AGENT_FRAMEWORK` category. Confidence is
`0.9` when the object is constructed in a production-scoped code path, `0.5` for
non-prod scope (e.g. tests/examples) — reachability is reported as
`REACHABLE_ENTRYPOINT` or `IMPORT_ONLY` accordingly.

### Known v1 limitation

The detector's scope is a single function/module — it does not currently track an
object that is constructed in one function and passed as an argument into another
function for invocation. If your orchestration setup builds the agent/chain object in
one place and calls it in another, this detector may miss the invocation half of the
signal (the lexical import-based detector still catches the library usage as a fallback
signal in that case).

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

## Hostile-repo defaults (fail-closed)

**What:** the scanner refuses symlinks by default, applies numeric size/file caps,
and surfaces incomplete-scan conditions as `scan_errors`.

**When:** every `opencomplai scan` (including `--quick`).

**Don't:** set `max_symlink_depth = 0` expecting “refuse” — in OpenComplAI, `0`
still means unlimited when links are allowed. Use `allow_symlinks = false`
(default) instead.

| Limit | Default | Notes |
|-------|---------|-------|
| `max_files` | `20000` | `0` = unlimited (explicit override) |
| `max_bytes_per_file` | `1048576` (1 MiB) | Oversized files are skipped |
| `max_total_bytes` | `209715200` (200 MiB) | Caps total inventory |
| `allow_symlinks` | `false` | Opt in via `.ocignore` if your monorepo requires links |

When `--fail-on` is anything other than `none`, non-empty `scan_errors` fail the
scan (hostile / incomplete inventory is not a silent pass).

### JSON envelope (not the signed artifact)

`opencomplai scan --output json` wraps the report in a versioned envelope
(`schema_version`, disclaimer, `scan_errors`, `payload`). That envelope is
**not** the signed `ScanStatusArtifact` from `opencomplai check`. Auditors
should treat them as different documents.

## Example fixtures

See `examples/sample-system/under-declared-*` for deliberately under-declared manifests.
