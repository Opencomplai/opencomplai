# Insurer AI Control Plan — {{article}}

**Topic:** {{title}}
**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## Suggested next steps

1. Read the supervisory topic **{{article}}** and note what evidence it expects for each AI system in use.
2. Produce that evidence in this repository (a policy section, a test result or a log) and record where it lives — fill in.
3. If the topic does not apply to a system, declare it under
   `framework_inputs.{{framework}}.excluded` in the system manifest, with a justification.
4. If it is covered by something outside the repository (for example a board-approved policy), record it under
   `framework_inputs.{{framework}}.attested` (statement, attested by, date).
5. Re-run `opencomplai gaps` to confirm the status changed.

| Field | Value |
|---|---|
| Owner | _Name / team_ |
| AI system | _fill in_ |
| Evidence location | _Path or link — fill in_ |
| Target date | _YYYY-MM-DD_ |

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
