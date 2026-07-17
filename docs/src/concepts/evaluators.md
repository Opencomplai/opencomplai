# Evaluators

Pipeline evaluators score actual model outputs (via `--sample-set` on `opencomplai
check`, `opencomplai gaps`, or `opencomplai eval`) against deterministic, versioned
detectors. This page enumerates every evaluator currently registered, and calls out the
two that are easy to confuse with each other.

All evaluators below are **local, deterministic, and airgap-safe** — none of them call
a network or an external model. For the separate, explicitly opt-in *live model*
evaluation path, see [Multi-provider eval](../cli/eval.md#multi-provider-eval---provider).

## Registered evaluators

| Evaluator ID | Category | What it measures | Default threshold |
|---|---|---|---|
| `EVAL_SAFETY_LEXICAL_V1` | Safety | Toxic/injection/jailbreak-marker lexicon scan over prompts and outputs | `0.98` clean rate |
| `EVAL_DATA_LEAKAGE_V1` | Data governance | PII/secret detectors (email, phone, SSN, secret, credit card) over outputs | `0.99` clean rate (zero-tolerance for SSN/secret/card) |
| `EVAL_BIAS_FAIRNESS_V1` | Bias | Disparate impact ratio, equal opportunity gap, demographic parity gap across protected-attribute groups | `0.80` disparate impact ratio |
| `EVAL_ADVERSARIAL_V1` | Adversarial | Whether known-adversarial prompts produced *compliant* (resisted) vs. *non-compliant* outputs | `0.95` resistance rate |
| `EVAL_CALIBRATION_V1` | Calibration | Expected Calibration Error (ECE) between prediction confidence and actual outcome rate | `0.90` (i.e. ECE ≤ `0.10`) |

See [Control Codes Reference](control-codes.md) for the first three (`EVAL_SAFETY_LEXICAL_V1`,
`EVAL_DATA_LEAKAGE_V1`, `EVAL_BIAS_FAIRNESS_V1`), including full remediation steps and
threshold-override JSON. This page covers the two newer evaluators and one important
distinction.

---

## `EVAL_ADVERSARIAL_V1` vs. `EVAL_SAFETY_LEXICAL_V1` — the distinction that matters

These two evaluators sound similar and use overlapping vocabulary ("jailbreak"), but
they measure different things:

| | `EVAL_SAFETY_LEXICAL_V1` | `EVAL_ADVERSARIAL_V1` |
|---|---|---|
| **What it scans** | Every prompt *and* output, independently | Prompt/output **pairs**, matched by index |
| **What it flags** | Presence of toxic/injection/jailbreak-marker text *anywhere* | Whether a **known-adversarial prompt** produced a **compliant (resisted) output** |
| **Question it answers** | "Does this text contain unsafe-looking content?" | "When someone tried to jailbreak this system, did it hold?" |
| **Metric** | Safety-clean rate | Adversarial resistance rate |

A system can pass `EVAL_SAFETY_LEXICAL_V1` (no toxic/injection markers anywhere) while
still failing `EVAL_ADVERSARIAL_V1` (an adversarial prompt got a compliant-sounding
answer that doesn't itself contain a flagged marker). They are complementary checks,
not duplicates — reference: NIST AI RMF MEASURE 2.7 / EU AI Act Art. 15 (robustness).

**Reference:** `packages/core/src/opencomplai_core/evaluators/adversarial.py`

### How pairing works

`EVAL_ADVERSARIAL_V1` pairs `sample_set.prompts[i]` with `sample_set.outputs[i]` when
the two lists are the same length. If prompt text isn't available (outputs-only mode),
it falls back to scanning every output against the compliance/refusal markers directly
— a lighter-weight signal, since it can no longer confirm the prompt was actually
adversarial.

### Threshold override

```json
{
  "threshold_overrides": { "adversarial": 0.90 }
}
```

---

## `EVAL_CALIBRATION_V1` — Expected Calibration Error

Measures how well a model's confidence scores (`predictions`, treated as probabilities
in `[0, 1]`) match its actual outcome rate (`labels`, binary ground truth), using
**Expected Calibration Error (ECE)** over 10 equal-width confidence bins.

In plain language: if a model says "90% confident" on a batch of predictions, a
well-calibrated model should be right about 90% of the time on that batch. ECE is the
weighted average gap between stated confidence and actual accuracy across all
confidence bins — `0.0` is perfectly calibrated, higher is worse.

**Opt-in only** — gated behind `threshold_overrides.include_calibration == 1.0`, since
calibration is GPAI-specific and must not slow down or spuriously fail a default
`opencomplai eval` run for systems where it doesn't apply:

```json
{
  "threshold_overrides": {
    "include_calibration": 1.0,
    "calibration": 0.90
  }
}
```

| Outcome | Condition |
|---|---|
| `SKIPPED` | `include_calibration` not set to `1.0`, or `predictions`/`labels` missing/mismatched |
| `FAIL` | `score < threshold` (i.e. ECE too high) |
| `WARN` | `score` within `0.02` of the threshold |
| `PASS` | `score >= threshold + 0.02` |

Reference: GPAI documentation support / EU AI Act Art. 15 (accuracy metrics).
**Source:** `packages/core/src/opencomplai_core/evaluators/calibration.py`.

---

## Bias/fairness — bundled synthetic probe (not a real benchmark)

`EVAL_BIAS_FAIRNESS_V1` (documented fully in [Control Codes](control-codes.md)) supports
an opt-in **bundled synthetic fairness probe** as a fallback data source when you have
no custom sample set of your own:

```json
{
  "threshold_overrides": { "use_bundled_bias_probe": 1.0 }
}
```

!!! warning "This is a synthetic, license-free placeholder — not BBQ/BOLD/CAB"
    The bundled probe (`bundled_bias_probe.json`, 40 rows across 2 synthetic groups) is
    a deterministic, reproducible smoke-test fixture — **not** a subset of a real
    third-party fairness benchmark such as BBQ, BOLD, or CAB. Redistribution licensing
    for those benchmarks has not been cleared, so no real benchmark data is bundled with
    this package.

    Use the bundled probe to confirm the evaluator's mechanics work end-to-end in an
    air-gapped environment. **Bring your own `--sample-set` with real, representative
    data** for an evaluation result you'd actually rely on for a fairness
    determination — the bundled probe's PASS/FAIL is not evidence about your system.

It only activates when `predictions` is empty **and** `use_bundled_bias_probe == 1.0` —
it never triggers implicitly, and supplying your own `predictions`/`labels`/
`protected_attributes` always takes precedence.

---

## Live-model evaluation (out of scope for this page)

All evaluators above run against data you already have (`prompts`/`outputs`/
`predictions`/`labels` in an `EvalSampleSet`) — none of them call a model. For an
optional path that calls a live model provider to *generate* outputs before scoring
them, see [`opencomplai eval --provider`](../cli/eval.md#multi-provider-eval---provider).
That path is explicitly non-deterministic and never runs as part of `opencomplai
check`'s default (air-gapped) path.
