# risk classify

Classify the risk level for an intended purpose without running a full compliance check.

## Synopsis

```bash
opencomplai risk classify --system-id <id> --intended-purpose <purpose> [OPTIONS]
```

!!! note
    This is a **subcommand** of `risk`, not a top-level command. The full invocation is `opencomplai risk classify`.

## Options

| Option | Default | Description |
|---|---|---|
| `--system-id` | *(required)* | Unique system identifier. |
| `--intended-purpose` | *(required)* | Primary intended purpose. |
| `--output` / `-o` | `human` | Output format: `human` or `json`. |

## Example

```bash
opencomplai risk classify \
  --system-id "my-model" \
  --intended-purpose "customer support chatbot"
```

Human output:

```text
Risk level: MINIMAL
```

JSON output:

```bash
opencomplai risk classify \
  --system-id "my-model" \
  --intended-purpose "customer support chatbot" \
  --output json
```

```json
{
  "model_name": "my-model",
  "model_version": "HEAD",
  "risk_level": "minimal",
  "rules_evaluated": 1,
  "rules_passed": 1,
  "rules_failed": 0,
  "rule_results": [
    {
      "rule_id": "EU_AIA_ART6_HIGH_RISK",
      "rule_name": "High-Risk System Classification (Article 6 / Annex III)",
      "passed": true,
      "rationale": "Use case 'customer support chatbot' does not match high-risk categories.",
      "reference": "EU AI Act, Article 6 and Annex III"
    }
  ],
  "evidence_summary": "Risk classification: MINIMAL. 1 rules passed, 0 rules failed.",
  "generated_at": "2026-04-27T09:16:52+00:00"
}
```

## Difference from `check`

`risk classify` returns a `RiskResult` — the output of the assessment engine only. `check` runs the full compliance workflow and produces a `ScanStatusArtifact` (which includes `failed_controls`, `evidence_hashes`, signing, and CI-gate semantics).
