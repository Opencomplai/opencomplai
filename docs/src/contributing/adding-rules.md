# Adding Rules

Rules are the core extensibility point of Opencomplai. Each rule is a deterministic check that maps an `AssessmentInput` to a `RuleResult`.

## File locations

| File | Purpose |
|---|---|
| `packages/core/src/opencomplai_core/rules.py` | All rule implementations and `RULE_REGISTRY` |
| `packages/core/tests/test_engine.py` | Engine tests (add your rule's tests here) |

## Step 1: Understand `BaseRule`

```python
from abc import ABC, abstractmethod
from opencomplai_core.models import AssessmentInput, RuleResult

class BaseRule(ABC):
    @property
    @abstractmethod
    def rule_id(self) -> str: ...       # e.g. "EU_AIA_ART6_HIGH_RISK"

    @property
    @abstractmethod
    def rule_name(self) -> str: ...     # Human-readable name

    @property
    @abstractmethod
    def reference(self) -> str: ...     # EU AI Act article reference

    @abstractmethod
    def evaluate(self, input: AssessmentInput) -> RuleResult: ...
```

## Step 2: Write your rule

Add a new class to `rules.py`. Use the naming convention `EU_AIA_<ARTICLE>_<DESCRIPTION>` for the `rule_id`.

```python
class TransparencyObligationRule(BaseRule):
    rule_id = "EU_AIA_ART52_TRANSPARENCY"
    rule_name = "Transparency Obligation (Article 52)"
    reference = "EU AI Act, Article 52"

    CHATBOT_SIGNALS: frozenset[str] = frozenset([
        "chatbot", "conversational", "virtual assistant",
        "chat assistant", "dialogue system",
    ])

    def evaluate(self, input: AssessmentInput) -> RuleResult:
        use_case = input.model.use_case.lower()
        is_chatbot = any(signal in use_case for signal in self.CHATBOT_SIGNALS)
        disclosure_present = input.answers.get("chatbot_disclosure", False)

        if is_chatbot and not disclosure_present:
            return RuleResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                passed=False,
                rationale=(
                    f"Use case '{input.model.use_case}' indicates a chatbot / conversational "
                    "system. Article 52 requires disclosure to users that they are interacting "
                    "with an AI. Set answers['chatbot_disclosure'] = True to confirm compliance."
                ),
                reference=self.reference,
            )

        return RuleResult(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            passed=True,
            rationale="Transparency obligation satisfied or not applicable.",
            reference=self.reference,
        )
```

## Step 3: Register the rule

Append an instance to `RULE_REGISTRY` at the bottom of `rules.py`:

```python
RULE_REGISTRY: list[BaseRule] = [
    UnacceptableRiskRule(),
    AnnexIIIClassifierRule(),
    ProfilingDetectionRule(),
    SubstantialModificationRule(),
    TransparencyObligationRule(),   # add here
]
```

The engine iterates `RULE_REGISTRY` on every `assess()` call. No other changes are needed.

## Step 4: Write tests

Add tests to `packages/core/tests/test_engine.py`:

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


def test_transparency_chatbot_without_disclosure():
    result = assess(_make_input("customer support chatbot"))
    rule = next(r for r in result.rule_results if r.rule_id == "EU_AIA_ART52_TRANSPARENCY")
    assert not rule.passed


def test_transparency_chatbot_with_disclosure():
    result = assess(_make_input("customer support chatbot", {"chatbot_disclosure": True}))
    rule = next(r for r in result.rule_results if r.rule_id == "EU_AIA_ART52_TRANSPARENCY")
    assert rule.passed


def test_transparency_non_chatbot():
    result = assess(_make_input("image classifier for quality control"))
    rule = next(r for r in result.rule_results if r.rule_id == "EU_AIA_ART52_TRANSPARENCY")
    assert rule.passed
```

## Step 5: Run the tests

=== "macOS / Linux"
    ```bash
    uv run pytest packages/core/tests/test_engine.py -v
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv run pytest packages/core/tests/test_engine.py -v
    ```

All existing tests must still pass. New tests must pass. No regressions.

## Rule design guidelines

- **Deterministic:** same input same output, always.
- **No side effects:** rules must not write files, make HTTP calls, or import from `cli`.
- **Informative rationale:** the `rationale` field is user-facing. Write it as a sentence a developer will read in the compliance report.
- **Accurate reference:** always cite the specific EU AI Act article.
- **Use `answers` for signals you cannot infer:** if a determination requires human input (e.g. "has the system undergone a conformity assessment?"), key it in `AssessmentInput.answers` and document the key in this page.
