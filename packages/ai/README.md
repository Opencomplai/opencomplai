# opencomplai-ai

[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![PyPI](https://img.shields.io/pypi/v/opencomplai-ai.svg)](https://pypi.org/project/opencomplai-ai/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

The optional **AI intent classification plugin** for [Opencomplai](https://opencomplai.com).
It adds the `--ai-intent` flag to `opencomplai scan`, classifying how each AI callsite in
your code is actually used — its decision autonomy, the subjects it acts on, and which EU
AI Act risk tier and Annex III area it maps to.

All inference runs **locally** — models execute on your machine via ONNX Runtime or
llama.cpp. No code or prompts leave your environment.

## Prerequisites

`opencomplai-ai` is a plugin. Install the core engine first:

```bash
pip install opencomplai-core   # or the opencomplai / opencomplai-cli suite
```

## Install

```bash
# Base install — CodeBERT (ONNX) classification, no extra build deps
pip install opencomplai-ai

# Deep install — adds llama.cpp for generative GGUF models
pip install "opencomplai-ai[deep]"
```

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

The default model (`codebert-onnx`) runs on the base install. The generative GGUF models
require the `[deep]` extra. Models are downloaded from the Hugging Face Hub on first use
and cached locally under `~/.opencomplai/`.

| Model ID | Runtime | Size | Needs `[deep]` |
|---|---|---|---|
| `codebert-onnx` *(default)* | ONNX Runtime | ~440 MB | no |
| `qwen2.5-coder-0.5b` | llama.cpp | ~400 MB | yes |
| `qwen2.5-coder-1.5b` *(recommended)* | llama.cpp | ~1.0 GB | yes |
| `smollm2-1.7b` | llama.cpp | ~1.1 GB | yes |
| `phi-3.5-mini` | llama.cpp | ~2.2 GB | yes |
| `mistral-7b` | llama.cpp | ~4.1 GB | yes |

```bash
opencomplai scan --ai-intent --ai-model qwen2.5-coder-1.5b
```

### Model download flow

On first use of a model, the plugin prompts before downloading and shows a progress bar.
The CodeBERT model has no prebuilt ONNX artifact on the Hub, so it is exported from the
official PyTorch checkpoint on first run and then cached. Subsequent scans reuse the
cached model with no network access.

## Documentation

Full AI-intent guide and the model reference at
**[docs.opencomplai.com](https://docs.opencomplai.com)**.

## License

AGPL-3.0-only. See [LICENSE](https://www.gnu.org/licenses/agpl-3.0).
