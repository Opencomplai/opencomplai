# Security measure — {{article}}

**Requirement:** {{title}}
**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What to write

Describe the measure in your own words in the document the check looks for. For this row that is usually a policy or procedure under `docs/`; the starter files come from `opencomplai scaffold NIS2` where one exists.

1. State what the organisation does for this topic, who owns it, and how often it is reviewed.
2. Name the real evidence next to the text: a path, a ticket or a record, with its date.
3. Replace every `_fill in_` line; the check reads a file that still has one as unfilled.

## How the check reads it

- A document that still contains `_fill in_` reads as **Partial** (draft estimate 0.35).
- A document with your own text and the expected keywords reads as **Partial** (draft estimate 0.6).
- The check alone never gives **Met**. A named person's attestation under `framework_inputs.{{framework}}.attested` (statement, attested by, date) is what can move the row further.
- If the requirement does not apply, declare it under `framework_inputs.{{framework}}.excluded` with a justification.

Re-run `opencomplai gaps` to see the status change.

| Field | Value |
|---|---|
| Owner | _Name / team_ |
| Evidence location | _Path or link — fill in_ |
| Target date | _YYYY-MM-DD_ |

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as **{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
