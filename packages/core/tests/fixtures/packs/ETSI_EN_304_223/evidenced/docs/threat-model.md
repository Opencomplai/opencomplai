# AI threat model

Example Ltd ticket ranking system, reviewed by the security group.

## Assets

| Asset | Owner | Where it lives |
|---|---|---|
| Training data | Data team | internal artefact registry |
| Model weights | Platform team | internal artefact registry |
| Prompts and outputs | Platform team | service logs and prompts folder |

## Attack paths

Per threat, how an attacker would reach the assets.

| Threat | Attack path | Likelihood | Impact |
|---|---|---|---|
| data poisoning (row 6.2) | tampered ticket export enters the training set | medium | high |
| evasion attack (row 6.3) | crafted ticket text lowers the ranking | medium | medium |
| membership inference (row 6.4) | repeated queries probe for training tickets | low | medium |
| model exfiltration (row 6.5) | stolen service credentials pull weights | low | high |
| model inversion (row 6.6) | queries rebuild customer text | low | medium |
| direct model poisoning (row 6.7) | unreviewed change to weights in the registry | low | high |
| sensitive model output (row 6.8) | summary repeats personal data | medium | medium |
| prompt injection (row 6.9) | ticket body carries instructions | high | medium |
| output that carries injection attacks (row 6.10) | ranked text reaches a rendering tool | low | medium |
| denial of service (row B.2) | flood of long tickets | medium | medium |
| supply chain attack (row B.3) | malicious package update | low | high |
| backdoor attack (row B.4) | trigger phrase planted in a fine-tune set | low | high |
| direct model theft (row B.5) | copy of weights from a laptop | low | high |
| training data leak (row B.6) | export bucket left open | low | high |
| model input leak (row B.7) | prompts written to shared logs | medium | medium |

## Mitigations

| Threat | Mitigation | Evidence location |
|---|---|---|
| Prompt injection and jailbreak | input filtering and a fixed system prompt, tested every release | docs/red-team-report.md |
| Data poisoning and model poisoning | signed dataset snapshots and two-person review of weight changes | docs/ai-asset-inventory.md |
| Model extraction and membership inference | rate limits and query monitoring | service configuration |

## Residual risk

Prompt injection remains likely. The head of platform accepted it on 2026-10-14 with weekly monitoring of ranked output.

## Review date

Next review: 2027-01-14 by the security group
