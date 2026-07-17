# GPAI Obligation Stub — {{article}}

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}

## What EU AI Act {{article}} requires

General-purpose AI (GPAI) model providers must maintain technical documentation, provide
information/documentation to downstream providers, and comply with EU copyright law
(Art. 53). GPAI models with systemic risk carry additional obligations: model evaluation,
adversarial testing, incident tracking/reporting, and cybersecurity protection (Art. 55).

## Suggested implementation

- [ ] Confirm whether your model meets the GPAI definition and, if so, whether it is
      classified as carrying systemic risk (compute threshold or Commission designation).
- [ ] Maintain technical documentation covering training/testing process and evaluation
      results, sufficient for downstream providers to understand capabilities/limitations.
- [ ] If systemic risk applies: document model evaluation and adversarial testing
      results, and your serious-incident tracking/reporting process.
- [ ] Reference `opencomplai checker` (the interactive EU AI Act wizard) to confirm your
      GPAI obligation set if you haven't already run it — see the `gpai_provider`/
      `gpai_systemic_risk` obligation catalog entries this template was derived from.

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
