# Requirement Action Plan — {{article}}

**Requirement:** {{title}}
**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## Suggested next steps

1. Read the framework's own text for **{{article}}** and note what evidence it expects.
2. Produce that evidence in this repository (a document, a test result or a
   configuration) and record where it lives — fill in.
3. If the requirement does not apply to this system, declare it under
   `framework_inputs.{{framework}}.excluded` in the system manifest, with a
   justification.
4. If it is met by something outside the repository (e.g. a board-approved
   policy) and the requirement takes an attestation, record it under
   `framework_inputs.{{framework}}.attested` (statement, attested by, date).
5. Re-run `opencomplai gaps` to confirm the status changed.

| Field | Value |
|---|---|
| Owner | _Name / team_ |
| Evidence location | _Path or link — fill in_ |
| Target date | _YYYY-MM-DD_ |

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
