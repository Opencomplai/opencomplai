# AI asset inventory

Example Ltd service desk ranking system. Reviewed with the platform team.

## Assets

| Asset | Kind | Version or hash | Owner | Source |
|---|---|---|---|---|
| ticket-ranker model | model | v1.4.0, sha256 3f9a1c07 | Platform team | in-house fine-tune of an open model |
| ticket history dataset | dataset | 2026-09 snapshot | Data team | Example Ltd help desk exports |
| ranking system prompt | system prompt | v2.1 | Platform team | repository prompts folder |
| tokenizer library | third-party component | v0.15.2 | Platform team | public package index |

Kinds to consider: model, dataset, training data, prompt, system prompt, fine-tune, adapter, evaluation set, tool or plug-in.

## Review

| Field | Value |
|---|---|
| Last reviewed | 2026-10-14 |
| Reviewed by | Head of platform |
| Next review date | 2027-01-14 |

## Notes

Each asset is stored in the internal artefact registry. Only the platform team can change it, and every change is logged in the registry audit trail.
