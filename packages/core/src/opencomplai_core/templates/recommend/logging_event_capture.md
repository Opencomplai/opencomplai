# Logging / Event Capture — {{article}}

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What EU AI Act {{article}} requires

Record-keeping: the system must automatically log events over its lifetime to enable
traceability appropriate to the system's intended purpose (Art. 12), and providers must
keep technical documentation up to date (Art. 11).

## Suggested implementation

1. Identify the entry points where the AI system produces a decision, prediction, or
   recommendation that a human or downstream system consumes.
2. Emit a structured log event per invocation containing at minimum:
   - `timestamp`, `system_id`, `commit_ref` (or model version)
   - Input reference (or hash, if inputs are sensitive)
   - Output/decision produced
   - Any human override or confirmation applied
3. Retain logs for a period appropriate to the system's risk classification and your
   sector's record-keeping obligations.
4. Reference the logging mechanism in your technical documentation
   (see `opencomplai docs generate` for the Annex IV dossier).

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`. Re-run
`opencomplai gaps` after implementing logging to confirm the article-level status
improves once corroborating evidence is available.
