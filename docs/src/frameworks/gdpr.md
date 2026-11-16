# GDPR: duties relevant to AI systems

This page covers `GDPR`, a pack of 21 requirements taken from Regulation (EU) 2016/679 that matter
when a system processes personal data. They are 21 rows, not the whole regulation: articles outside
the list are not checked. Nothing here is an audit, a certification or a legal assessment.

## What it is

A native pack. Each row is one article (or a short article range), with the article number as
published, a one-line description in this project's own words, and links to the EU AI Act and
ISO/IEC 27001 that are the project's own judgement. Every row is at low confidence and reads
`mapping not yet reviewed`.

## Does it apply to you

The pack asks six questions in the manifest: personal data processed, EU establishment or EU data
subjects, controller role, solely automated decisions, special-category data, and transfers outside
the EEA. Answer them under `framework_inputs.GDPR`. If the answers show no personal data or no
territorial reach, the pack reads not applicable; otherwise it applies by default.

## How rows are decided

Every row takes a provider attestation. 18 of 21 requirements are checked from evidence as well:
files and conventions in the repository (a data protection impact assessment, a record of
processing, a breach register and similar) corroborate the attestation. 3 of 21 are attestation
only. The target is 8 of 21; the pack is above it. A scaffold left unfilled does not count as
evidence. A row reads Met, Partial, Missing or Unverified.

| Evidence class | Rows |
|---|---|
| Machine | 0 |
| Hybrid | 18 |
| Organisational | 3 |

## Requirements

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| GDPR:Art. 5 | Principles relating to processing of personal data | hybrid | attestation: GDPR:Art. 5; scan: pii_dataflow (corroborating) | 90 | mapping not yet reviewed |
| GDPR:Art. 6 | Lawfulness of processing | organisational | attestation: GDPR:Art. 6 | 365 | mapping not yet reviewed |
| GDPR:Art. 9 | Processing of special categories of personal data | hybrid | attestation: GDPR:Art. 9; artifact: gdpr.dpia#special-categories (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 12 | Transparent information and modalities for exercising data subject rights | hybrid | attestation: GDPR:Art. 12; artifact: data_subject_request_procedure (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 13 | Information to be provided where data are collected from the data subject | hybrid | attestation: GDPR:Art. 13; artifact: privacy_notice (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 14 | Information where data have not been obtained from the data subject | hybrid | attestation: GDPR:Art. 14; artifact: privacy_notice (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 15 | Right of access by the data subject | hybrid | attestation: GDPR:Art. 15; artifact: data_subject_request_procedure (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 17 | Right to erasure ('right to be forgotten') | hybrid | attestation: GDPR:Art. 17; artifact: data_subject_request_procedure (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 21 | Right to object | hybrid | attestation: GDPR:Art. 21; artifact: data_subject_request_procedure (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 22 | Automated individual decision-making, including profiling | hybrid | attestation: GDPR:Art. 22; artifact: gdpr.dpia#automated-decisions (corroborating); artifact: human_oversight_construct (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 24 | Responsibility of the controller | organisational | attestation: GDPR:Art. 24 | 365 | mapping not yet reviewed |
| GDPR:Art. 25 | Data protection by design and by default | hybrid | attestation: GDPR:Art. 25; artifact: gdpr.dpia#measures (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 28 | Processor | hybrid | attestation: GDPR:Art. 28; artifact: processor_register (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 30 | Records of processing activities | hybrid | attestation: GDPR:Art. 30; artifact: record_of_processing (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 32 | Security of processing | hybrid | attestation: GDPR:Art. 32; artifact: security_policy_file (corroborating); evaluator: EVAL_DATA_LEAKAGE_V1 (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 33 | Notification of a personal data breach to the supervisory authority | hybrid | attestation: GDPR:Art. 33; artifact: breach_register (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 34 | Communication of a personal data breach to the data subject | hybrid | attestation: GDPR:Art. 34; artifact: breach_register (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 35 | Data protection impact assessment | hybrid | attestation: GDPR:Art. 35; artifact: gdpr.dpia#risks (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 36 | Prior consultation | hybrid | attestation: GDPR:Art. 36; artifact: gdpr.dpia#consultation (corroborating) | 365 | mapping not yet reviewed |
| GDPR:Art. 37-39 | Designation, position and tasks of the data protection officer | organisational | attestation: GDPR:Art. 37-39 | 365 | mapping not yet reviewed |
| GDPR:Chapter V | Transfers of personal data to third countries or international organisations | hybrid | attestation: GDPR:Chapter V; artifact: transfer_record (corroborating) | 365 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

Two starting documents are written into the repository on request: a data protection impact
assessment (`DPIA.md`, Art. 35) and a record of processing (`docs/ropa.md`, Art. 30). Each has
`_fill in_` placeholders. Three templates help with the privacy record, the security measure and the
impact assessment section. They are drafts, not legal advice.

## Timeline

Both entries are marked `mapping not yet reviewed`.

| Entry | Period |
|---|---|
| Response to a data subject's request, Art. 12(3) | One month from receipt of the request |
| Personal data breach notification, Art. 33(1) | 72 hours after becoming aware of the breach |

## Gate in CI

```sh
opencomplai check --target GDPR --gate GDPR --gate-fail-on missing --repo-root .
```

The command exits 1 and lists the requirement ids when a row at the chosen level is found.

## What stays attested and why

Three rows have no evidence a tool can read, and only a person can vouch for them:

- Art. 6, lawfulness of processing: that each purpose rests on the lawful basis recorded.
- Art. 24, responsibility of the controller: that duties are owned, resourced and reviewed.
- Art. 37-39, data protection officer: that the role is designated, independent and involved.

## Review status

Every row and both timeline entries are flagged `mapping not yet reviewed`. No flag has been cleared.
The 72-hour and one-month periods were read on EUR-Lex (CELEX 32016R0679).

## Disclaimer

Evidence found gives Met, Partial or Missing, not a legal conclusion. This pack is not an audit, a
certification or legal advice; ask a qualified lawyer about your own duties.
