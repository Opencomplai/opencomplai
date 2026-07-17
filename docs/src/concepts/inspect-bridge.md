# Inspect-AI eval bridge (curated)

**What it is:** a thin opt-in bridge from OpenComplAI’s `eval` command into
UK AISI Inspect (`inspect-ai`) tasks. OpenComplAI owns the mapping into
`EvaluatorResult`; Inspect owns model routing and scoring.

**When to use it:** you need a short empirical check on jailbreak resistance,
bias (BBQ), or calibration — and you are fine making a live model call.

**Don't:** treat bridge scores as a substitute for `opencomplai check`, Annex IV
dossiers, or legal advice. Bridge results never change contractual exit codes.

## Curated pin

| Task | Technical requirement |
|------|------------------------|
| `strong_reject` | Cyberattack resilience |
| `bbq` | Representation — absence of bias |
| `bigbench_calibration` | Interpretability / calibration |

This is a curated OpenComplAI pin of Inspect tasks — not a full external registry.

## Regulation → OpenComplAI → pinned task

| Concern | OpenComplAI default path | Bridge task (opt-in) |
|---------|--------------------------|----------------------|
| Jailbreak / adversarial | `EVAL_ADVERSARIAL_V1` (lexical) | `strong_reject` |
| Bias / fairness | `EVAL_BIAS_FAIRNESS_V1` (samples) | `bbq` |
| Calibration | `EVAL_CALIBRATION_V1` (samples) | `bigbench_calibration` |
| CI release gate | `opencomplai check` exit 0–4 | *(never)* |

## Vendor note (SOC 2 CC9 / ISO A.5.19)

Inspect, model APIs, and PyPI are third-party suppliers. Keep them off default
gate images; pin versions in the `inspect-bridge` extra; document residency for
any prompts you send to a hosted model.
