# Rules

Rules are the atomic unit of compliance evaluation in Opencomplai.

Every rule today belongs to the EU AI Act, and `rule` sources are EU AI Act only.
Other [frameworks](../frameworks/index.md) are assessed from the same evidence: NIST AI
RMF by re-projecting the EU AI Act rows, and a natively evaluated framework through its
own requirements map (see [Adding framework packs](../contributing/adding-framework-packs.md)).

## What a rule does

Each rule is a deterministic check that:

1. Receives an `AssessmentInput` (model metadata + optional answers).
2. Returns a `RuleResult` with a `passed` boolean, `rationale` string, and a `reference` to the article of the framework the rule belongs to.

## Rule ID naming convention

Rule IDs follow the pattern `EU_AIA_<ARTICLE>_<DESCRIPTION>`:

| Example ID | Description |
|---|---|
| `EU_AIA_ART6_HIGH_RISK` | Article 6 / Annex III high-risk classification check |

## The live rule set

Rules are implemented in `packages/core/src/opencomplai_core/rules.py`. Each `Rule` subclass implements the `evaluate(input: AssessmentInput) -> RuleResult` method.

The rule engine (in `packages/core/src/opencomplai_core/engine.py`) discovers all registered `Rule` subclasses, runs them against the input, and aggregates results into a `RiskResult`.

## Adding new rules

See [Adding Rules](../contributing/adding-rules.md) for the step-by-step guide.

## Python model reference

```python
from opencomplai_core.models import RuleResult

class RuleResult(BaseModel):
    rule_id: str
    rule_name: str
    passed: bool
    rationale: str
    reference: str  # EU AI Act article or clause reference
```
