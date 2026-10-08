# opencomplai-ai

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![PyPI](https://img.shields.io/pypi/v/opencomplai-ai.svg)](https://pypi.org/project/opencomplai-ai/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

The optional **AI intent classification plugin** for [Opencomplai](https://opencomplai.com).
It adds the `--ai-intent` flag to `opencomplai scan`, classifying how each AI callsite in
your code is actually used — its decision autonomy, the subjects it acts on, and which EU
AI Act risk tier and Annex III area it maps to.

All inference runs **locally** — models execute on your machine via llama.cpp, or via a
deterministic code-signal matcher that needs no model weights at all. No code or prompts
leave your environment unless you explicitly opt into the `saas` backend.

## Prerequisites

`opencomplai-ai` is a plugin. Install the core engine first:

```bash
pip install opencomplai-core   # or the opencomplai / opencomplai-cli suite
```

## Install

```bash
# Base install — only the deterministic codebert-onnx matcher, no download
pip install opencomplai-ai

# Deep install — required for the default model (qwen2.5-coder-1.5b) and
# every other generative GGUF model
pip install "opencomplai-ai[deep]"
```

The base install alone can only run `codebert-onnx`. `opencomplai scan --ai-intent`
resolves `qwen2.5-coder-1.5b` by default, which needs `[deep]` — without it the scan
fails fast with an actionable message instead of downloading the ~1 GB model first and
only then discovering it can't be run.

## Usage

Once installed alongside the CLI, the `--ai-intent` flag becomes available on the scan
command:

```bash
opencomplai scan --ai-intent
```

By default only callsites in files with lexical findings are annotated (fast). To analyze
every callsite in the repository:

```bash
opencomplai scan --ai-intent --ai-deep
```

Useful flags:

| Flag | Effect |
|---|---|
| `--ai-intent` | Enable AI intent classification |
| `--ai-model <id>` | Choose a model (see catalog below) |
| `--ai-deep` | Annotate every callsite, not just those near lexical findings |
| `--ai-verbose` | Show all callsite annotations (default: top 10 by risk tier) |

## Supported models

The **default model is `qwen2.5-coder-1.5b`** and requires the `[deep]` extra. GGUF
models are downloaded from the Hugging Face Hub on first use and cached locally under
`~/.cache/opencomplai/models/`.

`codebert-onnx` is a **deterministic Annex III / prohibited-practice / limited-risk
code-signal matcher** — no model weights, no download, runs on the base install. It
trades recall for speed and zero setup; it is not the default.

| Model ID | Runtime | Size | Needs `[deep]` |
|---|---|---|---|
| `codebert-onnx` | deterministic matcher | no download | no |
| `qwen2.5-coder-0.5b` | llama.cpp | ~400 MB | yes |
| `qwen2.5-coder-1.5b` *(default)* | llama.cpp | ~1.0 GB | yes |
| `smollm2-1.7b` | llama.cpp | ~1.1 GB | yes |
| `phi-3.5-mini` | llama.cpp | ~2.2 GB | yes |
| `mistral-7b` | llama.cpp | ~4.1 GB | yes |

```bash
opencomplai scan --ai-intent                              # default: qwen2.5-coder-1.5b, needs [deep]
opencomplai scan --ai-intent --ai-model codebert-onnx     # no download, no [deep] extra
```

### Model download flow

On first use of a GGUF model, the plugin prompts before downloading and shows a progress
bar; the download is refused up front (no prompt, no partial download) if `[deep]` isn't
installed. `codebert-onnx` needs none of this in normal use — it does deterministic
code-signal matching with no model artifact to fetch.

The package also contains a Python-API-only function, `opencomplai_ai.downloader.ensure_model("codebert-onnx")`,
that exports the official PyTorch checkpoint of CodeBERT to ONNX (CodeBERT has no
prebuilt ONNX build on the Hub). No CLI command calls it (`opencomplai ai configure`
only saves your model choice), nothing reads the exported file, and it is not used for
`--ai-intent` classification. It needs the separate `[onnx]` extra (`optimum[onnxruntime]`).

### Optional extras

| Extra | Adds | Needed for |
|---|---|---|
| `[deep]` | `llama-cpp-python` | every GGUF model, including the default `qwen2.5-coder-1.5b` |
| `[onnx]` | `optimum[onnxruntime]` | only the Python-API `ensure_model("codebert-onnx")` export — not classification, not any CLI command |

## Configuration

| Env var | Default | Effect |
|---|---|---|
| `OPENCOMPLAI_AI_TIMEOUT_SECONDS` | `10` | Per-callsite timeout for local GGUF inference. A callsite whose completion doesn't finish in time is skipped — never reported as "minimal risk" — and a second call is refused rather than racing the abandoned worker. |
| `OPENCOMPLAI_OFFLINE` | unset | Block all network access outright: no model downloads, no `saas` calls. |
| `OPENCOMPLAI_API_KEY` | unset | Required to use the `saas` cloud backend. |

## Documentation

Full AI-intent guide and the model reference at
**[docs.opencomplai.com](https://docs.opencomplai.com)**.

## License

AGPL-3.0-only. See [LICENSE](https://www.gnu.org/licenses/agpl-3.0).
