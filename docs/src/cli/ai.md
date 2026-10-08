# ai

Choose and inspect the backend used by `opencomplai scan --ai-intent`. The
group is part of the optional `opencomplai-ai` plugin; for what the intent pass
does, see the [AI intent analysis](scan.md#ai-intent-analysis---ai-intent)
section of `scan`.

**What:** two subcommands, `ai configure` to save the active model and
`ai status` to show it.

**Requires:** the plugin. Without it both subcommands print an install hint and
exit `1`.

=== "macOS / Linux"
    ```bash
    pip install opencomplai-ai
    pip install 'opencomplai-ai[deep]'   # only for the GGUF models
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai-ai
    pip install "opencomplai-ai[deep]"
    ```

## Models

| Model id | Runtime | License | Size | Needs |
|---|---|---|---|---|
| `codebert-onnx` | deterministic | AGPL-3.0-only | none | base install |
| `qwen2.5-coder-0.5b` | llama-cpp | Apache-2.0 | ~400 MB | `[deep]` and a one-time download |
| `qwen2.5-coder-1.5b` (default) | llama-cpp | Apache-2.0 | ~1000 MB | `[deep]` and a one-time download |
| `smollm2-1.7b` | llama-cpp | Apache-2.0 | ~1100 MB | `[deep]` and a one-time download |
| `phi-3.5-mini` | llama-cpp | MIT | ~2200 MB | `[deep]` and a one-time download |
| `mistral-7b` | llama-cpp | Apache-2.0 | ~4100 MB | `[deep]` and a one-time download |
| `saas` | http | none listed | none | consent to data egress |

`codebert-onnx` is a deterministic code-signal matcher. It loads no model,
creates no ONNX Runtime session and has no download: the id is kept only
because existing configs and annotations use it. It matches each callsite
against the built-in Annex III, prohibited-practice and limited-risk signal
lists and reports fixed confidence values, which are not a probability or a
model score. Its ONNX export is a Python-API-only function behind the `[onnx]`
extra; no command and no scan calls it.

The GGUF models run locally through llama.cpp. `saas` is the opt-in cloud
backend and sends redacted source snippets to the hosted intent API.

## `ai configure`

Save the active model. Without `--model` it opens an interactive list.

=== "macOS / Linux"
    ```bash
    opencomplai ai configure --model codebert-onnx --set-default
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai ai configure --model codebert-onnx --set-default
    ```

| Option | Default | Description |
|---|---|---|
| `--model` | *(interactive)* | Model id from the table above. |
| `--set-default` | off | Save the choice to `~/.opencomplai/ai-config.yaml`. Without it, `--model` only prints `Selected model: <id>  (not saved ...)`. In the interactive list a prompt asks whether to save. |

`configure` only saves the choice. It downloads nothing; a GGUF model is
downloaded the first time a scan needs it.

Choosing `saas` first shows the data-egress notice and asks for a recorded,
one-time consent. A non-interactive run cannot give consent, so it exits `2`
and tells you to run the command on a terminal or pick a local model. Declining
the prompt exits `1`. With `OPENCOMPLAI_OFFLINE` set, `saas` is refused with
exit `2`.

## `ai status`

Print the active model, its display name, size, runtime and license, whether
llama.cpp is installed (for the GGUF models), the cache directory
(`~/.cache/opencomplai/models`) and what is cached there.

=== "macOS / Linux"
    ```bash
    opencomplai ai status
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai ai status
    ```

`ai status` has no options. For `codebert-onnx` and `saas` an empty cache is
normal, because neither has a local file; no "not yet downloaded" line is
printed for them.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Done. Cancelling the interactive list also exits `0`. |
| 1 | `opencomplai-ai` is not installed, or the `saas` consent prompt was declined. |
| 2 | Unknown `--model` (the message lists the valid ids), or `saas` could not be consented to (non-interactive, or `OPENCOMPLAI_OFFLINE` set). |

## See also

- [scan](scan.md): `scan --ai-intent` uses the model chosen here.
