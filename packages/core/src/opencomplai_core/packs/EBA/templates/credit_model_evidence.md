# Credit model evidence action — {{article}}

**Requirement:** {{title}}
**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What to write

Prepare the evidence for the credit decision model that **{{article}}** touches.

1. Complete the model card: purpose, inputs, training data, known limits and the owner — fill in.
2. Attach the latest bias and fairness evaluation result, with its date and the groups compared.
3. Record how the model output is explained to staff and to the person affected.
4. Name the real evidence next to the text: a path, a ticket or a record, and its date.

## How the check reads it

- The scan finds the model card and the evaluation result as corroboration only.
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
