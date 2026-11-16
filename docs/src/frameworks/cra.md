# Cyber Resilience Act

## What it is

Regulation (EU) 2024/2847, the Cyber Resilience Act, sets cybersecurity duties for
manufacturers of products with digital elements: security by design, vulnerability handling,
user information, technical documentation and reporting to authorities. Opencomplai carries it
as the native target `CRA`, with 63 requirement rows. Article and annex numbers are as
published; the short titles and notes are this project's own wording.

The pack reads evidence in your repository and reports Met, Partial, Missing or Unverified per
row. It is not an audit, a certification or a legal assessment.

## Does it apply to you

Five questions decide it, answered under `framework_inputs.CRA`:

| Question | An answer that rules the Act out or changes your role |
|---|---|
| Do you place connectable software or hardware on the EU market? | No: the Act does not cover it |
| Is it only a hosted service, with nothing running on the user's side? | Yes: outside the Act (another law, such as NIS2, may apply) |
| Is it supplied commercially? | No: outside the Act |
| Is it a medical device, vehicle, aviation or marine product? | Yes: the sector's own EU law applies |
| Do you make it, or market it under your name? | No: the rows are manufacturer duties and apply only voluntarily |

A hosted AI service alone may be out of scope. If you ship software, a container image, a
device or a client library that others run, it is likely in scope. Confirm with your adviser.

## How rows are decided

Rows are checked from evidence in the repository, not decided by hand. Every row names the
probes that look for its evidence and, where a person must vouch for something, an attestation.
A found file gives a draft reading; it does not prove the control works. A row that only
a person can vouch for stays `Unverified` until someone attests to it.

As of this page, 50 of 63 requirements are checked from evidence (target 36): 0 machine, 50
hybrid and 13 organisational. A hybrid row combines a probe with an attestation.

## Requirements

