# Technical Documentation — Art. 11

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What EU AI Act {{article}} covers

The provider must draw up technical documentation before the system is placed on the
market and keep it up to date. Annex IV lists what it must contain. This is a plain
summary; the Regulation text governs.

## Suggested steps

1. Run `opencomplai docs generate` to produce the Annex IV dossier from your manifest.
2. Fill the manual sections the dossier leaves open (design choices, data, validation).
3. Describe the logging mechanism and point to the record-keeping duty (Art. 12).
4. Record who owns the file and when it is reviewed (for example on each release).
5. Keep a dated copy for each released version of the system.

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`. Re-run `opencomplai gaps`
once the dossier is in the repository.
