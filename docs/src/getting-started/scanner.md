# Detect AI in your code — the corroboration scanner

The `opencomplai scan` command cross-checks your manifest's declared
`intended_purpose` against the AI capability signals actually present in the
repository — dependencies, imports, model artifacts, API endpoints.

AI-SDK detection recognizes 22 provider SDKs, including `openai`, `anthropic`,
`google-genai`, `azure-ai-openai`, `cohere`, `mistralai`, `groq`, `together`,
`replicate`, `huggingface_hub`, `fireworks-ai`, `perplexityai`, `ai21`,
`stability-sdk`, `elevenlabs`, `deepgram`, `assemblyai`, `google-cloud-aiplatform`,
and `ibm-watsonx-ai` — this list is pure signature data
(`scanner/data/ai_signals.json`) and grows independently of CLI flags or behavior.

## Two honesty rules

!!! warning "Read these before using the scanner"
    1. **The declaration stays authoritative.** The scanner never auto-classifies
       risk or edits your manifest. It surfaces discrepancies for a human to reconcile.
    2. **"No local AI signals detected" is not a compliance verdict.** It means
       the scanner found nothing locally — not that the system is compliant.

## Quick start

=== "macOS / Linux"
    ```bash
    opencomplai scan --manifest system-manifest.json --repo-root .
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --manifest system-manifest.json --repo-root .
    ```

Point `--repo-root` at the directory that actually contains your model code,
inference imports, and dependencies.

