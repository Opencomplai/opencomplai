# `opencomplai eval`

Run the safety, bias, data-leakage, adversarial, and calibration pipeline evaluators
against an `EvalSampleSet` directly, without going through `opencomplai check`.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai eval --manifest system-manifest.json --sample-set eval-set.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai eval --manifest system-manifest.json --sample-set eval-set.json
    ```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--manifest` / `-m` | `system-manifest.json` | System manifest path |
| `--sample-set` | *(required)* | Path to an `EvalSampleSet` JSON |
| `--commit-ref` | `HEAD` | Commit reference for provenance |
| `--output` / `-o` | `human` | `human` or `json` |
| `--provider` | *(none)* | Opt-in: call a live model provider for each prompt (see below) |
| `--model` | *(none)* | Model name to request from `--provider` — required when `--provider` is set |
| `--provider-api-key-env` | `OPENCOMPLAI_PROVIDER_API_KEY` | Environment variable holding the provider API key |
| `--suite` | *(none)* | Opt-in COMPL-AI bridge (`compl-ai`) — see below |
| `--tasks` | curated pin | Comma-separated tasks for `--suite` |
| `--log-dir` | *(none)* | Local Inspect log directory for `--suite` |

See [Evaluators](../concepts/evaluators.md) for what each local evaluator measures and
which are opt-in vs. always-on.

---

## Multi-provider eval (`--provider`)

`--provider` adds an optional **live-model** evaluation pass alongside the local,
deterministic evaluators — useful when you want a real model's completions scored, not
just pre-recorded outputs in your sample set.

=== "macOS / Linux"
    ```bash
    export OPENCOMPLAI_PROVIDER_API_KEY=sk-...
    opencomplai eval \
      --manifest system-manifest.json \
      --sample-set eval-set.json \
      --provider openai \
      --model gpt-4o-mini
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_PROVIDER_API_KEY = "sk-..."
    opencomplai eval --manifest system-manifest.json --sample-set eval-set.json --provider openai --model gpt-4o-mini
    ```

!!! warning "Opt-in and non-deterministic — read this before using it"
    The local evaluators (safety, bias, leakage, adversarial, calibration) always run
    first and are fully deterministic. `--provider` is a separate, explicitly opt-in
    pass that calls a real model over the network — its output is inherently
    non-deterministic and **never affects `opencomplai check`'s exit code contract**.
    This code path is not imported by `check` at all; it is only reachable through
    `opencomplai eval --provider`.

Every provider-backed result is tagged `"deterministic": false` in its output so it can
never be mistaken for the local evaluator suite's results:

```json
{
  "provider": "openai",
  "model": "gpt-4o-mini",
  "deterministic": false,
  "note": "Live model-provider call — non-deterministic, network-dependent, opt-in only.",
  "completions": [
    { "prompt": "...", "completion": "..." }
  ]
}
```

### Required environment variable

The API key is read from the environment variable named by `--provider-api-key-env`
(default `OPENCOMPLAI_PROVIDER_API_KEY`) — never passed as a CLI argument. Use a
different variable name per provider/project if you need to keep credentials separate:

```bash
opencomplai eval --sample-set eval-set.json --provider openai --model gpt-4o-mini \
  --provider-api-key-env MY_OPENAI_KEY
```

### Supported providers

| `--provider` value | Endpoint shape |
|---|---|
| `openai` | OpenAI-compatible `/v1/chat/completions` |
| `openai_compatible` | Any self-hosted/vLLM/compatible deployment implementing the same `/v1/chat/completions` shape |

---

## COMPL-AI benchmark suite (`--suite compl-ai`)

**What it does:** runs a small, curated set of COMPL-AI / Inspect benchmarks
(`strong_reject`, `bbq`, `bigbench_calibration`) and maps scores into OpenComplAI
`EvaluatorResult` records.

**When to use it:** you want empirical model-behavior evidence next to your
local lexical evaluators — for example GPAI safety/bias/calibration spot-checks.

**Don't:** expect this to block `opencomplai check`. The bridge is opt-in,
non-deterministic, and `gate_on_bridge` stays **false**. Release gates stay on
the signed `compliance-artifact.json` path.

### Install

```bash
pip install 'opencomplai-core[compl-ai-bridge]'
# or: pip install 'opencomplai[compl-ai-bridge]'
```

Inspect model strings follow the Inspect docs (for example `openai/gpt-4o-mini`).
Set the provider API key in the environment Inspect expects (often
`OPENAI_API_KEY`).

### Example

```bash
opencomplai eval --suite compl-ai --model openai/gpt-4o-mini --log-dir .opencomplai/eval-logs
```

Optional: `--tasks strong_reject,bbq` to run a subset of the curated pin.

### Inspect model strings (not an OpenComplAI provider zoo)

Prefer Inspect's built-in model routing rather than OpenComplAI-specific clients:

| Example | Notes |
|---|---|
| `openai/gpt-4o-mini` | OpenAI API / compatible |
| `anthropic/claude-3-5-sonnet-latest` | Anthropic (Inspect) |
| `hf/...` / `vllm/...` / `ollama/...` | Local or self-hosted via Inspect |

The thin `--provider openai` path remains for sample-set live completions only.

This bridge is never imported by `opencomplai check`.
