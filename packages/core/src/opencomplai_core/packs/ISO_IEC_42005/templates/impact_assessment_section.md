# Impact assessment section — {{article}}

**Requirement:** {{title}}
**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What to write

Open `AI_IMPACT_ASSESSMENT.md` (run `opencomplai scaffold ISO_IEC_42005` if it does not exist yet) and find the section that starts with the `<!-- clause: ... -->` line for **{{article}}**.

1. Replace the `_fill in_` line with your own plain sentences: what your organisation does for this topic, who does it, and when.
2. Keep the `<!-- clause: ... -->` line and the heading. The check finds each section by that line.
3. Use concrete words the section is about (for example roles, dates, scales, systems, datasets), not general statements.
4. Name the real evidence next to the text: a path, a ticket or a record, and its date.

## How the check reads it

- A section that still contains `_fill in_` reads as **Partial** (draft estimate 0.35).
- A section with your own text and the expected keywords reads as **Partial** (draft estimate 0.6).
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
