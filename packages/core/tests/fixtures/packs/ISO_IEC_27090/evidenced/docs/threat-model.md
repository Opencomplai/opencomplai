# AI threat model

Reviewed by Example Ltd security. This file is corroborating evidence only.

## Assets

| Asset | Owner | Where it lives |
|---|---|---|
| Training data | Example Ltd data team | object store ex-train |
| Model weights | Example Ltd ML team | model registry |
| Prompts and outputs | Example Ltd service desk | gateway logs |

## Attack paths

Describe, per threat, how an attacker would reach the assets.

| Threat | Attack path | Likelihood | Impact |
|---|---|---|---|
| data poisoning (row 6.2) | via the public gateway | medium | high |
| evasion attack (row 6.3) | via the public gateway | medium | high |
| membership inference (row 6.4) | via the public gateway | medium | high |
| model exfiltration (row 6.5) | via the public gateway | medium | high |
| model inversion (row 6.6) | via the public gateway | medium | high |
| direct model poisoning (row 6.7) | via the public gateway | medium | high |
| sensitive model output (row 6.8) | via the public gateway | medium | high |
| prompt injection (row 6.9) | via the public gateway | medium | high |
| output that carries injection attacks (row 6.10) | via the public gateway | medium | high |
| denial of service (row B.2) | via the public gateway | medium | high |
| supply chain attack (row B.3) | via the public gateway | medium | high |
| backdoor attack (row B.4) | via the public gateway | medium | high |
| direct model theft (row B.5) | via the public gateway | medium | high |
| training data leak (row B.6) | via the public gateway | medium | high |
| model input leak (row B.7) | via the public gateway | medium | high |

## Mitigations

| Threat | Mitigation | Evidence location |
|---|---|---|
| Prompt injection and jailbreak | input filter and review of changes | config/guardrails.yaml |
| Data poisoning and model poisoning | input filter and review of changes | config/guardrails.yaml |
| Model extraction and membership inference | input filter and review of changes | config/guardrails.yaml |

## Residual risk

Which risks remain after the mitigations, and who accepted them?

Residual risk is accepted by the Example Ltd security lead for one year.

## Review date

Next review: 2026-06-30 by Example Ltd security lead
