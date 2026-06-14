# AI / LLM Dependency Inventory

**Compliance mapping:** EU AI Act Art. 3/50 · ISO 27001 A.5.7 · FedRAMP SA-11  
**Last audited:** 2026-05-29  
**Audited by:** Engineering team (automated CI scan + manual review)

---

## Result: No AI/LLM Dependencies Found

A repo-wide scan of all `pyproject.toml` and `package.json` files across the monorepo found **zero** occurrences of the following package names:

| Package | Category | Found |
|---|---|---|
| `openai` | LLM provider SDK | No |
| `anthropic` | LLM provider SDK | No |
| `transformers` | ML model library (Hugging Face) | No |
| `torch` / `pytorch` | ML inference framework | No |
| `tensorflow` | ML inference framework | No |
| `langchain` | LLM orchestration | No |
| `llm` | LLM CLI / library | No |
| `sentence-transformers` | Embedding model | No |
| `diffusers` | Image generation | No |
| `accelerate` | ML training accelerator | No |

---

## Classification Logic

Opencomplai's risk classification engine (`packages/core/src/opencomplai_core/rules.py`) is **fully deterministic and rule-based**:

- `AnnexIIIClassifierRule` — keyword matching against EU AI Act Annex III categories
- `UnacceptableRiskRule` — frozenset membership check for prohibited practice signals
- `ProfilingDetectionRule` — keyword matching for profiling signals
- `SubstantialModificationRule` — boolean flag from assessment answers

No machine-learning inference, embedding generation, or LLM completion is performed in production.

---

## Gate for Future AI/LLM Adoption

A CI check in `.github/workflows/ci-python.yml` and `.github/workflows/ci-node.yml` fails if any of the above package names appear in a dependency file without a corresponding approved entry added to this document.

To add an approved AI dependency:
1. Add an entry to the **Approved AI Dependencies** table below
2. Obtain CISO sign-off (record approval in the PR)
3. Update the CI allowlist in both workflow files

---

## Approved AI Dependencies

*None at this time.*

| Package | Version | Purpose | Approved by | Date |
|---|---|---|---|---|
| — | — | — | — | — |

---

## References

- `packages/core/src/opencomplai_core/rules.py` — rule registry (deterministic)
- `.github/workflows/ci-python.yml` — AI package CI gate
- `.github/workflows/ci-node.yml` — AI package CI gate (Node.js)
