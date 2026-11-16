# Outsourcing arrangement action — {{article}}

**Requirement:** {{title}}
**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What to write

Open `docs/vendor-register.md` (run `opencomplai scaffold EBA` if it does not exist yet) and add or update the entry for each outsourcing arrangement that **{{article}}** touches.

1. Name the service, the provider, the function it supports and whether it is critical or important — fill in.
2. Record the contract reference, the audit and access rights, the sub-outsourcing terms and the exit plan location.
3. Note when the arrangement was last reviewed and by whom.
4. Name the real evidence next to the text: a path, a ticket or a record, and its date.

## How the check reads it

- A register that still contains `_fill in_` reads as **Partial** (draft estimate 0.35).
- A register with your own text reads as **Partial** (draft estimate 0.6).
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
