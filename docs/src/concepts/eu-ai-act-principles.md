# Control Codes → Principles → Articles

This page maps every EU AI Act article Opencomplai tracks to the 6 EU Trustworthy AI
principles (per the EU High-Level Expert Group on AI), and to the rule/obligation/scan/
evaluator source that produces its `opencomplai gaps` status.

**This page is generated** from `packages/core/src/opencomplai_core/data/eu_ai_act_principles.json` and `packages/core/src/opencomplai_core/data/gap_article_map.json` — the exact same data `opencomplai gaps`'s `principle_summary` output reads, so this page and the CLI can
never drift out of sync. Regenerate with `python scripts/generate_principle_docs.py`
after editing either data file.

---

## Technical Robustness and Safety

`technical_robustness_safety`

| Article | Source(s) |
|---|---|
| Art. 15 | `evaluator:EVAL_SAFETY_LEXICAL_V1`, `evaluator:EVAL_DATA_LEAKAGE_V1`, `scan:agent_framework` |
| Art. 25 | `rule:EU_AIA_ART25_MODIFICATION_TRAP` |

## Privacy and Data Governance

`privacy_data_governance`

| Article | Source(s) |
|---|---|
| Art. 10 | `evaluator:EVAL_BIAS_FAIRNESS_V1`, `scan:PII_DATAFLOW` |

## Transparency

`transparency`

| Article | Source(s) |
|---|---|
| Art. 12 | _no automated source_ |
| Art. 50 | `obligation:transparency` |

## Diversity, Non-discrimination and Fairness

`diversity_non_discrimination_fairness`

| Article | Source(s) |
|---|---|
| Art. 5 | `rule:EU_AIA_ART5_UNACCEPTABLE`, `obligation:prohibited` |
| Art. 6 | `rule:EU_AIA_ART6_HIGH_RISK`, `rule:EU_AIA_ART6_PROFILING`, `scan:biometric`, `scan:scoring_profiling`, `scan:agent_framework` |
| Art. 10 | `evaluator:EVAL_BIAS_FAIRNESS_V1`, `scan:PII_DATAFLOW` |

## Societal and Environmental Wellbeing

`societal_environmental_wellbeing`

| Article | Source(s) |
|---|---|
| Art. 5 | `rule:EU_AIA_ART5_UNACCEPTABLE`, `obligation:prohibited` |

## Accountability

`accountability`

| Article | Source(s) |
|---|---|
| Art. 4 | `obligation:ai_literacy` |
| Art. 11 | _no automated source_ |
| Art. 53 | `obligation:gpai_provider` |
| Art. 55 | `obligation:gpai_systemic_risk` |

---

See [Control Codes Reference](control-codes.md) for what triggers each rule code, and run `opencomplai gaps` to see this same mapping applied to your own system.
