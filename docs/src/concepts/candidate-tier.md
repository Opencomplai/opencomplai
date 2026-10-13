# Candidate tier

A **candidate** is a lead for a person. It points at an AI library that is imported in your code but
yields no classification signal. It is not a finding, and nothing in the scan treats it as one.

Candidates sit under `eu_ai_scan.candidates` in the scan JSON. Only the intent-path scan
(`scan --ai-intent`) may add them. The list is empty when nothing qualifies.

## Fields

| Field | Meaning |
|---|---|
| `library` | The imported AI library. |
| `file` | The file holding the import. |
| `line` | The 1-based line of the import. |
| `reason` | Always `imported_not_classified`. |

There is no tier, Annex III area, severity or confidence on a candidate, on purpose.

## What a candidate never does

- It is never counted in `regulatory_finding_count`.
- It never enters the classification proposal written by `scan --propose`.
- It never changes severity, the report hash, SARIF output or any exit code.

A candidate asks one question of a reviewer: is this library used for something that needs a
classification? The answer is the declared purpose, confirmed by a person.

The decision behind this tier is in `docs/adr/ADR-eu-ai-scan-gate.md`, decision 8.
