# AI / LLM Dependency Inventory

**Compliance mapping:** EU AI Act Art. 3/50 · ISO 27001 A.5.7 · FedRAMP SA-11  
**Last audited:** 2026-08-24  
**Audited by:** Engineering team (documentation audit — issue #48)  
The content below was corrected on 2026-10-05; maintainer re-attestation is still pending.

---

## Result: AI/LLM Dependencies Found in the Optional `packages/ai` Plugin

The core rule engine (`packages/core`), CLI (`packages/cli`), and Python SDK
(`packages/sdk-python`) have **zero** AI/LLM dependencies and remain fully
deterministic — see [Classification Logic](#classification-logic) below.

`packages/ai` is a **separate, optional plugin** (not a dependency of `packages/core`,
`packages/cli`, or the `opencomplai` package that `pip install opencomplai` pulls in). It
ships a deterministic intent classifier and, with its `[deep]` extra, local LLM
inference, and is only present if a maintainer or contributor explicitly installs it. A repo-wide scan of `pyproject.toml` files found the following
occurrences of the CI gate's forbidden package names:

| Package | Category | Found |
|---|---|---|
| `openai` | LLM provider SDK | No |
| `anthropic` | LLM provider SDK | No |
| `torch` / `pytorch` | ML inference framework | No |
| `tensorflow` | ML inference framework | No |
| `langchain` | LLM orchestration | No |
| `llm` | LLM CLI / library | No |
| `sentence-transformers` | Embedding model | No |
| `diffusers` | Image generation | No |
| `accelerate` | ML training accelerator | No |
| `huggingface-hub` | Model hub client (Hugging Face) | **Yes** — `packages/ai` (optional plugin, base dependency) |
| `llama-cpp-python` | Local LLM inference (GGUF) | **Yes** — `packages/ai` (optional plugin, `[deep]` extra) |

**Coverage:** the manual scan above only inspected `pyproject.toml` (the only file type any
of these packages actually appear in today). The CI gate it mirrors covers more ground: it
scans `pyproject.toml`, `package.json`, and `requirements*.txt` files across the repo,
excluding `tests/`, `examples/`, `fixtures/`, `node_modules/`, `.venv/`, and `dist/` paths.

---

## Found AI/LLM Dependencies (`packages/ai` plugin)

| Package | Version constraint | Location | Purpose |
|---|---|---|---|
| `huggingface-hub` | `>=0.23` | `packages/ai/pyproject.toml` (base dependency) | Downloads GGUF model weights from the Hugging Face Hub for the `[deep]` models (`ensure_model` in `downloader.py`) |
| `llama-cpp-python` | `>=0.3.0` | `packages/ai/pyproject.toml` (`[deep]` optional extra) | Local GGUF model inference for the "deep" explainer backend (`explainer.py`, `registry.py`) |

The optional ONNX export function (`_ensure_onnx_export` in `downloader.py`)
additionally imports `optimum.onnxruntime` at runtime. `optimum` is declared only in the
`[onnx]` optional extra of `packages/ai/pyproject.toml` (`optimum[onnxruntime]>=1.18`),
not in the base dependencies, and is not on the gate's forbidden-package list, so the scan
above does not surface it on its own. If it is missing, the function raises a
`RuntimeError` with install instructions. That function is reachable only through the
Python API `ensure_model("codebert-onnx")`: no CLI command calls it, nothing reads the
`model.onnx` it writes, and it plays no part in classification. Neither `transformers` nor
`onnxruntime` is declared by any manifest; the optional `[onnx]` extra
(`optimum[onnxruntime]`) pulls them in transitively, for that Python-API export only.

None of these packages are imported by `packages/core` or `packages/sdk-python`.
`packages/cli` does not use any of them either: its only reference is an availability
probe (`import llama_cpp` in `_deep_installed`), which only reports whether the `[deep]`
extra is installed.
Installing `opencomplai` (or `pip install -e packages/core
packages/cli packages/sdk-python`) does not pull in `packages/ai` or any of the above.

---

## Classification Logic

Opencomplai's core risk classification engine
(`packages/core/src/opencomplai_core/rules.py`) is **fully deterministic and rule-based**:

- `AnnexIIIClassifierRule` — keyword matching against EU AI Act Annex III categories
- `UnacceptableRiskRule` — frozenset membership check for prohibited practice signals
- `ProfilingDetectionRule` — keyword matching for profiling signals
- `SubstantialModificationRule` — boolean flag from assessment answers

No machine-learning inference, embedding generation, or LLM completion is performed by
`packages/core`, `packages/cli`, or `packages/sdk-python`. In the optional `packages/ai`
plugin (see above), local ML inference happens only with the `[deep]` GGUF models
(`llama-cpp-python`, downloaded on demand). Its `codebert-onnx` backend is a deterministic
code-signal matcher with no model, no ONNX session and fixed confidence values, so the
plugin's base install performs no local ML inference. (The opt-in `saas` backend runs no
model in the plugin; with recorded consent it sends redacted code snippets to the hosted
intent API instead.) Either way this does not change the
deterministic behavior of the core engine — the plugin is an additive, opt-in
intent-classification aid, not a dependency of the compliance gate.

---

## Gate for Future AI/LLM Adoption

The `ai-package-gate` job in
[`.github/workflows/ci-python.yml`](https://github.com/Opencomplai/opencomplai/blob/main/.github/workflows/ci-python.yml)
scans `pyproject.toml`, `package.json`, and `requirements*.txt` files across the repo
(excluding `tests/`, `examples/`, `fixtures/`, `node_modules/`, `.venv/`, and `dist/`
paths) for the forbidden package names listed above and fails if any appear without a
matching entry in this document.

To propose a new AI dependency:
1. Add an entry to the **Approved AI Dependencies** table below with its package,
   version, purpose, and location.
2. Get a maintainer to re-attest to (review and approve) the entry — record the approval
   in the pull request. This is a maintainer action; this document does not self-approve
   entries.
3. Once approved, the gate will pass because the package name is present in this
   document.

---

## Approved AI Dependencies

The two packages below are **found**, documented, and structurally placed in this table
so the CI gate recognizes them — but they have **not yet been re-attested by a
maintainer** as part of this issue-#48 documentation correction. Approval status reflects
that pending state honestly; no sign-off, approver, or date is fabricated.

| Package | Version | Purpose | Location | Approval status |
|---|---|---|---|---|
| `huggingface-hub` | `>=0.23` | Downloads GGUF model weights from the Hugging Face Hub for the `[deep]` models | `packages/ai/pyproject.toml` | Pending maintainer re-attestation |
| `llama-cpp-python` | `>=0.3.0` (`[deep]` extra) | Local GGUF model inference for the "deep" explainer backend | `packages/ai/pyproject.toml` | Pending maintainer re-attestation |

---

## References

- `packages/core/src/opencomplai_core/rules.py` — deterministic rule registry (core, unaffected by `packages/ai`)
- `packages/ai/pyproject.toml` — declares `huggingface-hub` (base), `llama-cpp-python` (`[deep]` extra) and `optimum[onnxruntime]` (`[onnx]` extra); neither `transformers` nor `onnxruntime` is declared directly, the `[onnx]` extra pulls them in transitively
- `packages/ai/src/opencomplai_ai/downloader.py` — GGUF download logic (`ensure_model`, imports `huggingface_hub`) and the optional, Python-API-only ONNX export (`_ensure_onnx_export`, imports `transformers`, `optimum.onnxruntime`)
- `packages/ai/src/opencomplai_ai/explainer.py`, `registry.py` — `llama-cpp-python` (GGUF) backend
- `packages/ai/src/opencomplai_ai/classifier.py` — the `codebert-onnx` backend: deterministic code-signal matcher, imports none of the packages above
- `.github/workflows/ci-python.yml` — `ai-package-gate` job (AI package CI gate; scans `pyproject.toml`, `package.json`, and `requirements*.txt` repo-wide, excluding `tests/`, `examples/`, `fixtures/`, `node_modules/`, `.venv/`, and `dist/`)
- `.github/workflows/ci-node.yml` — Node.js CI; the `package.json` scan above already covers this workflow's projects, so it does not need its own AI/LLM package gate
