# Human Oversight Checklist — {{article}}

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What EU AI Act {{article}} requires

High-risk AI systems must be designed to allow effective human oversight, and any
substantial modification to a deployed high-risk system triggers a new conformity
assessment before redeployment (Art. 25 / Art. 3(23)).

## Suggested implementation

- [ ] Identify who is authorised to review, override, or halt this system's outputs.
- [ ] Document the escalation path when a human reviewer disagrees with an output.
- [ ] Define what counts as a "substantial modification" for this system (e.g. retraining
      on new data, architecture change, new deployment context) and require sign-off
      before redeploying after one occurs.
- [ ] Wire `opencomplai check --sign` (or your CI gate) to block deployment when a
      substantial-modification flag is set, until sign-off is recorded
      (`substantial_modification` answer in the assessment input).
- [ ] Record the reviewer's identity and decision in your evidence trail.

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
