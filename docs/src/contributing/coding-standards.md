# Coding Standards

---

## Python

### Toolchain

| Tool | Purpose | Run |
|---|---|---|
| `ruff check` | Linting | `ruff check packages/ services/` |
| `ruff format` | Formatting | `ruff format packages/ services/` |
| `pyright` / `mypy` | Type checking | `uv run pyright packages/` |

All three run in CI (`ci-python.yml`). The pre-commit hooks run `ruff check` and `ruff format` on changed files.

### Requirements

- **Python 3.11+** — use the new union syntax (`X | Y`) not `Optional[X]`.
- **Type hints required** on all public functions and class fields.
- **Pydantic v2** for data models — import from `pydantic`, not `pydantic.v1`.
- **Docstrings** on all public classes and functions. One-line summary + body if needed.
- **No side effects in rules** — rules must not write files, make HTTP calls, or import from `cli`.

### Import order

`ruff` enforces isort-style import ordering:

```python
# Standard library
from __future__ import annotations
import json
import sys

# Third-party
from pydantic import BaseModel, Field
import typer

# Local
from opencomplai_core.models import AssessmentInput, RuleResult
```

### Naming conventions

| Item | Convention | Example |
|---|---|---|
| Modules | `snake_case` | `risk_classify.py` |
| Classes | `PascalCase` | `HighRiskRule` |
| Functions / variables | `snake_case` | `assess_model` |
| Constants | `UPPER_SNAKE_CASE` | `RULE_REGISTRY` |
| Rule IDs | `EU_AIA_<ARTICLE>_<DESC>` | `EU_AIA_ART6_HIGH_RISK` |
| CLI commands | `kebab-case` | `opencomplai verify-output` |

---

## TypeScript / JavaScript (gateway-api)

### Toolchain

| Tool | Purpose | Run |
|---|---|---|
| `eslint` | Linting | `pnpm lint` |
| `prettier` | Formatting | `pnpm format:check` |
| `tsc` | Type checking | `pnpm typecheck` |

### Requirements

- TypeScript for all new `services/gateway-api` code.
- Strict mode enabled (`"strict": true` in `tsconfig.json`).
- No `any` types without a comment explaining why.
- JSDoc on public route handlers.

---

## Commit messages

Use the Conventional Commits format: `<type>(<scope>): <short summary>`

| Type | When to use |
|---|---|
| `feat` | New feature or behaviour |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Tests only |
| `refactor` | Refactor without behaviour change |
| `chore` | Dependency bumps, CI changes, tooling |

**Examples:**

```
feat(core): add Art. 52 transparency obligation rule
fix(cli): correct exit code for DEGRADED_COMPLETE in local mode
docs(deployment): add Grafana port to env-var table
test(core): add regression test for profiling detection rule
```

Scope is the package or service area: `core`, `cli`, `sdk`, `gateway-api`, `evidence-vault`, `docs`, `infra`.

---

## Pull request checklist

- [ ] `ruff check` and `ruff format --check` pass with zero errors.
- [ ] `uv run pytest packages/` is green.
- [ ] New public symbols have type hints and docstrings.
- [ ] New rules have tests in `test_engine.py`.
- [ ] Docs updated if user-facing behaviour changed.
- [ ] No `Content coming soon.` strings added to `docs/src/`.
- [ ] No `compliance-artifact.json` or `system-manifest.json` committed.
