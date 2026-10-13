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
| `--emit-evidence` / `--no-emit-evidence` | on | Append the `code_corroboration` ledger event, or skip it with `--no-emit-evidence`. `--quick` always skips it |
| `--enqueue-review` / `--no-enqueue-review` | off | Route major/critical gaps to HITL, or leave them out with `--no-enqueue-review`. `--quick` always leaves them out |
| `--strict` | off | Exit `2` on unknown top-level keys in the manifest instead of warning and ignoring them. No effect with `--quick`, which loads no manifest |
| `--ai-deep` | off | With `--ai-intent` or `--propose`: run the intent analysis on every callsite in the repository. By default only callsites in files that already have a lexical finding are analysed, which is faster. No effect with `--ai-legacy`, which already analyses every callsite |
| `--ai-verbose` | off | With `--ai-intent`: in the human report, list every finding instead of the first 10 per list (the callsite list is capped at 50) and add the matched signals, regulation reference and gate reason to each flag rationale. No effect on `--output json` |
| `--baseline` | — | JSON file with `accepted_categories` |
| `--fail-on` | `none` | CI gating: `none`, `new-major`, `major`, `critical` |
| `--output` | `human` | `human` or `json` |
| `--output-file` / `-f` | — | Write results to `.json` or `.md` file (stdout unchanged) |
| `--ocignore` | repo-root `.ocignore` | Custom scan config path (must be inside `--repo-root`) |
| `--ocignore-bootstrap` / `--no-ocignore-bootstrap` | bootstrap on | Create default `.ocignore` on first scan if missing |
| `--ai-intent` | off | Run local AI intent classification on extracted callsites (requires `opencomplai-ai`). It uses the configured model (`qwen2.5-coder-1.5b` unless changed), which needs the `[deep]` extra by default; on a base install the scan prints that AI intent was skipped. `--propose` uses the deterministic `codebert-onnx` backend instead |
| `--ai-model` | configured default (`codebert-onnx` under `--propose`) | Override the active model for this scan (e.g. `codebert-onnx`, `qwen2.5-coder-1.5b`) |
| `--framework-detectors` | off | Opt-in AST-level detection of orchestration-framework object construction + invocation (see below) |
| `--quick` | off | Zero-config discovery scan — no manifest, never gates CI, never emits evidence (see below) |
| `--propose` | off | Write `classification-proposal.json`: a classification the scan suggests from your code, for you to confirm with [`accept --proposal`](accept.md#confirming-a-classification-proposal). Turns on the intent analysis with the deterministic `codebert-onnx` backend unless `--ai-model` is given; needs the optional AI plugin (see below) |
| `--sarif-output` | — | Write scan evidence as a SARIF 2.1.0 document, for GitHub code scanning / GHAS upload (see [SARIF integration](../guides/sarif-integration.md)) |

## Zero-config discovery (`--quick`)

`opencomplai scan --quick` is a discovery-only scan meant as the very first command a
new user runs against a repo — before `init`, before a manifest exists at all:

=== "macOS / Linux"
    ```bash
    opencomplai scan --quick
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --quick
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

## Suggesting a classification (`--propose`)

`opencomplai scan --propose` suggests a classification from your code; you confirm it.
It turns on the intent analysis (as `--ai-intent` does) with the deterministic
`codebert-onnx` backend, ignoring the configured default model; `--ai-model` still
selects another model. It groups the call-site findings by Annex III area, and writes
`classification-proposal.json` into the repository root. The file names the most
supported area (or `none`), a confidence label that is a count of supporting call
sites rather than a probability, the supporting and minority evidence with file
and line, and any prohibited-practice signals. It also records `ai_backend` and `ai_model_id`
(optional; older proposals lack them and still confirm), and the command prints
`Intent backend: <model> (<backend>)` after the path.

=== "macOS / Linux"
    ```bash
    pip install opencomplai-ai
    opencomplai scan --manifest system-manifest.json --repo-root . --propose
    opencomplai accept --accepted-by "you@example.com" --proposal classification-proposal.json
    # opt into an LLM backend instead of the default (needs the [deep] extra):
    opencomplai scan --manifest system-manifest.json --repo-root . --propose --ai-model qwen2.5-coder-1.5b
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai-ai
    opencomplai scan --manifest system-manifest.json --repo-root . --propose
    opencomplai accept --accepted-by "you@example.com" --proposal classification-proposal.json
    # opt into an LLM backend instead of the default (needs the [deep] extra):
    opencomplai scan --manifest system-manifest.json --repo-root . --propose --ai-model qwen2.5-coder-1.5b
    ```

The default backend is `codebert-onnx`. `--ai-model` with another id from
[the model table](#available-models) opts into that backend instead.

After a code or manifest change the proposal is `stale`: `check` warns once on stderr
and ignores it. Run `scan --propose`, then `accept --proposal`, to refresh it.

- **It needs the optional AI plugin.** `--propose` needs `opencomplai-ai`
  (`pip install opencomplai-ai`); the base install is enough for the default backend
  and the `[deep]` extra is only for GGUF models. Without it the command prints the install hint and
  exits `1`. It also exits `2`, writing nothing, with `--quick` or `--ai-legacy`, or
  when the intent analysis did not run.
- **The declared purpose stays the source.** The proposal is a suggestion, not a legal
  determination, and the file says so. It stays `unconfirmed` until a person confirms
  it, and the confirmation records only that the person confirmed it as shown.
- **`check --scan` reads it only after a person confirms it.** A confirmed proposal that
  names an Annex III area your declared purpose does not cover adds a
  `confirmed_proposal:<area>` row, counted as `major` under `--fail-on` (see
  [`check`](check.md)). An absent, unconfirmed, edited or stale proposal changes nothing.
- **Its exit code can differ from a plain scan.** `--propose` turns on the intent
  analysis, so under `--fail-on` the exit code can differ from a plain scan of the
  same repository. A scan that fails `--fail-on` still writes the file.
- **The file does not move the input digest.** A later scan still reads
  `classification-proposal.json`, but the files the tool writes itself (the proposal,
  the confirmation record under `.opencomplai/acceptances/` and `.ocignore`, and any
  file named `scan-report.json`, `eval-report.json` or `compliance-artifact.json` at any
  depth) are left out of the digest, so writing them does not change it. A report file
  you write inside the scanned tree with `--sarif-output` or `--output-file` is part of
  the digest. Write it outside the repository or list it in `.ocignore`, or a confirmed
  proposal reads stale on the next run. The proposal also records a
  digest of the scanned code (`scan_tree_sha256`). When the code or the manifest changes
  after that, `check` treats the proposal as stale and ignores it; run `scan --propose`
  and `accept --proposal` again to refresh it.

Intent snippets are read relative to `--repo-root`, not the working directory. A snippet that
cannot be read adds a `snippet_unreadable` warning to the scan report (shown with
`--output json`) instead of being skipped silently.

## Candidates (leads for a person)

With `--ai-intent`, the scan also lists **candidates**: an AI library that production code
imports but that yields no Annex III signal. They are reported apart from the findings, under
`eu_ai_scan.candidates` in the JSON and in a separate block of the terminal report headed
"Candidates (leads for a person, not findings)". Each one names the library, the file and line
of the import, and the reason `imported_not_classified`.

- **A candidate is a lead, not a finding.** It asks a person to check whether the library is
  used for something that needs a classification. Nothing in the scan treats it as evidence.
- **It moves nothing.** A candidate changes no verdict, no exit code and no count in the
  classification proposal, and it is not part of the gate.
- **It carries no accuracy figure.** Candidates are excluded from precision and recall. The
  [benchmark page](../concepts/annex-iii-benchmark.md#candidates-leads-not-findings) lists the
  measured counts on its synthetic programs and makes no claim beyond that table.

The fields and the rules are described in [Candidate tier](../concepts/candidate-tier.md).

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

`--ai-intent` runs a second pass after signature detection: each extracted callsite is classified by the selected backend on three EU AI Act dimensions — `decision_autonomy`, `subject_type`, and `consequential` — producing a per-callsite `eu_obligation` list.

There are three backends. `codebert-onnx` is a deterministic code-signal matcher: it runs on the base install of `opencomplai-ai`, needs no download, no ONNX Runtime and no `optimum`, and matches each callsite against the built-in Annex III, prohibited-practice and limited-risk signal lists. The GGUF models (`qwen2.5-coder-*`, `smollm2-1.7b`, `phi-3.5-mini`, `mistral-7b`) are real local LLM inference; they need the `[deep]` extra and a one-time model download. `saas` is the third, opt-in cloud backend: it runs no model locally and, once you have consented to data egress and set `OPENCOMPLAI_API_KEY`, sends redacted code snippets to the hosted intent API. The `codebert-onnx` id is kept for compatibility with existing configs and annotations; no CodeBERT model is loaded.

### Install

**Deterministic matcher (base install, no download):**

=== "macOS / Linux"
    ```bash
    pip install opencomplai-ai
    opencomplai ai configure --model codebert-onnx --set-default
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai-ai
    opencomplai ai configure --model codebert-onnx --set-default
    ```

**GGUF (optional, local LLM inference with larger models):**

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
| `codebert-onnx` | no download | deterministic matcher | base install |
| `qwen2.5-coder-0.5b` | 400 MB | llama-cpp | `[deep]` |
| `qwen2.5-coder-1.5b` | 1 GB | llama-cpp | `[deep]` |
| `smollm2-1.7b` | 1.1 GB | llama-cpp | `[deep]` |
| `phi-3.5-mini` | 2.2 GB | llama-cpp | `[deep]` |
| `mistral-7b` | 4.1 GB | llama-cpp | `[deep]` |
| `saas` | — | http | — |

### Output

With an AI backend selected, the human report adds the EU AI Act sections (AI usage map, Prohibited, High-risk, Limited-risk, flag rationale). Real output from `--ai-intent --ai-model codebert-onnx` on the `tests/fixtures/eu_ai_scan` fixture (the final flag-rationale section is omitted here):

```
Code Corroboration Scan
  severity:     none
  declared:     (none)
  detected:     (none)
  discrepancies: (none)

EU AI Act Scan
  ────────────────────────────────────────

  1. AI usage map (6 sites in 2 files)
     llm_inference        2 files   create, gemini_api, load, openai
     scoring              1 files   predict_proba

  2. Prohibited (Art. 5) — 0 findings

  3. High-risk (Annex III) — 0 findings

  4. Limited-risk (Art. 50) — 2 findings
     src/app/api/oracle/route.ts:4  gemini_api
       Inform users they are interacting with an AI system at first interaction
     src/app/api/oracle/route.ts:10  gemini_api
       Inform users they are interacting with an AI system at first interaction

  5. Declaration cross-check
     declared:      (none)
     detected:        (none)
     discrepancies: (none)
```

Each annotation also carries a `confidence` value, printed per callsite by `--ai-legacy`. It is not a similarity score or a calibrated probability: the deterministic matcher assigns fixed values by match type (`0.5` to `0.8`), and the GGUF models report a fixed `0.75`. Treat it as a label for how the callsite was matched, not as a measure of reliability.

See the [scanner guide](../getting-started/scanner.md#local-ai-intent-analysis-ai-intent) for a full walkthrough.

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
