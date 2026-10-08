# Value Chain Responsibilities — Art. 25

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What EU AI Act {{article}} covers

A distributor, importer, deployer or other third party can become the provider of a
high-risk system, with the provider duties, in some cases. This is a plain summary;
the Regulation text governs.

## Suggested decisions

- [ ] Do we put our own name or trademark on a high-risk system already on the market?
- [ ] Do we make a substantial modification (Art. 3(23)), for example retraining on new
      data, an architecture change, or a new deployment context?
- [ ] Do we change the intended purpose so the system becomes high-risk?
- [ ] If yes to any, record that we take the provider role and who owns the provider duties.
- [ ] Wire `opencomplai check --sign` (or your CI gate) to block deployment when a
      substantial-modification flag is set, until sign-off is recorded
      (`substantial_modification` answer in the assessment input).
- [ ] Record the reviewer's identity and decision in your evidence trail.

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
