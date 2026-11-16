# EBA guidelines

Upstream status: the European Banking Authority guidelines in this pack are being withdrawn
in favour of DORA, and the status of each is to be confirmed on the authority's website.
Today 7 of 25 requirements checked from evidence (target 3); the other 18 take a provider
attestation. The mapping is not yet reviewed.

## What it is

`EBA` is a native, attestation-led pack. It carries one row per section of three EBA
guidelines: GL/2019/04 section 3.8 (ICT and security risk, as amended by GL/2025/02),
GL/2019/02 (outsourcing) and GL/2020/06 (loan origination). Ids are as published; each row
is a one-line description in this project's own words. The guidance text is not reproduced.

## Does it apply to you

The pack asks four questions: is the organisation a supervised institution, does it supply
one, does it grant or assess credit, and does it provide payment services. A supplier to an
institution gets the pack as `voluntary`. An organisation that is neither is `not_applicable`.
Answers to the credit and payment questions scope individual rows out. Confirm with your adviser.

## How rows are decided

Every row reads `Unverified` until you record an attestation. Seven rows are `hybrid`: a file
the scaffolds create gives supporting evidence next to the attestation. Evidence found gives
Met, Partial or Missing. It never lowers a row and never makes an unattested row Met.

## Requirements

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| EBA:GL/2019/04 3.8 | Payment service user relationship management | organisational | attestation: EBA:GL/2019/04 3.8 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 3 | Outsourcing (Title II, assessment of arrangements) | organisational | attestation: EBA:GL/2019/02 Section 3 | 730 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 4 | Critical or important functions | organisational | attestation: EBA:GL/2019/02 Section 4 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 5 | Sound governance arrangements and third-party risk | organisational | attestation: EBA:GL/2019/02 Section 5 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 6 | Sound governance arrangements and outsourcing | organisational | attestation: EBA:GL/2019/02 Section 6 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 7 | Outsourcing policy | organisational | attestation: EBA:GL/2019/02 Section 7 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 8 | Conflicts of interests | organisational | attestation: EBA:GL/2019/02 Section 8 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 9 | Business continuity plans | organisational | attestation: EBA:GL/2019/02 Section 9 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 10 | Internal audit function | organisational | attestation: EBA:GL/2019/02 Section 10 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 11 | Documentation requirements | hybrid | attestation: EBA:GL/2019/02 Section 11; artifact: vendor_register (corroborating) | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 12.1 | Supervisory conditions for outsourcing | organisational | attestation: EBA:GL/2019/02 Section 12.1 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 12.2 | Risk assessment of outsourcing arrangements | organisational | attestation: EBA:GL/2019/02 Section 12.2 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 12.3 | Due diligence | organisational | attestation: EBA:GL/2019/02 Section 12.3 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 13 | Contractual phase | hybrid | attestation: EBA:GL/2019/02 Section 13; artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 13.1 | Sub-outsourcing of critical or important functions | organisational | attestation: EBA:GL/2019/02 Section 13.1 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 13.2 | Security of data and systems | organisational | attestation: EBA:GL/2019/02 Section 13.2 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 13.3 | Access, information and audit rights | hybrid | attestation: EBA:GL/2019/02 Section 13.3; artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 13.4 | Termination rights | hybrid | attestation: EBA:GL/2019/02 Section 13.4; artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 14 | Oversight of outsourced functions | organisational | attestation: EBA:GL/2019/02 Section 14 | 365 | mapping not yet reviewed |
| EBA:GL/2019/02 Section 15 | Exit strategies | hybrid | attestation: EBA:GL/2019/02 Section 15; artifact: exit_plan (corroborating) | 365 | mapping not yet reviewed |
| EBA:GL/2020/06 4.3 | Credit risk policies and procedures | organisational | attestation: EBA:GL/2020/06 4.3 | 365 | mapping not yet reviewed |
| EBA:GL/2020/06 4.3.3 | Technology-enabled innovation for credit granting | organisational | attestation: EBA:GL/2020/06 4.3.3 | 365 | mapping not yet reviewed |
| EBA:GL/2020/06 4.3.4 | Models for creditworthiness assessment and credit decision-making | hybrid | attestation: EBA:GL/2020/06 4.3.4; artifact: model_card (corroborating); evaluator: EVAL_BIAS_FAIRNESS_V1 | 90 | mapping not yet reviewed |
| EBA:GL/2020/06 4.3.7 | Data infrastructure | hybrid | attestation: EBA:GL/2020/06 4.3.7; artifact: data_provenance_sheet (corroborating) | 365 | mapping not yet reviewed |
| EBA:GL/2020/06 5.1 | Information and documentation | organisational | attestation: EBA:GL/2020/06 5.1 | 365 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

`opencomplai scaffold` can create an outsourcing register at `docs/vendor-register.md`, shared
with the third-party pack. Fill it in; the vendor register probe then finds it.

## Timeline

Both entries are `mapping not yet reviewed`, have no application date and are low confidence.

- `eba.gl_2019_04_sections_withdrawn`: sections 3.1 to 3.7 of GL/2019/04 are reported as deleted upstream since DORA applies. Only section 3.8 stays in this pack. Mapping not yet reviewed.
- `eba.gl_2019_02_repeal_pending`: repeal of the GL/2019/02 outsourcing guideline is reported as pending. It covers the GL/2019/02 rows in this pack. Mapping not yet reviewed.

## Gate in CI

```sh
opencomplai check --target EBA --gate EBA --gate-fail-on missing --repo-root .
```

The gate exits 1 when a requirement it lists is Missing.

## What stays attested and why

18 rows are `organisational`: they describe governance, contracts or decisions that leave no
file in a repository. Only a person can vouch for them, so each row states why it takes an
attestation. The machine share is a low 7 of 25 because the guidelines are mostly outsourcing
governance; this is shown as it is.

## Review status

Every row and both timeline entries carry `mapping not yet reviewed`, at low confidence, and
are flagged for founder review. No flag is cleared.

## Disclaimer

Not an audit, certification or legal assessment. A result says what evidence was found, not
that an institution meets any guideline.