The table is generated from `requirements.json` by `tools/packs/pack_doc.py CRA`.

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| CRA:Art. 13(2) | Cybersecurity risk assessment | hybrid | attestation: CRA:Art. 13(2); artifact: ai_threat_model (corroborating); artifact: cra.technical_documentation#3 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(3) | Documented, updated risk assessment | hybrid | attestation: CRA:Art. 13(3); artifact: cra.technical_documentation#3 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(5) | Due diligence on third-party components | hybrid | attestation: CRA:Art. 13(5); artifact: sbom_file (corroborating); artifact: ai_supply_chain_pins (corroborating); artifact: dependency_update_config (corroborating) | 90 | mapping not yet reviewed |
| CRA:Art. 13(6) | Component flaws reported upstream and fixed | hybrid | attestation: CRA:Art. 13(6); artifact: vulnerability_handling_policy (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(7) | Systematic cybersecurity documentation | hybrid | attestation: CRA:Art. 13(7); artifact: cra.technical_documentation#2 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(8) | Support period and vulnerability handling | hybrid | attestation: CRA:Art. 13(8); artifact: cra.support_period_statement (corroborating); artifact: vulnerability_handling_policy (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(9) | Security updates kept available | hybrid | attestation: CRA:Art. 13(9); artifact: update_mechanism_note (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(12) | Documentation, assessment, declaration and CE mark | organisational | attestation: CRA:Art. 13(12) | 365 | mapping not yet reviewed |
| CRA:Art. 13(13) | Documentation kept for 10 years | organisational | attestation: CRA:Art. 13(13) | 365 | mapping not yet reviewed |
| CRA:Art. 13(14) | Conformity across series production | organisational | attestation: CRA:Art. 13(14) | 365 | mapping not yet reviewed |
| CRA:Art. 13(15) | Product identification number | organisational | attestation: CRA:Art. 13(15) | 365 | mapping not yet reviewed |
| CRA:Art. 13(16) | Manufacturer contact details on product | organisational | attestation: CRA:Art. 13(16) | 365 | mapping not yet reviewed |
| CRA:Art. 13(17) | Single point of contact | hybrid | attestation: CRA:Art. 13(17); artifact: security_policy_file (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(18) | User information and instructions supplied | hybrid | attestation: CRA:Art. 13(18); artifact: cra.user_information#8 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(19) | Support period end date stated | hybrid | attestation: CRA:Art. 13(19); artifact: cra.support_period_statement (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 13(20) | Declaration of conformity supplied | organisational | attestation: CRA:Art. 13(20) | 365 | mapping not yet reviewed |
| CRA:Art. 13(21) | Corrective action, withdrawal or recall | organisational | attestation: CRA:Art. 13(21) | 365 | mapping not yet reviewed |
| CRA:Art. 13(22) | Cooperation with market surveillance | organisational | attestation: CRA:Art. 13(22) | 365 | mapping not yet reviewed |
| CRA:Art. 13(23) | Notice before ceasing operations | organisational | attestation: CRA:Art. 13(23) | 365 | mapping not yet reviewed |
| CRA:Art. 14(1) | Actively exploited vulnerability reporting | hybrid | attestation: CRA:Art. 14(1); artifact: cra.vulnerability_notification_record#early-warning (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 14(3) | Severe incident reporting | hybrid | attestation: CRA:Art. 14(3); artifact: cra.vulnerability_notification_record#notification (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 14(8) | Users informed of exploited flaws and incidents | hybrid | attestation: CRA:Art. 14(8); artifact: cra.vulnerability_notification_record#user-information (corroborating) | 365 | mapping not yet reviewed |
| CRA:Art. 28 | EU declaration of conformity | organisational | attestation: CRA:Art. 28 | 365 | mapping not yet reviewed |
| CRA:Art. 30 | CE marking | organisational | attestation: CRA:Art. 30 | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (1) | Risk-based level of cybersecurity by design | hybrid | attestation: CRA:Annex I Part I (1); artifact: ai_threat_model (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(a) | No known exploitable vulnerabilities at release | hybrid | attestation: CRA:Annex I Part I (2)(a); artifact: sast_config (corroborating); artifact: dependency_update_config (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(b) | Secure by default configuration | hybrid | attestation: CRA:Annex I Part I (2)(b); artifact: secure_defaults_config (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(c) | Vulnerabilities fixable by security updates | hybrid | attestation: CRA:Annex I Part I (2)(c); artifact: update_mechanism_note (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(d) | Protection from unauthorised access | hybrid | attestation: CRA:Annex I Part I (2)(d); artifact: policy_access_control (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(e) | Confidentiality of data | hybrid | attestation: CRA:Annex I Part I (2)(e); artifact: policy_cryptography (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(f) | Integrity of data, commands and programs | hybrid | attestation: CRA:Annex I Part I (2)(f); artifact: signed_release_config (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(g) | Data minimisation | hybrid | attestation: CRA:Annex I Part I (2)(g); scan: pii_dataflow (corroborating) | 90 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(h) | Availability of essential functions | hybrid | attestation: CRA:Annex I Part I (2)(h); artifact: rate_limiting_config (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(i) | Limited impact on other devices and networks | organisational | attestation: CRA:Annex I Part I (2)(i) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(j) | Limited attack surface | hybrid | attestation: CRA:Annex I Part I (2)(j); artifact: iac_definitions (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(k) | Exploitation mitigation | hybrid | attestation: CRA:Annex I Part I (2)(k); artifact: sast_config (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(l) | Security logging and monitoring | hybrid | attestation: CRA:Annex I Part I (2)(l); artifact: event_log_evidence (corroborating) | 90 | mapping not yet reviewed |
| CRA:Annex I Part I (2)(m) | Secure permanent data removal | organisational | attestation: CRA:Annex I Part I (2)(m) | 365 | mapping not yet reviewed |
| CRA:Annex I Part II (1) | Vulnerabilities and components documented, SBOM | hybrid | attestation: CRA:Annex I Part II (1); artifact: ai_supply_chain_pins (corroborating); artifact: sbom_file (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part II (2) | Vulnerabilities remediated without delay | hybrid | attestation: CRA:Annex I Part II (2); artifact: vulnerability_handling_policy (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part II (3) | Regular security tests and reviews | hybrid | attestation: CRA:Annex I Part II (3); artifact: ci_test_workflow (corroborating); artifact: sast_config (corroborating) | 180 | mapping not yet reviewed |
| CRA:Annex I Part II (4) | Public disclosure of fixed vulnerabilities | hybrid | attestation: CRA:Annex I Part II (4); artifact: vulnerability_handling_policy (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part II (5) | Coordinated vulnerability disclosure policy | hybrid | attestation: CRA:Annex I Part II (5); artifact: vulnerability_handling_policy (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part II (6) | Vulnerability information sharing and contact | hybrid | attestation: CRA:Annex I Part II (6); artifact: security_policy_file (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part II (7) | Secure distribution of updates | hybrid | attestation: CRA:Annex I Part II (7); artifact: signed_release_config (corroborating); artifact: update_mechanism_note (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex I Part II (8) | Updates disseminated without delay | hybrid | attestation: CRA:Annex I Part II (8); artifact: update_mechanism_note (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (1) | Manufacturer identity and contact | hybrid | attestation: CRA:Annex II (1); artifact: cra.user_information#1 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (2) | Vulnerability reporting contact | hybrid | attestation: CRA:Annex II (2); artifact: cra.user_information#2 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (3) | Product identification | hybrid | attestation: CRA:Annex II (3); artifact: cra.user_information#3 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (4) | Intended purpose and security properties | hybrid | attestation: CRA:Annex II (4); artifact: cra.user_information#4 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (5) | Known risk circumstances and foreseeable misuse | hybrid | attestation: CRA:Annex II (5); artifact: cra.user_information#5 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (6) | Web address of declaration of conformity | hybrid | attestation: CRA:Annex II (6); artifact: cra.user_information#6 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (7) | Security support offered and end date | hybrid | attestation: CRA:Annex II (7); artifact: cra.user_information#7 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (8) | Instructions for secure use through to decommissioning | hybrid | attestation: CRA:Annex II (8); artifact: cra.user_information#8 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex II (9) | Location of the SBOM if offered | hybrid | attestation: CRA:Annex II (9); artifact: cra.user_information#9 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex VII (1) | General description of the product | hybrid | attestation: CRA:Annex VII (1); artifact: cra.technical_documentation#1 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex VII (2) | Design, development, production, vulnerability handling | hybrid | attestation: CRA:Annex VII (2); artifact: cra.technical_documentation#2 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex VII (3) | Cybersecurity risk assessment in the file | hybrid | attestation: CRA:Annex VII (3); artifact: cra.technical_documentation#3 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex VII (4) | Basis for the support period | hybrid | attestation: CRA:Annex VII (4); artifact: cra.technical_documentation#4 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex VII (5) | Standards and solutions applied | hybrid | attestation: CRA:Annex VII (5); artifact: cra.technical_documentation#5 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex VII (6) | Test reports | hybrid | attestation: CRA:Annex VII (6); artifact: cra.technical_documentation#6 (corroborating) | 180 | mapping not yet reviewed |
| CRA:Annex VII (7) | Copy of the declaration of conformity | hybrid | attestation: CRA:Annex VII (7); artifact: cra.technical_documentation#7 (corroborating) | 365 | mapping not yet reviewed |
| CRA:Annex VII (8) | SBOM available on authority request | hybrid | attestation: CRA:Annex VII (8); artifact: cra.technical_documentation#8 (corroborating) | 365 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

The scaffold command writes four starting documents, each with `_fill in_` placeholders you
replace with your own facts:

| Document | Written to |
|---|---|
| Vulnerability handling policy | `docs/vulnerability-handling.md` |
| Support period statement | `SUPPORT.md` |
| Technical documentation | `CRA_TECHNICAL_DOCUMENTATION.md` |
| User security information | `docs/security-information.md` |

Remediation templates exist for the reporting record, the secure-by-default property, the
technical file points, the user information points and vulnerability handling.

To produce a software bill of materials:

1. Generate it in CI with your build ecosystem's SPDX or CycloneDX tool.
2. Write it to the repository as `sbom.json`, `bom.json`, `*.spdx.json` or `*.cdx.json`.
3. Keep the header key `spdxVersion` (SPDX) or `bomFormat` (CycloneDX) in the file.
4. The `sbom_file` check reads only those file names and that header key, nothing else.
5. It does not check that the list is complete or current; a person reviews that.

## Timeline

The dates come from `timeline.json`. Each entry is marked `mapping not yet reviewed`.

| Entry | Applies | Rows |
|---|---|---|
| Reporting duties start to apply | 2026-09-11 | 3; mapping not yet reviewed |
| General application of the Regulation | 2027-12-11 | 60; mapping not yet reviewed |
| Early warning notification | 24 hours after becoming aware | 2; mapping not yet reviewed |
| Vulnerability or incident notification | 72 hours after becoming aware | 2; mapping not yet reviewed |
| Final report on an actively exploited vulnerability | 14 days after a corrective measure is available | 1; mapping not yet reviewed |
| Final report on a severe incident | one month after the notification | 1; mapping not yet reviewed |

## Gate in CI

```sh
opencomplai check --target CRA --gate CRA --gate-fail-on missing --repo-root .
```

The gate exits 1 when a row reads `Missing`, and lists the requirement ids. An `Unverified`
row does not fail it unless you choose a stricter `--gate-fail-on`.

## What stays attested and why

13 rows are organisational: only a person can vouch for them, for example that documents are
retained for the required period or that production procedures keep each unit in line. Record
each under `framework_inputs.CRA.attested` with a statement, who made it and the date.
The pack data states the reason per row.

## Review status

Every row and timeline entry carries `confidence: low` and `needs_founder_review`. The
mapping to the EU AI Act and ISO/IEC 27001 is the project's own judgement and reads
`mapping not yet reviewed`. No flag has been cleared.

## Disclaimer

This page and the pack are not an audit, a certification or a legal assessment. A reading of
Met means evidence was found, not that the Act is satisfied. Take legal advice on whether and
how the Regulation applies to your product.
