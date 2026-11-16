# EIOPA Opinion on AI governance and risk management

This page covers `EIOPA_AI`, a pack of 8 requirements taken from the EIOPA Opinion on artificial intelligence governance and risk management (section 3, paragraphs 3.1 to 3.38, grouped into 8 rows). The Opinion sets supervisory expectations for insurance and reinsurance undertakings and creates no new legal duty. Nothing here is an audit, a certification or a legal assessment.

## What it is

A native pack. Each row groups a range of paragraphs, with the ids as published, a one-line description in this project's own words, and links to other frameworks that are the project's own judgement. The guidance text is not reproduced. Every row is at low confidence and reads `mapping not yet reviewed`.

## Does it apply to you

The pack asks two questions in the manifest under `framework_inputs.EIOPA_AI`: whether the organisation is an insurance or reinsurance undertaking (or supplies AI to one), and whether the AI system is high-risk under the EU AI Act. An answer of no to the first reads not applicable. A high-risk system reads not applicable too, because the Opinion leaves it to the EU AI Act. With no answers the pack reads voluntary. Confirm with your adviser.

## How rows are decided

Every row takes a provider attestation. 7 of 8 requirements are checked from evidence as well: files and conventions in the repository corroborate the attestation. 1 of 8 is attestation only. The target is 4 of 8; the pack is above it. A scaffold left unfilled does not count as evidence. A row reads Met, Partial, Missing or Unverified.

| Evidence class | Rows |
|---|---|
| Machine | 1 |
| Hybrid | 6 |
| Organisational | 1 |

## Requirements

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| EIOPA_AI:3.1-3.6 | Risk-based approach and proportionality | organisational | attestation: EIOPA_AI:3.1-3.6 | 365 | mapping not yet reviewed |
| EIOPA_AI:3.7-3.11 | Risk management system | hybrid | attestation: EIOPA_AI:3.7-3.11; artifact: risk_register (corroborating); artifact: policy_ai (corroborating) | 365 | mapping not yet reviewed |
| EIOPA_AI:3.12-3.16 | Fairness and ethics | machine | attestation: EIOPA_AI:3.12-3.16; evaluator: EVAL_BIAS_FAIRNESS_V1 | 90 | mapping not yet reviewed |
| EIOPA_AI:3.17-3.21 | Data governance | hybrid | attestation: EIOPA_AI:3.17-3.21; artifact: data_provenance_sheet (corroborating); scan: pii_dataflow (corroborating) | 365 | mapping not yet reviewed |
| EIOPA_AI:3.22-3.24 | Documentation and record keeping | hybrid | attestation: EIOPA_AI:3.22-3.24; artifact: event_log_evidence (corroborating); artifact: technical_documentation_dossier (corroborating) | 365 | mapping not yet reviewed |
| EIOPA_AI:3.25-3.28 | Transparency and explainability | hybrid | attestation: EIOPA_AI:3.25-3.28; artifact: model_card (corroborating); artifact: deployer_instructions (corroborating) | 365 | mapping not yet reviewed |
| EIOPA_AI:3.29-3.33 | Human oversight | hybrid | attestation: EIOPA_AI:3.29-3.33; artifact: human_oversight_construct (corroborating) | 365 | mapping not yet reviewed |
| EIOPA_AI:3.34-3.38 | Accuracy, robustness and cybersecurity | hybrid | attestation: EIOPA_AI:3.34-3.38; evaluator: EVAL_ADVERSARIAL_V1; artifact: security_policy_file (corroborating) | 180 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

One starting document is written into the repository on request: an AI policy (`docs/policies/ai-policy.md`). It has `_fill in_` placeholders. A control template helps with the insurer-side AI controls. They are drafts, not legal advice.

## Timeline

This pack has no timeline: a supervisory opinion without application dates of its own.

## Gate in CI

```sh
opencomplai check --target EIOPA_AI --gate EIOPA_AI --gate-fail-on missing --repo-root .
```

The command exits 1 and lists the requirement ids when a row at the chosen level is found.

## What stays attested and why

One row has no evidence a tool can read, and only a person can vouch for it:

- EIOPA_AI:3.1-3.6, risk-based approach and proportionality: that the measures fit the risk of each AI use and the size of the undertaking.

## Review status

Every row is flagged `mapping not yet reviewed`. No flag has been cleared.

## Disclaimer

Evidence found gives Met, Partial or Missing, not a legal conclusion. This pack is not an audit, a certification or legal advice; ask a qualified lawyer about your own duties.