!!! tip "Add or review `.ocignore` before your first scan"
    The CLI creates a default [`.ocignore`](#ocignore) in your repo root the
    first time you run `opencomplai scan` (disable with
    `--no-ocignore-bootstrap`). The default excludes common noise like
    `node_modules/` and `.git/`, but what it includes or excludes changes what
    the scanner actually sees — review and customize it for your repo layout
    before relying on the results. See [`.ocignore` scan configuration](#ocignore)
    below.

## `.ocignore` scan configuration {#ocignore}

The scanner reads a repo-root [`.ocignore`](https://github.com/opencomplai/opencomplai/blob/main/.ocignore)
file for **exclusion patterns** and **inventory limits**. It does **not** read
`.gitignore` at scan time — on first `opencomplai scan`, the CLI can create a
default `.ocignore` and optionally merge non-comment lines from `.gitignore` once.

### Pattern subset (v1)

| Supported | Not supported (v1) |
|-----------|-------------------|
| `fnmatch` globs (`*.pem`, `dist/`) | Negation (`!pattern`) |
| Trailing `/` for directories (`node_modules/`) | `**` recursive globs |
| Basename match (`Makefile` matches any depth) | Anchored paths (`/abs/path`) |

Examples:

| Pattern | Matches |
|---------|---------|
| `node_modules/` | `node_modules/pkg/index.js` |
| `*.pem` | `certs/server.pem` |
| `build` | `build` or `out/build` (basename) |

### Limits (`[limits]` block)

`0` means **no cap** for numeric limits. Template defaults are unlimited.

| Key | `0` / `false` | Non-zero |
|-----|---------------|----------|
| `max_files` | No file-count cap | Stop walk |
| `max_bytes_per_file` | No per-file cap | Skip oversized files |
| `max_total_bytes` | No cumulative cap | Stop walk |
| `skip_binary` | Include binaries | Skip non-model binaries |
| `max_symlink_depth` | Unlimited resolution | Block deeper symlinks |
| `max_notebook_cells` | Parse all cells | Truncate notebook parsing |

CI-safe preset (paste into `.ocignore` — not the default):

```gitignore
[limits]
max_files = 10000
max_bytes_per_file = 2097152
max_total_bytes = 104857600
skip_binary = true
```

Use `--no-ocignore-bootstrap` in CI when `.ocignore` is committed. Use
`--ocignore PATH` for a custom config file (must live inside `--repo-root`).

Progress output summarizes skips, e.g. `673 files inventoried (18 ignored, 5 over limit)`.

## The under-declared fixtures

The repo ships three deliberately under-declared example systems under
`examples/sample-system/`. Each has a manifest that understates the actual
AI capability in the code:

| Fixture | Declares | Scanner detects | Why |
|---|---|---|---|
| `under-declared-chatbot` | `customer support chatbot` | `biometric` | imports `face_recognition` |
| `under-declared-scoring` | `rule-based scoring` | `employment`, `essential_services`, `law_enforcement` | pickled classifier + `rank_applicants()` |
| `under-declared-analytics` | `analytics dashboard` | `employment`, `essential_services`, `law_enforcement` | `chromadb` + `sentence-transformers` + applicant-ranking imports |

Run the chatbot fixture:

=== "macOS / Linux"
    ```bash
    opencomplai scan \
      --manifest examples/sample-system/under-declared-chatbot/system-manifest.json \
      --repo-root examples/sample-system/under-declared-chatbot \
      --no-emit-evidence
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --manifest examples/sample-system/under-declared-chatbot/system-manifest.json --repo-root examples/sample-system/under-declared-chatbot --no-emit-evidence
    ```

Expected output:

```
Code Corroboration Scan
  severity:     major
  declared:     (none)
  detected:     biometric
  discrepancies: biometric
    - requirements.txt:1
    - requirements.txt:2
    - src/face.py:1

  Declaration is authoritative; confirm or update intended_purpose.
```

A folder with no AI signals stays honest:

```
Code Corroboration Scan
  severity:     none
  declared:     (none)
  detected:     (none)
  No local AI signals detected — not a compliance verdict.
```

## Local AI intent analysis (`--ai-intent`)

The `--ai-intent` flag runs an **EU AI Act-focused scan** on top of signature detection. Instead of classifying every callsite in the repository, the scanner applies a **callsite-level AI usage gate** first, then classifies only provably AI-related sites (LLM calls, ML inference, embeddings, model loading, scoring with ML context).

### What you see

Human output is organized as a six-section **EU AI Act Scan** workflow:

1. **AI usage map** — files and functions where AI is actually used, grouped by usage type (`llm_inference`, `ml_inference`, `scoring`, etc.)
2. **Prohibited (Art. 5)** — practices that cannot be lawfully deployed
3. **High-risk (Annex III)** — findings grouped by Annex III area (1–8)
4. **Limited-risk (Art. 50)** — transparency obligations only
5. **Declaration cross-check** — declared vs detected categories and discrepancies
6. **Flag rationale** — one plain-language **WHY** sentence per flagged line, citing the matched signal, regulation article, and gate reason

Framework glue (`APIRouter`, `ASGITransport`, `Depends`, `TestClient`) and other non-AI callsites are **excluded** from this output.

### Scan scope

For production assessments, point `--repo-root` at your deployed service (for example `dashboard-saas/`) rather than the entire monorepo. Add demo paths such as `examples/` to [`.ocignore`](../../.ocignore) so sample fixtures do not affect your system's results. Set `intended_purpose` in `system-manifest.json` to describe **your** system — not a sample credit-scoring manifest.

### Flags

| Flag | Effect |
|---|---|
| `--ai-intent` | Gated EU AI Act scan (default v2 behavior) |
| `--ai-verbose` | Show detailed per-callsite appendix in Section 1 |
| `--ai-deep` | Skip file-level pre-filter; callsite gate still applies |
| `--ai-legacy` | Restore pre-v2 behavior: all callsites + old `AI Intent Analysis` block |

### JSON output

With `--output json`, the report includes an `eu_ai_scan` block:

```json
{
  "eu_ai_scan": {
    "capabilities": [{"location": "src/app.py:1", "function": "openai", "usage_type": "llm_inference", "file": "src/app.py"}],
    "prohibited": [],
    "high_risk": [{"location": "src/score.py:42", "function": "predict_proba", "risk_tier": "high_risk", "rationale": {"summary": "Matched Annex III area 5...", "matched_signals": ["predict_proba"], "regulation_ref": "Art. 6(2), Annex III pt.5(b)"}}],
    "limited_risk": [],
    "gated_callsite_count": 3,
    "regulatory_finding_count": 0
  },
  "evidence": []
}
```

In `--ai-intent` mode (without `--ai-legacy`), `evidence` contains **regulatory intent findings only** — not lexical framework noise. Minimal-tier AI usage appears in `eu_ai_scan.capabilities` but not in `evidence`.

### Three classification dimensions

For each gated callsite, the intent classifier evaluates three dimensions directly relevant to the EU AI Act:

| Dimension | Labels | EU AI Act relevance |
|---|---|---|
| `decision_autonomy` | `autonomous` / `advisory` / `human_in_loop` / `display_only` | Article 14 — oversight obligations scale with how much the AI output drives the final decision |
| `subject_type` | `natural_person` / `legal_entity` / `system` | Determines whether Articles 13–15 apply |
| `consequential` | `yes` / `no` | Whether the AI output causes a real-world effect on rights, access, or benefits |

These three dimensions are combined into a per-callsite `eu_obligation` list. For example, `autonomous` + `natural_person` + `yes` maps to `["Art.6(2)+Annex III", "technical dossier required", "conformity assessment", "EU DB registration"]` (HIGH_RISK). `display_only` + `legal_entity` + `yes` maps to `["Art.52 disclosure if user-facing"]` (MINIMAL_RISK).

### Prerequisites

**ONNX path — CPU only, no C compiler required:**

=== "macOS / Linux"
    ```bash
    pip install opencomplai-ai 'optimum[onnxruntime]'
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai-ai "optimum[onnxruntime]"
    ```

**GGUF path — optional, supports larger models:**

=== "macOS / Linux"
    ```bash
    pip install 'opencomplai-ai[deep]'   # adds llama-cpp-python
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install "opencomplai-ai[deep]"   # adds llama-cpp-python
    ```

### Available models

| Model ID | Size | License | Runtime | Install extra |
|---|---|---|---|---|
| `codebert-onnx` | 440 MB | MIT | onnxruntime | `optimum[onnxruntime]` |
| `qwen2.5-coder-0.5b` | 400 MB | Apache-2.0 | llama-cpp | `[deep]` |
| `qwen2.5-coder-1.5b` | 1 GB | Apache-2.0 | llama-cpp | `[deep]` |
| `smollm2-1.7b` | 1.1 GB | Apache-2.0 | llama-cpp | `[deep]` |
| `phi-3.5-mini` | 2.2 GB | MIT | llama-cpp | `[deep]` |
| `mistral-7b` | 4.1 GB | Apache-2.0 | llama-cpp | `[deep]` |
| `saas` | — | — | http | — |

The default model is `qwen2.5-coder-1.5b` (GGUF, requires `[deep]`). To use `codebert-onnx` (no llama-cpp, runs on any CPU):

=== "macOS / Linux"
    ```bash
    opencomplai ai configure --model codebert-onnx --set-default
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai ai configure --model codebert-onnx --set-default
    ```

### First run — ONNX export for `codebert-onnx`

The first `--ai-intent` scan with `codebert-onnx` exports the model from the official PyTorch checkpoint (`microsoft/codebert-base`) and caches the ONNX graph locally. The CLI prompts once before downloading:

```
Preparing CodeBERT-base (ONNX) (~440 MB)
  Source: microsoft/codebert-base (PyTorch checkpoint)
  Export: ONNX -> ~/.cache/opencomplai/models/codebert-base/model.onnx
  This runs once; the exported model is cached for future scans.

Download and export now? [Y/n]:
```

Export takes 1–3 minutes on a typical laptop. All subsequent scans read `model.onnx` from cache with no network access and no prompt.

### Running the under-declared fixtures with `--ai-intent`

=== "macOS / Linux"
    ```bash
    # Chatbot fixture
    opencomplai scan \
      --manifest examples/sample-system/under-declared-chatbot/system-manifest.json \
      --repo-root examples/sample-system/under-declared-chatbot \
      --ai-intent --no-emit-evidence

    # Scoring fixture
    opencomplai scan \
      --manifest examples/sample-system/under-declared-scoring/system-manifest.json \
      --repo-root examples/sample-system/under-declared-scoring \
      --ai-intent --no-emit-evidence

    # Analytics fixture
    opencomplai scan \
      --manifest examples/sample-system/under-declared-analytics/system-manifest.json \
      --repo-root examples/sample-system/under-declared-analytics \
      --ai-intent --no-emit-evidence
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Chatbot fixture
    opencomplai scan --manifest examples/sample-system/under-declared-chatbot/system-manifest.json --repo-root examples/sample-system/under-declared-chatbot --ai-intent --no-emit-evidence

    # Scoring fixture
    opencomplai scan --manifest examples/sample-system/under-declared-scoring/system-manifest.json --repo-root examples/sample-system/under-declared-scoring --ai-intent --no-emit-evidence

    # Analytics fixture
    opencomplai scan --manifest examples/sample-system/under-declared-analytics/system-manifest.json --repo-root examples/sample-system/under-declared-analytics --ai-intent --no-emit-evidence
    ```

The `EU AI Act Scan` block appears at the end of the human-readable output when `--ai-intent` is set (without `--ai-legacy`). Example:

```
EU AI Act Scan
────────────────────────────────────────
1. AI usage map (3 sites in 1 files)
     llm_inference      1 files   openai, chat

2. Prohibited (Art. 5) — 0 findings

3. High-risk (Annex III) — 1 findings
     5 Essential services           1
     src/app.py:18  predict_proba  5 Essential services

4. Limited-risk (Art. 50) — 0 findings

5. Declaration cross-check
     declared:      essential_services
     detected:      essential_services
     discrepancies: (none)

6. Flag rationale — 1 flagged lines
     src/app.py:18  predict_proba
       WHY: Matched Annex III area 5 code signal "predict_proba" (Creditworthiness assessment and credit scoring); high-risk obligations apply under Art. 6(2), Annex III pt.5(b). Gate: inference_verb_with_file_context.
```

Use `--ai-legacy` to restore the previous `AI Intent Analysis` block that listed every annotated callsite.

Expected annotation counts across the three fixtures:

| Fixture | Callsites annotated | Typical `conf` |
|---|---|---|
| `under-declared-chatbot` | ~2 | > 0.93 |
| `under-declared-scoring` | ~10 | > 0.90 |
| `under-declared-analytics` | ~6 | > 0.90 |

The scoring fixture produces the highest annotation count because `rank_applicants`, `load_model`, and multiple feature-engineering callsites each generate an annotation. The analytics fixture's `chromadb` and `sentence-transformers` imports account for most of its annotations.

### Confidence scores

`conf` is the average cosine similarity between the callsite's embedding and the winning label pattern, averaged across all three dimensions. Scores above `0.90` are reliable. Scores between `0.70` and `0.90` are plausible but worth human review before acting on the `eu_obligation` output.

### "no callsites annotated"

```
AI Intent Analysis:
  no callsites annotated
```

This is the expected output for repositories that contain no AI-related code — the feature extractor found no callsites or imports the intent detector could classify. It is not an error.

## Opt-in on `init` and `check`

The scanner is **opt-in** and never changes exit codes unless you set `--fail-on`:

=== "macOS / Linux"
    ```bash
    # Run scanner after writing the manifest
    opencomplai init --system-id my-sys --intended-purpose "..." --scan

    # Corroborate during the compliance gate
    opencomplai check --scan

    # CI: fail the gate only when NEW major discrepancies appear
    opencomplai check --scan --fail-on new-major
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Run scanner after writing the manifest
    opencomplai init --system-id my-sys --intended-purpose "..." --scan

    # Corroborate during the compliance gate
    opencomplai check --scan

    # CI: fail the gate only when NEW major discrepancies appear
    opencomplai check --scan --fail-on new-major
    ```

## Severity levels

| Severity | Meaning |
|---|---|
| `none` | No discrepancy between declared and detected |
| `minor` | Detected capability plausibly covered by declaration |
| `major` | Clear gap — declaration likely needs updating |
| `critical` | High-confidence undeclared high-risk capability |

## `--fail-on` CI gating

| Value | Effect |
|---|---|
| `none` (default) | Always exits `0` — advisory only |
| `new-major` | Exits `1` only when a **new** major/critical gap appears vs. baseline |
| `major` | Exits `1` on any major or critical gap |
| `critical` | Exits `1` on critical gaps only |

Use a baseline file to suppress already-accepted gaps:

=== "macOS / Linux"
    ```bash
    # Accept current gaps into a baseline
    echo '{"accepted_categories": ["biometric"]}' > scan-baseline.json

    # Future runs only fail on NEW gaps not in the baseline
    opencomplai check --scan --fail-on new-major --baseline scan-baseline.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Accept current gaps into a baseline
    '{"accepted_categories": ["biometric"]}' | Set-Content scan-baseline.json

    # Future runs only fail on NEW gaps not in the baseline
    opencomplai check --scan --fail-on new-major --baseline scan-baseline.json
    ```

## MCP / agent signals

**What:** the scanner can flag MCP server imports/config and multi-agent patterns
(`DET_AGENTS_MCP_V1` → `mcp_server` / `agent_framework`).

**When:** repos that use Model Context Protocol tools or multi-agent frameworks.

**Don't:** treat a detection as “high-risk under the Act.” It is a corroboration
signal for Art. 14-style oversight discussions — not a legal classification.

## Service-backed mode (Docker stack)

When `OPENCOMPLAI_API_URL` is set, `scan` writes a `code_corroboration`
ledger event to the evidence vault and can route major/critical gaps to the
HITL review queue:

=== "macOS / Linux"
    ```bash
    OPENCOMPLAI_API_URL=http://localhost:8080 \
      opencomplai scan --manifest system-manifest.json --repo-root . --enqueue-review
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"
    opencomplai scan --manifest system-manifest.json --repo-root . --enqueue-review
    ```

## Further reading

- [scan CLI reference](../cli/scan.md) — all flags
- [Customer workflow §2b](../guides/customer-workflow.md) — where scan fits in the full compliance lifecycle
- **EU AI Act regulatory workflow** — `opencomplai scan --ai-intent` implements Steps 3–4 of the compliance workflow (prohibited practices screen and Annex III risk tier determination) as a static code approximation.
