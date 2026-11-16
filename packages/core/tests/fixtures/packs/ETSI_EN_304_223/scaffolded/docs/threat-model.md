# AI threat model

Draft for review. Replace every `_fill in_` cell with your own text. Unfilled, the file reads as Partial; a filled file is still only corroborating evidence.

## Assets

| Asset | Owner | Where it lives |
|---|---|---|
| Training data | _fill in_ | _fill in_ |
| Model weights | _fill in_ | _fill in_ |
| Prompts and outputs | _fill in_ | _fill in_ |

## Attack paths

Describe, per threat, how an attacker would reach the assets.

| Threat | Attack path | Likelihood | Impact |
|---|---|---|---|
| data poisoning (row 6.2) | _fill in_ | _fill in_ | _fill in_ |
| evasion attack (row 6.3) | _fill in_ | _fill in_ | _fill in_ |
| membership inference (row 6.4) | _fill in_ | _fill in_ | _fill in_ |
| model exfiltration (row 6.5) | _fill in_ | _fill in_ | _fill in_ |
| model inversion (row 6.6) | _fill in_ | _fill in_ | _fill in_ |
| direct model poisoning (row 6.7) | _fill in_ | _fill in_ | _fill in_ |
| sensitive model output (row 6.8) | _fill in_ | _fill in_ | _fill in_ |
| prompt injection (row 6.9) | _fill in_ | _fill in_ | _fill in_ |
| output that carries injection attacks (row 6.10) | _fill in_ | _fill in_ | _fill in_ |
| denial of service (row B.2) | _fill in_ | _fill in_ | _fill in_ |
| supply chain attack (row B.3) | _fill in_ | _fill in_ | _fill in_ |
| backdoor attack (row B.4) | _fill in_ | _fill in_ | _fill in_ |
| direct model theft (row B.5) | _fill in_ | _fill in_ | _fill in_ |
| training data leak (row B.6) | _fill in_ | _fill in_ | _fill in_ |
| model input leak (row B.7) | _fill in_ | _fill in_ | _fill in_ |

## Mitigations

| Threat | Mitigation | Evidence location |
|---|---|---|
| Prompt injection and jailbreak | _fill in_ | _fill in_ |
| Data poisoning and model poisoning | _fill in_ | _fill in_ |
| Model extraction and membership inference | _fill in_ | _fill in_ |

## Residual risk

Which risks remain after the mitigations, and who accepted them?

_fill in_

## Review date

Next review: _YYYY-MM-DD_ by _fill in_
