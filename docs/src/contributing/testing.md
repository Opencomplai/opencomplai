# Testing

Opencomplai uses `pytest` for Python tests and `pnpm test` for the Node.js gateway service. This page covers how to run the full test suite, where tests live, and what to write for new contributions.

---

## Python tests

### Run all Python tests

=== "macOS / Linux"
    ```bash
    uv run pytest packages/
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv run pytest packages/
    ```

### Run tests for a specific package

=== "macOS / Linux"
    ```bash
    uv run pytest packages/core/
    uv run pytest packages/cli/
    uv run pytest packages/sdk-python/
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv run pytest packages/core/
    uv run pytest packages/cli/
    uv run pytest packages/sdk-python/
    ```

### Run a specific test file

=== "macOS / Linux"
    ```bash
    uv run pytest packages/core/tests/test_engine.py -v
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv run pytest packages/core/tests/test_engine.py -v
    ```

### Run with coverage

=== "macOS / Linux"
    ```bash
    uv run pytest packages/ --cov=packages --cov-report=term-missing
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv run pytest packages/ --cov=packages --cov-report=term-missing
    ```

---

## Test layout

Tests mirror the source structure under each package:

```
packages/
  core/
    src/opencomplai_core/     source
    tests/
      test_engine.py          engine + rule tests
      test_models.py          Pydantic model validation tests
  cli/
    src/opencomplai_cli/
    tests/
      test_main.py            CLI command tests (via typer.testing.CliRunner)
  sdk-python/
    src/opencomplai/
    tests/
      test_sdk.py             SDK public API tests
```

---

## Writing tests for a new rule

When you add a rule, add tests to `packages/core/tests/test_engine.py`. Use the `_make_input` helper pattern:

```python
from opencomplai_core.engine import assess
from opencomplai_core.models import AssessmentInput, ModelMetadata


def _make_input(use_case: str, answers: dict | None = None) -> AssessmentInput:
    return AssessmentInput(
        model=ModelMetadata(
            name="test-model",
            version="1.0",
            modality="text",
            use_case=use_case,
            deployment_context="test",
        ),
        answers=answers or {},
    )


def test_my_rule_passes():
    result = assess(_make_input("safe use case"))
    rule = next(r for r in result.rule_results if r.rule_id == "EU_AIA_MY_RULE")
    assert rule.passed


def test_my_rule_fails():
    result = assess(_make_input("triggering use case"))
    rule = next(r for r in result.rule_results if r.rule_id == "EU_AIA_MY_RULE")
    assert not rule.passed
    assert "keyword" in rule.rationale  # verify the rationale is informative
```

---

## Writing tests for a new CLI command

Use `typer.testing.CliRunner`:

```python
from typer.testing import CliRunner
from opencomplai_cli.main import app

runner = CliRunner()


def test_validate_manifest_valid(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"system_id":"x","intended_purpose":"p","compliance_target":"EU_AI_ACT","high_risk_presumption":false,"commit_ref":"HEAD"}')
    result = runner.invoke(app, ["validate-manifest", str(manifest)])
    assert result.exit_code == 0
    assert "valid" in result.output


def test_validate_manifest_missing_file(tmp_path):
    result = runner.invoke(app, ["validate-manifest", str(tmp_path / "missing.json")])
    assert result.exit_code == 2
```

---

## Node.js tests (gateway-api)

=== "macOS / Linux"
    ```bash
    cd services/gateway-api
    pnpm test
    ```

=== "Windows (PowerShell)"
    ```powershell
    cd services/gateway-api
    pnpm test
    ```

The gateway-api uses Jest. Test files live under `services/gateway-api/src/__tests__/`.

---

## CI matrix

Tests run automatically on every pull request via `.github/workflows/ci-python.yml` and `.github/workflows/ci-node.yml`. The matrix covers:

| Workflow | Scope | Tools |
|---|---|---|
| `ci-python.yml` | All Python packages | `uv run pytest`, `ruff check`, `ruff format --check` |
| `ci-node.yml` | `services/gateway-api` | `pnpm test`, `pnpm lint` |
| `ci-docker.yml` | Docker Compose stack | `docker compose build`, smoke tests |

All three must be green before a PR can merge.

---

## Pre-commit hooks

The project uses `pre-commit` to run checks before each commit. Install once:

=== "macOS / Linux"
    ```bash
    pre-commit install
    ```

=== "Windows (PowerShell)"
    ```powershell
    pre-commit install
    ```

Hooks run `ruff check`, `ruff format`, and other checks on changed files. Run manually:

=== "macOS / Linux"
    ```bash
    pre-commit run --all-files
    ```

=== "Windows (PowerShell)"
    ```powershell
    pre-commit run --all-files
    ```
