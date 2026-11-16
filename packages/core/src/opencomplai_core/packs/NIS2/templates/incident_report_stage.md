# Incident report stage — {{article}}

**Requirement:** {{title}}
**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What to write

Open `docs/security/incident-notification.md` (run `opencomplai scaffold NIS2 incident_notification` if it does not exist yet) and find the section for the stage named by **{{article}}**: early warning, incident notification, intermediate report or final report.

1. Replace each `_fill in_` cell with your own entry: what is sent, to whom, the due time and when it was sent.
2. Keep the `<!-- clause: ... -->` line and the heading. The check finds each section by that line.
3. Check deadlines and recipients against the national rules that apply to you.

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
