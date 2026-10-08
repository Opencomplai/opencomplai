# GPAI Provider Documentation: {{article}}

> Draft for founder and lawyer review: a topic checklist summarised from Annex XI and Annex XII of Regulation (EU) 2024/1689, not legal advice and not a statement that you comply; check each topic against the current text.

**Gap source:** {{source}} (`{{evidence_ref}}`)
**Why this was generated:** {{rationale}}
**Template:** `{{template_id}}`

## Part A: technical documentation (Annex XI Section 1; Art. 53 row)

General description of the model:

- [ ] Intended tasks, and the kinds of AI systems it can be integrated into.
- [ ] Acceptable-use policy.
- [ ] Release date and how it is distributed.
- [ ] Architecture and number of parameters.
- [ ] Input and output modalities and formats.
- [ ] Licence.

Development elements:

- [ ] Integration tooling and instructions for use.
- [ ] Design choices and training methodology, with the reasons for them.
- [ ] Training, testing and validation data: type, provenance, curation and bias detection.
- [ ] Compute used and training time.
- [ ] Known or estimated energy consumption.

## Part B: information for downstream providers (Annex XII; Art. 53 row)

- [ ] General description: tasks, interaction with external hardware or software, relevant software versions.
- [ ] Architecture, modalities, formats and licence.
- [ ] How the model can be integrated into a downstream system, and its input and output limits.
- [ ] Summary of data provenance and curation that a downstream provider needs.

## Part C: systemic-risk additions (Annex XI Section 2; Art. 55 row only)

- [ ] Evaluation strategies, results and limitations.
- [ ] Adversarial testing (internal or external) and the mitigation or alignment steps taken.
- [ ] System architecture, where relevant.
- [ ] Serious-incident tracking and cybersecurity measures (Art. 55).

## Not covered here

The copyright policy and the public training-content summary (Art. 53(1)(c) and (d)) are not covered by this template. For an Art. 53 row they are written alongside this file as `art53-gpai_copyright_policy.md` and `art53-gpai_training_summary.md`.

## Where to save it

`opencomplai gaps` only checks that a conventionally named file exists, never its content. Save your documents as:

- `docs/gpai/model-documentation.md` (Part A)
- `docs/gpai/downstream-information.md` (Part B)
- `docs/gpai/systemic-risk.md` (Part C)

## Traceability

This template was generated because `opencomplai gaps` reported **{{article}}** as
**{{status}}**, sourced from {{source}} `{{evidence_ref}}`.
