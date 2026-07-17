# Risk Register Entry — {{article}}

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What EU AI Act {{article}} requires

Data and data governance (Art. 10) and accuracy/robustness/cybersecurity (Art. 15)
require the provider to identify, document, and mitigate risks related to training data
quality, bias, and system robustness against errors, faults, and adversarial attempts.

## Suggested risk register entry

| Field | Value |
|---|---|
| Risk ID | RISK-{{template_id}}-001 |
| Article | {{article}} |
| Description | _Describe the specific risk (e.g. training data bias, adversarial robustness gap, data leakage) — fill in._ |
| Likelihood | _Low / Medium / High_ |
| Impact | _Low / Medium / High_ |
| Mitigation | _Describe the control (e.g. bias evaluator threshold, red-team test, data governance review)._ |
| Owner | _Name / team_ |
| Review cadence | _e.g. every release, quarterly_ |
| Evaluator reference | Run `opencomplai eval --sample-set <path>` and cite the relevant evaluator id (`EVAL_BIAS_FAIRNESS_V1`, `EVAL_SAFETY_LEXICAL_V1`, `EVAL_DATA_LEAKAGE_V1`) here once available. |

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
